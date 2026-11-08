import os,sys
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
os.environ['JARVIS_SILENT']='1'
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).parent)]
from harness import fresh,CLOCK
app,pc,_=fresh(None)
app.handle('open youtube'); pc.log.clear()
assert app.handle('close it').ok and pc.log[-1]==('close','youtube','site')
app.handle('open edge and chrome'); pc.log.clear()
assert app.handle('close it').plan.kind=='ask' and not pc.log
app,pc,_=fresh(SimpleNamespace(complete=lambda *a,**k:'ASK: Open what, sir?'))
app.handle('open'); r=app.handle('notepad')
assert r.ok and pc.log[-1]==('open','notepad','app',1,None)
assert app.last_report['steps'][0]['action']=='open' and 'timing' in app.last_report
app.clock=lambda:CLOCK+timedelta(minutes=3)
pc.log.clear()
assert app.handle('close it').plan.kind=='ask' and not pc.log
app,pc,_=fresh(None)
app.pending=SimpleNamespace(pending={'unsafe':'action'})
app.clock=lambda:CLOCK+timedelta(minutes=3)
assert app.pending is None,'stale confirmation must expire'
print('DIALOGUE AND DIAGNOSTICS PASSED')
