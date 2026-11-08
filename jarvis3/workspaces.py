"""Explicit editable workspace profiles; no shell or inferred personal defaults."""
import hashlib,json,re
from pathlib import Path
from .engine.knowledge import website_url
from .engine.registry import Result,Ask
def table(memory):memory._w("CREATE TABLE IF NOT EXISTS workspaces(name TEXT PRIMARY KEY,profile TEXT,approved TEXT DEFAULT '',cursor INTEGER DEFAULT 0,state TEXT DEFAULT 'ready')")
def profiles(memory):
    table(memory)
    return [{'name':r[0],**json.loads(r[1]),'state':r[2]} for r in memory._q('SELECT name,profile,state FROM workspaces ORDER BY name')]
def folder_path(value):
    if not isinstance(value,str) or len(value)>1000 or any(ord(c)<32 for c in value):raise ValueError('Choose a local project folder.')
    path=Path(value)
    if not path.is_absolute() or str(path).startswith(('\\\\','//')) or not path.is_dir():raise ValueError('Choose an existing local folder.')
    return str(path.resolve())

def validate(name,apps,urls,browser,catalog,folders=None,aliases=None):
    name=re.sub(r'\s+',' ',re.sub(r'[_-]',' ',name.strip().lower()))
    if not re.fullmatch(r'[a-z0-9][a-z0-9 _-]{0,39}',name):raise ValueError('Use a short workspace name with letters and numbers.')
    folders=[] if folders is None else folders
    if browser not in ('edge','chrome') or not isinstance(apps,list) or not isinstance(urls,list) or not isinstance(folders,list) or len(apps)+len(urls)+len(folders)>8:raise ValueError('Choose a browser and up to eight steps.')
    if any(not isinstance(a,str) or not a.strip() for a in apps):raise ValueError('Use app names as text.')
    apps=list(dict.fromkeys(a.strip().lower() for a in apps))
    if any(catalog.get(a) not in ('app','folder') or re.search(r'jarvis|python|terminal|powershell|command prompt',a,re.I) for a in apps):raise ValueError('Use installed app or known folder names. An assistant or command shell cannot be a workspace step.')
    clean=[]
    for value in urls:
        url=website_url(value.strip()) if isinstance(value,str) and value.strip() else None
        if not url:raise ValueError('Use full public website links, without passwords or spaces.')
        clean.append(url)
    folders=list(dict.fromkeys(folder_path(p) for p in folders))
    if not apps and not clean and not folders:raise ValueError('Add an app, folder or website first.')
    aliases=[] if aliases is None else aliases
    if not isinstance(aliases,list) or len(aliases)>6 or any(not isinstance(a,str) for a in aliases):raise ValueError('Use up to six short alternate workspace names.')
    aliases=list(dict.fromkeys(re.sub(r'\s+',' ',re.sub(r'[_-]',' ',a.strip().lower())) for a in aliases))
    if any(not re.fullmatch(r'[a-z0-9][a-z0-9 ]{0,39}',a) for a in aliases):raise ValueError('Use short alternate names with letters and numbers.')
    aliases=[a for a in aliases if a!=name]
    return name,{'apps':apps,'urls':list(dict.fromkeys(clean)),'browser':browser,**({'folders':folders} if folders else {}),**({'aliases':aliases} if aliases else {})}
def save(memory,name,apps,urls,browser,catalog,folders=None,aliases=None):
    name,profile=validate(name,apps,urls,browser,catalog,folders,aliases);table(memory)
    names={name,*profile.get('aliases',[])}
    with memory.lock:
        if any(names & {r['name'],*r.get('aliases',[])} for r in profiles(memory) if r['name']!=name):raise ValueError('That name already belongs to another workspace.')
        value=json.dumps(profile,sort_keys=True)
        row=memory._q('SELECT profile FROM workspaces WHERE name=?',name)
        if not row or row[0][0]!=value:memory._w('INSERT OR REPLACE INTO workspaces(name,profile) VALUES(?,?)',name,value)
    return name
