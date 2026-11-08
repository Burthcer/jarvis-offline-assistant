"""Completion must survive independent readback, not just a successful method return."""
import os,sys,tempfile
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-proof-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.engine.understand import Plan,Call

store=Store(':memory:');app=App(Fake(),store,None,natural=False)
now=datetime.now();notices=[];app.on_verified=lambda results:notices.append(all(r.ok for _,r in results))
def run(name,**args):
    return app._run(Plan('act',calls=[Call(name,args)]),name,'typed',now,{})

real_add=store.add
def missing(text,due=None,kind='reminder',**kwargs):
    return {'id':99999,'text':text,'kind':kind,'due':due and due.isoformat()},False
with patch.object(store,'add',side_effect=missing):
    reply=run('timer_set',duration=600)
    assert not reply.ok and notices==[False],'Missing timer was announced complete'
    assert not run('reminder_add',text='test rent',when=now+timedelta(days=1)).ok
    assert not run('note_save',text='my university is Test College').ok

row,_=real_add('test rent',now+timedelta(days=1),'reminder')
with patch.object(store,'set_due',lambda *a:None):
    assert not run('reminder_change',item='test rent',when=now+timedelta(days=2)).ok,'Unchanged deadline passed verification'
with patch.object(store,'delete',lambda *a:None):
    assert not run('reminder_cancel',item='test rent').ok,'Unremoved reminder passed verification'

assert run('timer_set',duration=600).ok
with patch.object(store,'pause_timer',lambda *a:None):
    assert not run('timer_control',action='pause',which='all').ok,'Still-running timer passed pause verification'
assert run('timer_control',action='pause',which='all').ok
assert run('timer_control',action='resume',which='all').ok
assert run('timer_control',action='cancel',which='all').ok
assert run('note_save',text='my university is Test College').ok
with patch.object(store,'delete',lambda *a:None):
    assert not run('note_forget',query='university').ok
assert run('note_forget',query='university').ok
with patch.object(store,'repeat',lambda *a:None):
    assert not run('recurring_reminder',text='daily check',schedule='daily at 5 pm').ok,'Missing repeat schedule passed verification'
assert run('recurring_reminder',text='daily check',schedule='daily at 5 pm').ok
store.db.close();app.memory.db.close()
print('V3 EFFECT PROOF: missing writes, wrong deadline, failed deletion/pause/repeat refused; real SQLite changes verified')
