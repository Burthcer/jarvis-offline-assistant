"""Self-corrections choose one final value; stored content stays data."""
import os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-natural-correction-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.corrections import corrected_request
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
store=Store(':memory:');pc=Fake();app=App(pc,store,None,natural=False)
try:
    for source,want in (
        ('set a timer for ten minutes actually no make it twenty five','set a timer for 25 minutes'),
        ('set a timer for 10 minutes actually 30 seconds','set a timer for 30 seconds'),
        ('set a timer for 10 minutes actually make it one hour and twenty minutes','set a timer for 1 hour and 20 minutes'),
        ('set volume to 30 actually no make it fifty five','volume 55'),
        ('open chrome actually edge','open edge'),
        ('open chrome actually no',''),
        ('remember my note is actually read the book','remember my note is actually read the book'),
        ('remember my note is open notepad, actually close chrome',None),
        ('remind me to actually finish the report tomorrow','remind me to actually finish the report tomorrow'),
        ('set a timer for ten minutes actually no the other thing',None)):
        assert corrected_request(source,app.catalog)==want,(source,corrected_request(source,app.catalog))
    for source,want in (
        ('set a timer for 10 minutes actually 20 seconds actually 30','set a timer for 30 seconds'),
        ('set a timer for 10 minutes actually two hours actually 20','set a timer for 20 hours'),
        ('open chrome actually close edge actually notepad','close notepad'),
        ('close chrome actually open edge actually notepad','open notepad'),
        ('set volume to 30 actually fifty actually seventy five','volume 75'),
        ('open chrome actually unknown thing actually edge',None),
        ('open chrome actually no, actually edge',None)):
        assert corrected_request(source,app.catalog)==want,(source,corrected_request(source,app.catalog))
    assert app.handle('open chrome actually edge').ok and pc.log[-1][1]=='edge'
    pc.log.clear();assert app.handle('open chrome actually no').ok and not pc.log
    assert not app.handle('remember my note is open notepad, actually close chrome').ok and not pc.log
    assert app.handle('set volume to 30 actually no make it fifty five').ok and pc.vol==55
    pc.log.clear()
    assert app.handle('open chrome actually close edge actually notepad').ok
    assert pc.log==[('close','notepad','app')],'an intermediate correction executed or final action inherited the wrong verb'
    app.ai=SimpleNamespace(complete=lambda *a,**k:'timer_set(duration="25 minutes")')
    assert app.handle('set a timer for ten minutes actually no make it twenty five').ok
    assert len(store.all_timers())==1 and store.all_timers()[0]['text']=='25-minute'
finally:store.db.close();app.memory.db.close()
print('NATURAL CORRECTIONS: compound numbers/units, final volume/app, cancellation, literal data and single timer passed')
