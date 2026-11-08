"""Real local SQLite, no external actions. Corrections and stale-safe grouped undo."""
import os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime,timedelta
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-ledger-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.engine.understand import Plan,Call
from jarvis3.corrections import corrected_request
store=Store(':memory:');app=App(Fake(),store,None,natural=False)
pc=app.os
assert corrected_request('set a timer for ten minutes actually no make it fifteen')=='set a timer for fifteen minutes'
assert corrected_request('set a timer for 10 minutes actually make it 15 minutes')=='set a timer for 15 minutes'
assert corrected_request('open notepad actually close chrome')=='close chrome'
assert corrected_request('open notepad actually not that') is None
app.ai=SimpleNamespace(complete=lambda *a,**k:'timer_set(duration="fifteen minutes")')
assert app.handle('set a timer for ten minutes actually no make it fifteen').ok
assert len(store.all_timers())==1 and store.all_timers()[0]['text']=='15-minute'
assert app.handle('scratch that').ok and not store.all_timers()
app.ai=None
now=datetime.now()
def run(*calls):return app._run(Plan('act',calls=[Call(name,args) for name,args in calls]),'test','typed',now,{})
assert run(('timer_set',{'duration':900}),('reminder_add',{'text':'new reminder','when':now+timedelta(days=1)})).ok
assert len(store.all_timers())==1 and len(store.upcoming(now))==1
assert app.handle('scratch that').ok and not store.all_timers() and not store.upcoming(now)
assert run(('note_save',{'text':'my university is Original College'})).ok
ident=store.notes('university')[0]['id'];store.rename(ident,'my university is Later Edit')
reply=app.handle('undo last action');assert not reply.ok and 'changed afterwards' in reply.text
assert store.get(ident)['text']=='my university is Later Edit'
assert run(('reminder_add',{'text':'protected original','when':now+timedelta(days=1)})).ok
before=len(store.upcoming(now));app.pending=Plan('ask',raw=[('open',{'target':'chrome'})],pending={})
assert app.handle('scratch that').ok and len(store.upcoming(now))==before and app.pending is None
assert run(('note_save',{'text':'my postcode is 123456'})).ok
with patch.object(app.ledger,'clock',return_value=app.ledger.entries[-1]['at']+121):assert not app.handle('undo that').ok
# An external action blocks undoing an older local action accidentally.
app.handle('open notepad');assert not app.handle('scratch that').ok
assert store.notes('postcode')
assert app.handle('volume 70').ok and pc.vol==70
assert app.handle('scratch that').ok and pc.vol==50
app.handle('volume 70');pc.vol=63
assert not app.handle('scratch that').ok and pc.vol==63,'Undo overwrote a later volume adjustment'
assert run(('note_save',{'text':'my city is Test City'})).ok
app._run(Plan('act',calls=[Call('volume',{'action':'down'})]),'reduce the youtube volume','typed',now,{})
assert not app.handle('scratch that').ok and store.notes('city'),'Per-app volume undo targeted an older local action'
# A metadata-only edit need not update the item timestamp. It still owns the
# fact and must prevent a stale creation undo deleting the newly edited note.
assert run(('note_save',{'text':'my campus is Sample Campus'})).ok
ident=store.notes('campus')[0]['id'];store.set_aliases(ident,['study place'])
reply=app.handle('scratch that')
assert not reply.ok and 'changed afterwards' in reply.text and store.get(ident),'Undo deleted a fact after a later alias edit'
# Metadata unchanged by the recorded action still needs a later-edit guard.
assert run(('note_save',{'text':'my campus is Revised Campus'})).ok
assert store.notes('campus')[0]['id']==ident
store.set_aliases(ident,['study place','college location'])
assert not app.handle('scratch that').ok and store.get(ident)['text']=='my campus is Revised Campus'
# Newly attached repeat metadata must likewise protect its reminder.
assert run(('reminder_add',{'text':'sample study reminder','when':now+timedelta(days=2)})).ok
ident=store.upcoming(now)[-1]['id']
store.db.execute('INSERT INTO repeats(item_id,days) VALUES(?,?)',(ident,7));store.db.commit()
assert not app.handle('scratch that').ok and store.get(ident),'Undo deleted a reminder after a later repeat edit'
store.db.close();app.memory.db.close()
print('CORRECTION/LEDGER: explicit replacement, unknown correction refusal, grouped rollback, later edits, pending cancellation, expiry and external barrier passed')
