"""Early speech-only interruption, then one complete pivot. No device or sound."""
import os,sys,tempfile,time,threading,queue
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-interrupt-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from jarvis3.engine.ears import Ears,Job,BLOCK,SR
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.engine.ui import UiApp
from jarvis3.conversation import Conversation
from jarvis3.interrupts import request,begins
store=Store(':memory:');pc=Fake();app=App(pc,store,None,natural=False)
assert request('Stop talking, actually open notepad',app.is_complete)=='open notepad'
assert request('wait for the bus',app.is_complete) is None
assert not begins('the recording said stop talking')
calls=[];heard=[];busy=[True]
class STT:
    def __call__(self,a,h):return 'Stop talking' if len(a)==BLOCK else 'Stop talking, actually open notepad'
    def again(self,a):return ''
ear=Ears(None,None,STT(),heard.append);ear.is_complete=app.is_complete
ear.can_interrupt=lambda:busy[0]
ui=NS(_closing=threading.Event(),_shutdown_requested=threading.Event(),engine=app,conversation=Conversation(),q=queue.Queue())
class Speaker:
    def stop(self):calls.append('speech-stop');busy[0]=False
ui.voice=NS(speaker=Speaker())
ear.on_interrupt=lambda e:UiApp._early_interrupt(ui,e)
def job(kind,final=False):
    j=Job(np.zeros(BLOCK if kind=='wake_probe' else BLOCK*3,np.int16),1,2);j.voice_a=1.2;j.kind=kind;j.final=final;j.final_at=time.monotonic();j.speech_end_wall=time.monotonic();return j
worker=threading.Thread(target=ear._worker);worker.start()
try:
    ear.jobs.put(job('wake_probe'));ear.jobs.join()
    assert calls==['speech-stop'] and not pc.log and not heard,'prefix performed an action'
    assert ear.armed_from==1.2 and ui.conversation.reason=='interrupt','overlapping pivot was not eligible'
    busy[0]=True;ear.jobs.put(job('wake_probe'));ear.jobs.join()
    assert calls==['speech-stop'],'same utterance interrupted twice'
    ear.jobs.put(job('transcript',True));ear.jobs.join()
    assert len(heard)==1 and heard[0].text=='open notepad',heard
    assert app.handle(heard[0].text).ok and len(pc.log)==1,'pivot did not execute exactly once'
    assert ear.decide('wait for the bus',started=1.2) is None,'ambient phrase became command'
    assert ear.decide('stop talking',started=.9) is None,'pre-window speech accepted'
    assert ear.decide('open notepad',now=time.monotonic()+20,started=2) is None,'interrupt session never expired'
    other=Ears(None,None,None,heard.append);other.can_interrupt=lambda:True
    other.paused_until=float('inf');other._early_interrupt(job('wake_probe'),'stop talking');assert not other.interrupts
    other.paused_until=0;other.cancel_output.set();other._early_interrupt(job('wake_probe'),'stop talking');assert not other.interrupts
finally:
    ear.stop=True;worker.join(2);ear.shutdown();store.db.close();app.memory.db.close()
assert not worker.is_alive()
print('INTERRUPTION: prefix stops only speech, overlapping complete pivot once, deduplication/ambient/pre-window/expiry/mic-off/shutdown checks passed')
