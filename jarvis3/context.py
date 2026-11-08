"""Request-scoped literal foreground title/address. No clipboard or page-text watch."""
import re
from .engine.uia import DENY_WINDOW,OWN_WINDOW
from .engine.understand import Plan,Call
from .legacy.timeparse import parse_when

CLIP_NOTE=re.compile(r'(?:(?:save|make|keep) (?:a )?note (?:about |from )(?:the |my |this )?clipboard(?: text| contents)?|(?:save|keep) (?:the |my )?clipboard(?: text| contents)? as (?:a )?note)[.!]?',re.I)
CLIP_REMINDER=re.compile(r'remind me (?:to (?P<task>.{1,80}?)|(?P<about>about)) (?:the |my |this )?clipboard(?: text| contents)?(?: (?P<when>.+))?[.!]?',re.I)

def is_request(text):
    return bool(CLIP_NOTE.fullmatch(text) or CLIP_REMINDER.fullmatch(text) or re.fullmatch(r'(?:save|make|keep) (?:a )?note about (?:this|that)[.!]?',text,re.I) or re.fullmatch(r'remind me to .{1,80}? (?:this|that)(?: .+)?[.!]?',text,re.I))

def reference(app):
    if hasattr(app.os,'reference'):r=app.os.reference()
    else:
        program,title=app.os.front();r={'program':program,'title':title,'url':None}
    from .reference import safe_url
    return r['program'],r['title'].strip(),safe_url(r.get('url'))

def clipboard_request(app,text,now,pending):
    note=CLIP_NOTE.fullmatch(text)
    reminder=CLIP_REMINDER.fullmatch(text)
    waiting=bool(pending and pending.get('kind')=='clipboard')
    if not note and not reminder and not waiting:return None
    if not note and not reminder:
        _,due=parse_when(text,now)
        if due is None or (now-pending['at']).total_seconds()>120:return None
    else:due=None
    if not getattr(app,'context_options',{}).get('clipboard_context',False):return Plan('ask',say='Turn on clipboard context in Settings first, sir.')
    try:
        _,title=app.os.front()
        if DENY_WINDOW.search(title):return Plan('ask',say='I cannot capture clipboard context from that protected window, sir.')
        if waiting and not note and not reminder:
            if app.os.clipboard_sequence()!=pending['sequence']:return Plan('ask',say='The clipboard changed, sir. Please ask for that reminder again.')
            content=pending['text']
        else:
            from .clipboard_capture import checked_text
            capture=app.os.clipboard_capture();content=checked_text(capture['text'])
            if type(capture.get('sequence')) is not int or capture['sequence']<=0:raise ValueError('Clipboard identity is unavailable, sir.')
    except ValueError as error:return Plan('ask',say=str(error))
    except Exception:return Plan('ask',say='I could not capture that clipboard text, sir.')
    app.context_source='Clipboard (explicit request)'
    if note:return Plan('act',calls=[Call('note_save',{'text':content})],source='context')
    if reminder:
        content=(reminder['task'] or 'Review')+': '+content
        _,due=parse_when(reminder['when'] or '',now)
        if due is None:
            app.context_pending={'kind':'clipboard','at':now,'sequence':capture['sequence'],'text':content}
            return Plan('ask',say='When should I remind you, sir?')
    return Plan('act',calls=[Call('reminder_add',{'text':content,'when':due})],source='context')
def request(app,text,now):
    note=re.fullmatch(r'(?:save|make|keep) (?:a )?note about (?:this|that)[.!]?',text,re.I)
    reminder=re.fullmatch(r'remind me to (.{1,80}?) (?:this|that)(?: (.+))?[.!]?',text,re.I)
    pending=getattr(app,'context_pending',None);app.context_pending=None;app.context_source=None
    clip=clipboard_request(app,text,now,pending)
    if clip is not None:return clip
    if pending and pending.get('kind')=='clipboard':pending=None
    if not note and not reminder and not pending:return None
    if pending and not note and not reminder:
        if (now-pending['at']).total_seconds()>120:return None
        _,due=parse_when(text,now)
        if due is None:return None
        try:current=reference(app)
        except Exception:current=None
        if current!=pending['front']:return Plan('ask',say='The active item changed, sir. Please name the reminder again.')
        return Plan('act',calls=[Call('reminder_add',{'text':pending['text'],'when':due})],source='context')
    try:program,title,url=reference(app)
    except Exception:return Plan('ask',say='Please name the item, sir. I could not read the active window title.')
    identity=(program,title,url)
    if not title or title.lower()==program.lower() or DENY_WINDOW.search(title) or OWN_WINDOW.search(title):
        return Plan('ask',say='Please name the item, sir. I cannot use this window as a reference.')
    title=title[:180];app.context_source='Foreground title ('+program[:50]+')'+(' + browser URL' if url else '')
    content=title+('\nURL: '+url if url else '')
    if note:return Plan('act',calls=[Call('note_save',{'text':'Active item: '+content})],source='context')
    task=reminder[1]+' '+content
    _,due=parse_when(reminder[2] or '',now)
    if due is None:
        app.context_pending={'at':now,'front':identity,'text':task}
        return Plan('ask',say='When should I remind you, sir?')
    return Plan('act',calls=[Call('reminder_add',{'text':task,'when':due})],source='context')
