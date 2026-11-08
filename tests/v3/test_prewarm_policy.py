"""Wake-only warm-up uses fake models/devices and never loads model weights."""
import os,sys,queue,threading,tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from datetime import datetime
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-warm-policy-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from jarvis3.engine import ui
from jarvis3.engine.ears import Ears,Job
from jarvis3.conversation import Conversation
from jarvis3.engine.dialogue import Dialogue

class FakeAI:
    loaded=False
    def __init__(self):self.loads=0;self.done=threading.Event();self.thread=None
    def load(self):self.loads+=1;self.loaded=True;self.thread=threading.get_ident();self.done.set()

def fixture():
    app=ui.UiApp.__new__(ui.UiApp);app.cfg={'voice_on':True,'speak_replies':False,'cool_mode':False}
    app._closing=threading.Event();app._shutdown_requested=threading.Event();app._warming=threading.Lock()
    app.engine=NS(ai=FakeAI(),dialogue=Dialogue());app.conversation=Conversation();app.voice=ui.Voice(app)
    ears=Ears(None,None,None,lambda h:None);app.voice.ears=ears
    ears._capture_begin(1.,app.conversation.generation)
    job=Job(np.zeros(10,np.int16),1.,2.);job.voice_a=1.;job.conversation_generation=app.conversation.generation
    ears._capture_accept(job)
    event={'id':'test','capture_epoch':0,'sample_onset':1.,'conversation_generation':app.conversation.generation}
    app.feedback=NS(cue=lambda *a:False);app.q=queue.Queue()
    return app,event

app,event=fixture();app._warm_ai('hearing');app._warm_ai('listening')
assert not app.engine.ai.loads,'unaddressed VAD warmed AI'
app._wake(event)
assert app.engine.ai.done.wait(1) and app.engine.ai.loads==1
assert app.engine.ai.thread!=threading.get_ident(),'model warm-up blocked the wake callback'
app._wake(event);assert app.engine.ai.loads==1,'accepted duplicate wake loaded twice'
for invalidate in (
    lambda a,e:e.update(capture_epoch=10),
    lambda a,e:e.update(conversation_generation=-1),
    lambda a,e:a.voice.set_listening(False),
    lambda a,e:a.voice.ears._capture_begin(3.,a.conversation.generation),
    lambda a,e:a.cfg.update(cool_mode=True),
    lambda a,e:a._closing.set(),
    lambda a,e:a._shutdown_requested.set()):
    app,event=fixture()
    # Avoid real UI updates in the microphone-off fixture.
    app.set_note=lambda *a:None
    invalidate(app,event);app._wake(event)
    assert not app.engine.ai.loads,'revoked/off/cool/closing wake warmed AI'
# Recheck inside the asynchronous worker: disabling mic after scheduling wins.
app,event=fixture();pending=[]
class DeferredThread:
    def __init__(self,target,**kwargs):pending.append(target)
    def start(self):pass
with patch.object(ui.threading,'Thread',DeferredThread):app._wake(event);app._wake(event)
assert len(pending)==1
app.voice.listening=False;pending[0]()
assert not app.engine.ai.loads and app._warming.acquire(blocking=False)
app._warming.release()

# The real AI.complete path still loads on demand when understanding needs it.
# Inject only its native model object/module; no weights, CUDA or inference.
from jarvis3.engine.ai import AI
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.control import CANCEL_INFERENCE
from jarvis3.engine.understand import instant
ai=AI();loads=[]
model=NS(tokenize=lambda text:[1]*20,token_eos=lambda:0,
         create_chat_completion=lambda *a,**k:{'usage':{'prompt_tokens':20},'choices':[{'message':{'content':'timer_set(duration="20 minutes")'}}]},close=lambda:None)
def load():loads.append(True);ai.llm=model
ai.load=load;CANCEL_INFERENCE.clear()
store=Store(':memory:');engine=App(Fake(),store,ai,natural=False,clock=lambda:datetime(2026,11,6,10))
try:
    text='I need twenty minutes for my homework'
    assert instant(text,engine.names) is None,'fixture no longer exercises AI understanding'
    with patch.dict(sys.modules,{'llama_cpp':NS(LogitsProcessorList=list)}):reply=engine.handle(text)
    assert reply.ok and loads==[True] and len(store.all_timers())==1 and reply.plan.source=='ai'
finally:ai.unload();store.db.close();engine.memory.db.close()
print('PREWARM POLICY: VAD ignored, valid wake async once, revoked/off/cool/closing/deferred rejection, real completion on-demand path passed')
