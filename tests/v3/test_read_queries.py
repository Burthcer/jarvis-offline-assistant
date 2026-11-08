"""Natural agenda queries use local readback; clock/data/actions stay separate."""
import os,sys,tempfile
from pathlib import Path
from datetime import datetime,timedelta
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-read-query-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.engine.understand import instant
now=datetime(2026,11,4,10)
store=Store(':memory:');pc=Fake();app=App(pc,store,None,natural=False,clock=lambda:now)
try:
 store.add('submit coursework',now+timedelta(hours=2),'reminder')
 store.add('buy vegetables',now+timedelta(days=1,hours=3),'reminder')
 store.add('visit library',now+timedelta(days=2,hours=1),'reminder')
 store.add('return headphones',now+timedelta(days=7,hours=1),'reminder')
 store.add('collect receipt',now-timedelta(days=1),'reminder')
 before=tuple(tuple(r) for r in store.db.execute('SELECT * FROM items ORDER BY id'))
 for query,day in (
  ('what do I have today','today'),
  ('what do we have for tomorrow','tomorrow'),
  ('what have I got on Friday','friday'),
  ("what's on my list for today",'today'),
  ('what is on our agenda tomorrow','tomorrow'),
  ('show me my reminders for tomorrow','tomorrow'),
  ('please read our reminders on Friday','friday')):
  reply=app.handle(query)
  assert reply.ok and reply.plan.source=='phrase' and len(reply.results)==1,(query,reply.text)
  call=reply.results[0][0]
  assert call.ability=='reminder_list' and call.args=={'day':day},(query,call)
  assert ('submit coursework' in reply.text)==(day=='today'),(query,reply.text)
  assert ('buy vegetables' in reply.text)==(day=='tomorrow'),(query,reply.text)
  assert ('visit library' in reply.text)==(day=='friday'),(query,reply.text)
 reply=app.handle('how many reminders do we have for tomorrow')
 assert reply.ok and reply.results[0][0].args=={'day':'tomorrow','count':True} and reply.results[0][1].facts['count']==1
 # A read of the current weekday includes the whole current day. An explicit
 # "next" remains the next occurrence, without changing deadline parsing.
 reply=app.handle('what do I have on Wednesday')
 assert reply.ok and 'submit coursework' in reply.text and 'return headphones' not in reply.text,'bare current weekday skipped today'
 reply=app.handle('what do I have this Wednesday')
 assert reply.ok and 'submit coursework' in reply.text and 'return headphones' not in reply.text,'explicit this weekday skipped today'
 reply=app.handle('what do I have next Wednesday')
 assert reply.ok and 'return headphones' in reply.text and 'submit coursework' not in reply.text,'explicit next weekday included today'
 reply=app.handle('what do I have yesterday')
 assert reply.ok and 'collect receipt' in reply.text and 'submit coursework' not in reply.text
 from jarvis3.engine.abilities.personal import day_bounds
 assert day_bounds('wednesday',now)[0].date()==(now+timedelta(days=7)).date(),'default deadline/clock day semantics changed'
 assert not pc.log and tuple(tuple(r) for r in store.db.execute('SELECT * FROM items ORDER BY id'))==before
 assert not pc.log and tuple(tuple(r) for r in store.db.execute('SELECT * FROM items ORDER BY id'))==before
 for query in ('what day is today','what is the day of the week','what is my college email','what do you know about me',
               'what do I have today and open chrome','show my reminders for tomorrow and delete them','what do I have for lunch today',
               'I wondered what do I have today','remember what do I have today'):
  hit=instant(query,app.names)
  assert not hit or all(a!='reminder_list' for a,_ in hit[1]),(query,hit)
finally:store.db.close();app.memory.db.close()
print('READ QUERIES: natural dated agenda reads, zero model/actions/writes, clock/fact/compound/data boundaries passed')
