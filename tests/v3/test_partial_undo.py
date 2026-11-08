"""Local-only partial rollback in explicit mixed groups; fake PC, no real apps."""
import os,sys,tempfile
from pathlib import Path
from datetime import datetime,timedelta
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-partial-undo-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.engine.understand import Plan,Call

store=Store(':memory:');pc=Fake(running=());app=App(pc,store,None,natural=False);now=datetime.now()
def run(*calls):return app._run(Plan('act',calls=[Call(n,a) for n,a in calls]),'test','typed',now,{})
try:
 assert run(('note_save',{'text':'my older fact is Keep Me'})).ok
 assert run(('timer_set',{'duration':600}),('open',{'target':'notepad'}),('reminder_add',{'text':'sample deadline','when':now+timedelta(days=1)})).ok
 before=list(pc.log);reply=app.handle('scratch that')
 assert reply.ok and not store.all_timers() and not store.upcoming(now),'mixed action did not undo its exact local changes'
 assert pc.log==before and 'notepad' in pc._running,'partial undo changed/replayed the external app'
 assert 'notepad' in reply.text and 'left' in reply.text.lower(),'partial undo hid remaining app action'
 assert not app.handle('scratch that').ok and store.notes('older fact'),'second undo jumped across remaining external action'
 # A failed external attempt may still have had effects. Preserve its barrier
 # while undoing the exact local delta, without retrying that attempt.
 pc.fail.add('edge')
 assert not run(('timer_set',{'duration':900}),('open',{'target':'edge'})).ok
 before=list(pc.log);reply=app.handle('scratch that')
 assert reply.ok and not store.all_timers() and pc.log==before and 'edge' in reply.text
 assert not app.handle('scratch that').ok
 pc.fail.clear()
 # Mixed groups never use a native/window CheckedUndo even when available.
 assert run(('timer_set',{'duration':60}),('window_state',{'action':'minimize','target':'notepad'})).ok
 pose=pc.window_poses['notepad'];before=list(pc.log)
 reply=app.handle('scratch that')
 assert reply.ok and not store.all_timers() and pc.window_poses['notepad']==pose and pc.log==before
 assert 'minimize notepad' in reply.text
 # All later-revision checks happen before any local row is restored.
 assert run(('timer_set',{'duration':120}),('note_save',{'text':'my protected fact is Initial'}),('open',{'target':'chrome'})).ok
 ident=store.notes('protected fact')[0]['id'];store.set_aliases(ident,['later alias'])
 before=list(pc.log);reply=app.handle('scratch that')
 assert not reply.ok and store.all_timers() and store.get(ident) and pc.log==before,'stale partial rollback was not atomic'
 # Never retain secret note snapshots or selectively roll around them.
 assert run(('timer_set',{'duration':180}),('note_save',{'text':'my password is OpaqueSensitiveExample'}),('open',{'target':'chrome'})).ok
 entry=app.ledger.entries[-1]
 assert not entry['change'] and 'OpaqueSensitiveExample' not in repr(entry)
 assert not app.handle('scratch that').ok and store.notes('password')
 # A local no-op plus an external action must still block older undo.
 assert run(('timer_control',{'action':'status'}),('open',{'target':'notepad'})).ok
 assert not app.handle('scratch that').ok and store.notes('older fact')
 # Assignment/recurrence are Store-only: prove their complete state, including
 # repeat metadata, is removed without changing Memory commitments/jobs.
 from jarvis3.engine.organizer import rows
 memory_before=(rows(app.memory,'commitments'),rows(app.memory,'jobs'))
 ids_before={r['id'] for r in store.db.execute('SELECT id FROM items')}
 repeats_before=[tuple(r) for r in store.db.execute('SELECT * FROM repeats')]
 assert run(('assignment',{'text':'sample coursework','when':'tomorrow at 5 pm'}),('open',{'target':'chrome'})).ok
 assert app.handle('scratch that').ok
 assert {r['id'] for r in store.db.execute('SELECT id FROM items')}==ids_before
 assert run(('recurring_reminder',{'text':'sample daily study','schedule':'daily at 5 pm'}),('open',{'target':'chrome'})).ok
 assert app.handle('scratch that').ok
 assert {r['id'] for r in store.db.execute('SELECT id FROM items')}==ids_before
 assert [tuple(r) for r in store.db.execute('SELECT * FROM repeats')]==repeats_before
 assert (rows(app.memory,'commitments'),rows(app.memory,'jobs'))==memory_before
 # Cross-database organiser effects stay an external barrier as a whole.
 happens=(now+timedelta(days=20)).strftime('%d %B %Y')
 deadline=(now+timedelta(days=10)).strftime('%d %B %Y')
 assert run(('timer_set',{'duration':240}),('event_track',{'text':'sample workshop on '+happens+' registration closes '+deadline})).ok
 ids_before={r['id'] for r in store.db.execute('SELECT id FROM items')}
 assert not app.handle('scratch that').ok
 assert {r['id'] for r in store.db.execute('SELECT id FROM items')}==ids_before
 assert len(rows(app.memory,'commitments'))==len(memory_before[0])+1
finally:store.db.close();app.memory.db.close()
print('PARTIAL UNDO: exact local rollback, named external/failure/window barriers, later-edit atomic refusal, secret/no-op protection passed')