def run(name,ctx,resume=False):
    name=re.sub(r'\s+',' ',re.sub(r'[_-]',' ',name.strip().lower()))
    table(ctx.memory);rows=ctx.memory._q('SELECT profile,approved,cursor,state FROM workspaces WHERE name=?',name.lower())
    if not rows:
        matches=[r['name'] for r in profiles(ctx.memory) if name in r.get('aliases',[])]
        if len(matches)==1:
            name=matches[0];rows=ctx.memory._q('SELECT profile,approved,cursor,state FROM workspaces WHERE name=?',name)
    if not rows:return Result(False,'Save that workspace in Settings first, sir.',exact=True)
    value,approved,cursor,state=rows[0];profile=json.loads(value)
    try:validate(name,profile['apps'],profile['urls'],profile['browser'],ctx.catalog,profile.get('folders'),profile.get('aliases'))
    except ValueError as e:return Result(False,str(e),exact=True)
    digest=hashlib.sha256(value.encode()).hexdigest()
    steps=[('app',a) for a in profile['apps']]+[('folder',p) for p in profile.get('folders',[])]+[('url',u) for u in profile['urls']]
    if approved!=digest:
        if not ctx.confirmed or getattr(ctx.app,'confirmation_data',{}).get('workspace_hash')!=digest:raise Ask('Workspace '+name+' will open '+', '.join(profile['apps']+profile.get('folders',[])+profile['urls'])+'. Shall I start, sir?',pending={'workspace':name,'workspace_hash':digest})
        ctx.memory._w('UPDATE workspaces SET approved=? WHERE name=? AND profile=?',digest,name,value)
    if resume and state!='paused':return Result(False,'That workspace has no paused steps, sir.',exact=True)
    cursor=cursor if resume else 0
    ctx.os.workspace_stop_events=(ctx.app.workspace_cancel,ctx.app.stop_requested)
    reused=0;requested=0
    def current():
        row=ctx.memory._q('SELECT profile,approved FROM workspaces WHERE name=?',name)
        return bool(row and row[0]==(value,digest))
    def changed():
        return Result(False,'That workspace changed, sir. Start it again to review the new steps.',{'profile_changed':True},exact=True)
    def progress(state):
        # Saving a replacement profile must never receive an old run's cursor.
        with ctx.memory.lock:
            if not current():return False
            ctx.memory._w('UPDATE workspaces SET cursor=?,state=? WHERE name=?',cursor,state,name)
            return True
    def present(kind,target):
        try:
            if kind=='app':return ctx.os.verify_open(target,ctx.catalog[target]) is True
            return ctx.os.workspace_present(kind,target,profile['browser']) is True
        except Exception:return False
    def stopped():
        return ctx.app.workspace_cancel.is_set() or ctx.app.stop_requested.is_set()
    def pause():
        if not progress('paused'):return changed()
        return Result(True,'Workspace stopped, sir.',{'cancelled':True},exact=True)
    while cursor<len(steps):
        if not current():return changed()
        if stopped():return pause()
        kind,target=steps[cursor]
        try:
            already=present(kind,target)
            if not current():return changed()
            if stopped():return pause()
            if already:ok=True;reused+=1
            else:
                # Recheck immediately before dispatch, without holding a DB
                # lock across Windows/Shell calls. An action already started
                # cannot be retracted by editing the profile.
                if not current():return changed()
                if stopped():return pause()
                if kind=='app':ok=ctx.os.open(target,ctx.catalog[target])
                elif kind=='folder':ok=ctx.os.open_folder_path(target)
                else:ok=ctx.os.url(profile['browser'],target)
                if ok:requested+=1
        except Exception:ok=False
        if not current():return changed()
        if not ok:
            if not progress('paused'):return changed()
            return Result(False,f'Stopped at workspace step {cursor+1}, sir. Say resume workspace {name} to retry that step.',exact=True)
        # Capture a URL's receipt before opening the next URL. App/folder
        # presence needs only the final pass, avoiding a duplicate native probe.
        if not already and kind=='url':present(kind,target)
        if not current():return changed()
        cursor+=1
        if not progress('requested' if cursor==len(steps) else 'paused'):return changed()
    # Earlier targets may have disappeared while later steps were opening.
    verified=all(not stopped() and current() and present(kind,target) and current() for kind,target in steps)
    if not current():return changed()
    if stopped():return pause()
    if not progress('ready' if verified else 'requested'):return changed()
    return Result(True,'Workspace ready, sir.' if verified else 'Workspace requested, sir.',{'requested':requested,'reused':reused,'verified':verified},exact=True)
