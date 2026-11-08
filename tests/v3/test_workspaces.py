"""Workspace profiles, first-run approval, changed-plan guard and fail-stop resume."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-workspace-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.workspaces import save,profiles
store=Store(':memory:');pc=Fake(running=());app=App(pc,store,None,natural=False)
save(app.memory,'study',['notepad','chrome'],['https://example.com/'],'edge',app.catalog)
reply=app.handle('continue working on study');assert reply.plan.kind=='ask' and not pc.log and 'notepad' in reply.text
# Material edit between preview and yes must ask again, never silently approve.
save(app.memory,'study',['notepad','edge'],['https://example.com/'],'edge',app.catalog)
reply=app.handle('yes');assert reply.plan.kind=='ask' and not pc.log and 'edge' in reply.text
pc.fail.add('edge');reply=app.handle('yes')
assert not reply.ok and len([c for c in pc.log if c[:2]==('open','notepad')])==1
assert not any(c[0]=='url' for c in pc.log),'ran beyond failed step'
pc.fail.clear();reply=app.handle('resume workspace study');assert reply.ok
assert len([c for c in pc.log if c[:2]==('open','notepad')])==1,'replayed successful step on resume'
assert profiles(app.memory)[0]['state']=='ready'
assert not app.handle('resume workspace study').ok
before=list(pc.log)
try:save(app.memory,'bad',['powershell'],[],'edge',app.catalog);raise AssertionError('shell profile accepted')
except ValueError:pass
try:save(app.memory,'bad',['notepad'],['javascript:evil()'],'edge',app.catalog);raise AssertionError('script URL accepted')
except ValueError:pass
assert pc.log==before
save(app.memory,'cancel-test',['notepad','chrome'],[],'edge',app.catalog);pc._running.clear();pc.log.clear()
app.handle('start workspace cancel-test');original=pc.open
def first(*args,**kwargs):
    result=original(*args,**kwargs);app.workspace_cancel.set();return result
with patch.object(pc,'open',side_effect=first):assert app.handle('yes').ok
assert len(pc.log)==1 and profiles(app.memory)[0]['state']=='paused'
assert app.handle('resume workspace cancel-test').ok and len(pc.log)==2
with tempfile.TemporaryDirectory(prefix='v3-owned-project-') as project:
    pc.log.clear();pc.open=original;app.workspace_cancel.clear()
    save(app.memory,'project',[],[],'edge',app.catalog,[project])
    reply=app.handle('start workspace project');assert reply.plan.kind=='ask' and project in reply.text and not pc.log
    assert app.handle('yes').ok and pc.log==[('folder_path',str(Path(project).resolve()))]
    save(app.memory,'project',['notepad'],[],'edge',app.catalog,[project])
    assert app.handle('start workspace project').plan.kind=='ask','folder/app plan edit skipped approval'
try:
    save(app.memory,'bad path',[],[],'edge',app.catalog,['relative/path'])
    raise AssertionError('Relative project path accepted')
except ValueError:pass
store.db.close();app.memory.db.close()
print('WORKSPACES: editable profile, exact preview/approval, changed-plan refusal, failure stop, no-replay resume and unsafe profile rejection passed')
