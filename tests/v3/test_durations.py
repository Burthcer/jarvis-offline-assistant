"""Real SQLite timer lengths, deterministic routing, and fabricated-model guards."""
import os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from jarvis3.durations import seconds,evidenced
from jarvis3.engine.registry import Duration,Which,Ask,DROP

for words,want in [('twenty-five minutes',1500),('one hundred seconds',100),('one hundred and five seconds',105),
 ('one and a half hours',5400),('half an hour',1800),('a quarter of an hour',900),('one hour and twenty five minutes',5100),
 ('1h',None),('1hr',3600),('90 seconds',90),('0.5 minutes',30),('.5 minutes',30),('13-minute',780)]:
 assert seconds(words)==want,(words,seconds(words),want)
for words in ('minus five minutes','-5 minutes','twenty bananas five minutes','five minutes and open chrome','five minutes or ten minutes','twenty thirteen minutes'):
 assert seconds(words) is None,(words,seconds(words))
for value,request,ok in [('1 minute','set a timer for10 minutes',False),('1 minute','set a timer for 10 minutes',False),
 ('10 minutes','set a timer for 10 seconds',False),('1 minute','someone needs a timer',False),
 ('90 seconds','set a timer for one and a half minutes',True),('4500 seconds','one hour and fifteen minutes',True),
 ('30 minutes','set timers for ten minutes and twenty minutes',False),('25 minutes','set a twenty five minute timer',True),
 ('1 hour','set a timer for one hour and fifteen minutes',False),
 ('5 minutes','set a timer for minus five minutes',False),('5 minutes','set a timer for negative five minutes',False),
 ('5 minutes','set a timer for .5 minutes',False),('10 minutes','the code is x10minutes',False)]:
 assert evidenced(value,request)==ok,(value,request)
assert seconds('9'*400+' hours') is None,'overflow escaped duration bounds'
for value,text,want in [('25','pause the twenty five minute timer','1500'),
 ('twenty five','cancel the 25-second timer','25')]:
 assert Which().convert(value,SimpleNamespace(text=text,followup=False))==want,(value,text)
for value,text in [('10','pause the timer'),('5','pause the five minute and five second timer'),
 ('five minutes','cancel the twenty minute timer'),('all','pause the five minute timer'),('all','cancel all timers except the last one')]:
 try:Which().convert(value,SimpleNamespace(text=text,followup=False))
 except Ask:pass
 else:raise AssertionError((value,text,'constraint erased or expanded'))
# Even in a follow-up, history is not evidence for an invented length.
try:Duration().convert('10 minutes',SimpleNamespace(text='yes',followup=True))
except Ask:pass
else:raise AssertionError('follow-up permitted fabricated duration')

with tempfile.TemporaryDirectory(prefix='v3-durations-') as home:
 os.environ['JARVIS_V3_HOME']=home
 from jarvis3.engine.app import App
 from jarvis3.engine.osapi import Fake
 from jarvis3.legacy.store import Store
 from jarvis3.engine.abilities.timers import route
 store=Store(':memory:');pc=Fake();ai=SimpleNamespace(complete=lambda *a,**k:(_ for _ in ()).throw(AssertionError('clear timer used model')))
 app=App(pc,store,ai,natural=False)
 try:
  for request,want in [('set a timer for twenty five minutes',1500),('start a timer for one and a half hours',5400),
    ('a thirteen minute timer',780),('please set a timer for 1 hour and 15 minutes',4500),('keep a ten second timer',10)]:
   result=app.handle(request)
   assert result.ok and result.results[0][0].args=={'duration':want},(request,result.text)
   assert result.results[0][1].facts['seconds']==want
  assert not pc.log
  for request in ('a two minute and a four minute timer','set a timer','set a timer for twenty minutes and open chrome',
    'how do I set a timer for 5 minutes','do not set a 5 minute timer','set two timers for five minutes','set a timer for five minutes or ten minutes'):
   assert route(request) is None,request
  for row in store.all_timers():store.delete(row['id'])
  app.handle('set a timer for five minutes')
  only=store.all_timers()[0]['id']
  app.ai=SimpleNamespace(complete=lambda *a,**k:'timer_control(action="cancel", which="five minutes")')
  reply=app.handle('cancel the twenty minute timer')
  assert reply.plan.kind=='ask' and [r['id'] for r in store.all_timers()]==[only],'wrong length constraint was erased'
  app.ai=SimpleNamespace(complete=lambda *a,**k:'timer_control(action="pause", which="all")')
  reply=app.handle('pause the five minute timer')
  assert reply.plan.kind=='ask' and store.all_timers()[0]['status']=='open','specific timer became all'
  assert app.handle('pause all timers').ok and store.all_timers()[0]['status']=='paused'
 finally:store.db.close();app.memory.db.close()
print('DURATIONS: compound/fractional lengths, exact units/evidence, no-model timer creation and ambiguous/action boundaries passed')
