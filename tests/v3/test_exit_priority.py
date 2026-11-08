"""Recognised exit bypasses queued work; Java alias is narrowly exit-only."""
import os,sys,tempfile,threading
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-exit-priority-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.paths import enter
enter()
from jarvis3.control import assistant_exit,ControlQueue,CANCEL_INFERENCE
from jarvis3.engine.ears import Ears,Heard
from jarvis3.engine.understand import Plan,Call
from jarvis3.engine import ui,understand
from jarvis3.engine.osapi import Fake
for text in ('shutdown','Shut down.','please shut down','Jarvis, shut down','can you please shut down'):
    assert assistant_exit(text),text
for text in ('shut up','shut down the computer','close the second tab','Java shutdown hook','how do I shut down'):
    assert not assistant_exit(text),text
ear=Ears(None,None,None,lambda h:None)
for text in ('Java Shutdown.','Java, shut down','Hey Java, please quit'):
    out=ear.decide(text);assert out and assistant_exit(out[0]) and out[1]=='name',text
for text in ('Java shutdown hook','I said Java shutdown','Java open chrome','Shutdown'):
    assert ear.decide(text) is None,text
class NoAI:
    loaded=False
    def complete(self,*a,**k):return 'ASK: Which app?'
    def unload(self):pass
with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None):
    app=ui.UiApp(gui=False,tray=False);app.voice.ears=ear;said=[];app.say=lambda *a:said.append(a)
    entered=threading.Event()
    def delayed(*a,**k):
        entered.set();assert CANCEL_INFERENCE.wait(2)
        return Plan('act',calls=[Call('open',{'target':'chrome'})],source='ai')
    with patch.object(understand,'resolve',side_effect=delayed):
        exit_capture_generation=app.conversation.generation
        worker=threading.Thread(target=app.submit,args=('do this background request',));worker.start()
        assert entered.wait(1)
        app.q.put(('typed','open notepad'))
        app._heard(Heard('Shutdown','name','',0,1,conversation_generation=exit_capture_generation))
        assert app.q.get_nowait()=='quit','exit waited behind older requests'
        worker.join(2);assert not worker.is_alive() and not app.engine.os.log and not said,'stale model result executed/spoke after exit'
    assert app._shutdown_requested.is_set() and app.engine.exit_requested and ear.cancel_output.is_set()
    app._request_shutdown();assert app.q.qsize()==1,'duplicate shutdown enqueued another exit'
    app.store.db.close();app.engine.memory.db.close()
CANCEL_INFERENCE.clear();ear.shutdown()
print('EXIT: strict Java-shutdown recovery, negative room cases, urgent queue, inference cancellation and stale action/speech suppression passed')
