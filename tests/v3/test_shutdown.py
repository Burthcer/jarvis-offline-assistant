"""Shutdown and partial-start cleanup with owned fake sources; no devices/models."""
import os,sys,tempfile,queue,threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-stop-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.paths import enter
enter()
import numpy as np
from jarvis3.engine.ears import Ears,Job,MicStream,LoopRing,SR
from jarvis3.engine import ui
closed=[];heard=[];wake=[]
ear=Ears(SimpleNamespace(close=lambda:closed.append('mic')),SimpleNamespace(close=lambda:closed.append('reference')),None,heard.append)
ear.on_wake=wake.append
item=Job(np.zeros(SR,np.int16),0,1);item.text='Jarvis open notepad';ear.jobs.put(item)
ear.arm(since=0);ear.wake_pending=True;ear.shutdown()
ear._decide(item);ear._notify_wake(item)
assert set(closed)=={'mic','reference'} and ear.jobs.unfinished_tasks==0 and item.cancelled and not heard and not wake
assert not ear.armed_until and not ear.wake_pending
assert ear._submit([np.zeros(SR,np.int16)],0,0).cancelled
mic=MicStream.__new__(MicStream);mic.closed=threading.Event();mic.device_lock=threading.RLock();mic.s=SimpleNamespace(close=lambda:closed.append('stream'))
mic.watch_thread=threading.Thread(target=mic._watch);mic.watch_thread.start();mic.close()
assert mic.s is None and mic.read() is None and not mic.watch_thread.is_alive()
ring=LoopRing(start=False);ring.close();assert ring.closed.is_set()

class STT:
    def load(self):closed.append('stt loaded')
    def unload(self):closed.append('stt unloaded')
class Speaker:
    def __init__(self,**kwargs):pass
    def load(self):raise RuntimeError('injected voice failure')
    def shutdown(self):closed.append('speaker released')
owner=SimpleNamespace(cfg={'tts_volume':1,'tts_voice':'jarvis','wake_replies':[]},_closing=threading.Event(),voice=SimpleNamespace(ears=None,speaker=None),engine=SimpleNamespace(ai=SimpleNamespace(unload=lambda:closed.append('AI released')),chat_ai=None),q=queue.Queue())
owner._reply_over=lambda:None
with patch.object(ui,'Transcriber',STT),patch.object(ui,'Speaker',Speaker):ui.UiApp._boot(owner)
assert 'stt unloaded' in closed and 'speaker released' in closed and 'AI released' in closed
message=owner.q.get()
assert message[0]=='error' and 'injected voice failure' in message[1] and owner.voice.ears is None and owner.voice.speaker is None
print('V3 SHUTDOWN: sources/watchers closed, queued/late actions cancelled, partial startup releases models and speech PASSED')
