"""A same-utterance prefix name survives a dropped name in final transcription."""
import os,sys,tempfile,time,threading
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-prefix-address-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from jarvis3.engine.ears import Ears,Job,BLOCK
class STT:
    def __call__(self,a,h):return 'Jarvis open notepad' if len(a)==BLOCK else 'open notepad'
    def again(self,a):return ''
heard=[];wakes=[];ear=Ears(None,None,STT(),heard.append);ear.on_wake=wakes.append;ear.is_complete=lambda t:t.lower()=='open notepad'
def job(kind,onset=1.2,cancelled=False):
    j=Job(np.zeros(BLOCK if kind=='wake_probe' else BLOCK*3,np.int16),onset-.2,onset+1)
    j.voice_a=onset;j.kind=kind;j.final=kind!='wake_probe';j.final_at=time.monotonic();j.speech_end_wall=j.final_at;j.cancelled=cancelled;return j
worker=threading.Thread(target=ear._worker);worker.start()
try:
    ear.jobs.put(job('wake_probe'));ear.jobs.join()
    assert len(wakes)==1 and not heard and not ear.armed_until,'prefix opened an unrestricted window or executed early'
    ear.jobs.put(job('transcript'));ear.jobs.join()
    assert len(heard)==1 and heard[0].text=='open notepad' and heard[0].trigger=='name','same-utterance final name drop lost the command'
    ear.jobs.put(job('transcript',3.2));ear.jobs.join()
    assert len(heard)==1,'prefix authorised another utterance'
    ear.jobs.put(job('wake_probe',5.2,cancelled=True));ear.jobs.put(job('transcript',5.2));ear.jobs.join()
    assert len(heard)==1,'cancelled prefix authorised a command'
    ear.is_complete=lambda t:False
    ear.jobs.put(job('wake_probe',7.2));ear.jobs.put(job('transcript',7.2));ear.jobs.join()
    assert len(heard)==1,'unrecognised room text inherited a wake'
    ear.is_complete=lambda t:True
    ear.jobs.put(job('wake_probe',9.2));ear.jobs.join()
    key,at=ear.prefix_addresses[-1];ear.prefix_addresses[-1]=(key,at-17)
    ear.jobs.put(job('transcript',9.2));ear.jobs.join();assert len(heard)==1,'expired prefix authorised speech'
    ear.jobs.put(job('wake_probe',11.2));ear.jobs.join();ear.paused_until=float('inf')
    ear.jobs.put(job('transcript',11.2));ear.jobs.join();assert len(heard)==1,'mic off allowed a queued command'
finally:ear.stop=True;worker.join(2);ear.shutdown()
assert not worker.is_alive()
print('PREFIX ADDRESS: same-utterance name drop recovered, no early/unrestricted action, other/cancelled/unknown utterances refused')
