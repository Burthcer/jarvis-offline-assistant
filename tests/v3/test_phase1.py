"""Phase 1 safety/order checks. Scripted transcripts and audio sinks, never speakers."""
import os,sys,tempfile,threading,time,queue
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-phase1-')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from jarvis3.paths import enter
enter()
import numpy as np
from jarvis3.feedback import Feedback,cue_audio
from jarvis3.engine.ears import Ears,Job,SR,BLOCK_S
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.engine.registry import ABILITIES,Result,ability
from jarvis3.engine.understand import Plan,Call

signals=[];accepted=[]
texts=iter(['Jarvis open','Jarvis open notepad','Jarvis open notepad'])
ear=Ears(None,None,lambda *args:next(texts),accepted.append)
ear.on_wake=signals.append
def job(kind,final=False):
    item=Job(np.zeros(SR,np.int16),0,1);item.voice_a=.128;item.kind=kind;item.final=final;item.final_at=time.monotonic()
    return item
for item in (job('wake_probe'),job('wake_probe')):ear.jobs.put(item)
thread=threading.Thread(target=ear._worker);thread.start()
ear.jobs.join()
assert len(signals)==1 and not accepted and not ear.armed_until,'wake probe executed/armed a partial request'
ear.jobs.put(job('transcript',True));ear.jobs.join();ear.stop=True;thread.join(2)
assert len(accepted)==1 and accepted[0].text=='open notepad' and len(signals)==1,'duplicate wake or command'
assert not thread.is_alive()
assert ear.decide('open notepad',started=5) is None,'unaddressed room command accepted'
assert ear.decide('my friend Jarvis said open notepad',started=5) is None
ear.arm(since=5);assert ear.decide('open notepad',started=5.1)==('open notepad','follow_up')
assert not Ears(None,None,None,lambda h:None)._complete('Jarvis open notepad'),'default completeness must not force action'

events=[]
pc=Fake();store=Store(':memory:');app=App(pc,store,None,natural=False)
app.on_verified=lambda results:events.append((list(pc.log),all(r.ok for _,r in results)))
assert app.handle('open notepad').ok and events[-1][0]==[('open','notepad','app',1,None)]
pc.fail.add('chrome');assert not app.handle('open chrome').ok and events[-1][1] is False
assert len(events)==2
app.handle('open bluebird');assert len(events)==2,'uncertain/no-action request announced success'
@ability('v3_test_confirm',None,risk='confirm')
def confirmed(args,ctx):return Result(True,'Checked')
pc.log.clear();plan=Plan('act',calls=[Call('open',{'target':'notepad'}),Call('v3_test_confirm',{})])
app._run(plan,'open and sensitive action','typed',app.clock(),{})
assert not pc.log,'an earlier step ran before the whole confirmation was checked'
del ABILITIES['v3_test_confirm']

tones=[cue_audio(k) for k in ('wake','success','error')]
assert all(a.dtype==np.int16 and 0<len(a)<24000//4 and abs(a.astype(np.int32)).max()<10000 for a in tones)
assert not np.array_equal(tones[1],tones[2])
emitted=[]
feedback=Feedback(lambda kind,token,start:(emitted.append((kind,token)),start(),True)[2])
token=feedback.begin();feedback.cue('wake','utterance1');feedback.cue('wake','utterance1')
assert emitted==[('wake','utterance1')]
feedback.record('verified',token);feedback.cue('success',token)
steps=feedback.snapshot();assert next(i for i,e in enumerate(steps) if e['event']=='verified')<next(i for i,e in enumerate(steps) if e['event']=='success-output-start')
muted=Feedback();muted.cue('wake','x');assert muted.snapshot()[-1]['event']=='wake-silent'

from jarvis3.launcher import acquire_voice
closed=[];kernel=SimpleNamespace(CreateMutexW=lambda *args:123,CloseHandle=closed.append)
with patch('ctypes.get_last_error',return_value=183):assert not acquire_voice(kernel) and closed==[123]

from jarvis3.engine import ui
class NoAI:
    loaded=False
    def complete(self,*a,**k):return 'ASK: Which app, sir?'
    def unload(self):pass
with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None):
    window=ui.UiApp(gui=False,tray=False)
    calls=[];window.feedback.send=lambda k,t,start:(calls.append(k),True)[1]
    window.submit('open notepad',spoken=True)
    assert calls==['success']
    window.engine.os.fail.add('chrome');window.submit('open chrome',spoken=True);assert calls==['success','error']
    window.submit('what app',spoken=True);assert calls==['success','error'],'question emitted completion'
    window.submit('open bluetooth settings',spoken=True)
    assert calls==['success','error'] and any(e['event']=='requested-unverified' for e in window.feedback.snapshot()),'unchecked launch dispatch generated a cue'
    window.cfg['quiet_enabled']=True
    with patch('jarvis3.engine.preferences.quiet',return_value=True):assert not window._cue('wake','x',lambda:None)
    api=ui.Api(window);assert api.v3_status({'audible_cues':False})['audible_cues'] is False
    window.store.db.close();window.engine.memory.db.close()
store.db.close();app.memory.db.close()
print('V3 PHASE1: wake-only probes, no duplicate effects, verified-before-cue, failure, quiet and confirmation isolation PASSED')
