"""Routines by voice and from the page: start opens everything, close closes everything. Fake PC, no model, no sound."""
import os,sys,tempfile,types
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-routines-')
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tests/v2')]
private=lambda text:text.replace('jarvis2.','jarvis3.engine.').replace('from jarvis import','from jarvis3.legacy import').replace('from jarvis.','from jarvis3.legacy.').replace("'jarvis.","'jarvis3.legacy.").replace('"jarvis.','"jarvis3.legacy.')
harness=types.ModuleType('harness');harness.__file__=str(ROOT/'tests/v2/harness.py');sys.modules['harness']=harness
exec(compile(private((ROOT/'tests/v2/harness.py').read_text(encoding='utf-8')),harness.__file__,'exec'),harness.__dict__)
class NoAI:
    def complete(self,msgs,temperature=0.0,max_tokens=90):raise AssertionError('the model was consulted: '+msgs[-1]['content'][-80:])
app,os_,store=harness.fresh(NoAI());app.natural=False
r=app.handle('learn a skill called study that opens notepad and then opens youtube and then keep a ten second timer')
assert r.ok and 'study' in app.memory.routines(),r.text
os_.log.clear();r=app.handle('start routine study')
assert r.ok and any(x[:2]==('open','notepad') for x in os_.log) and any(x[:2]==('open','youtube') for x in os_.log),(r.text,os_.log)
assert r.text=='Started the study routine, sir.',('one short line, not every step',r.text)
os_.log.clear();r=app.handle('close routine study')
closes=[x for x in os_.log if x[0]=='close']
assert r.ok and {x[1] for x in closes}>={'notepad','youtube'} and r.text=='Closed the study routine, sir.',(r.text,os_.log)
os_.log.clear();r=app.handle('close the study routine');assert r.ok and len([x for x in os_.log if x[0]=='close'])==2,r.text
r=app.handle('close routine nothing');assert not r.ok and 'no routine' in r.text,r.text
r=app.handle('learn a skill called quiet time that keep a ten second timer');assert r.ok
r=app.handle('close routine quiet time');assert not r.ok and 'nothing to close' in r.text,r.text
assert app.memory.routine_get('study') and not any(s['a']=='routine_close' for s in app.memory.routine_get('study'))
r=app.handle('when I say nested close routine study');assert not r.ok,'closing a routine cannot live inside a routine'
print('ROUTINES: taught, start opens all, close routine closes all (two phrasings), unknown/empty refused, no nesting, no model consulted')
