"""Capture retains pre-roll and does not commit at a brief natural pause."""
import os,sys,tempfile,time,threading
from unittest.mock import patch
from types import SimpleNamespace as NS
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-capture-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from jarvis3.engine.ears import Ears,Job,MicStream,BLOCK,SR

# Four quiet lead-in blocks, speech, a 0.512s pause, resumed speech, final silence.
levels=[False]*4+[True]*6+[False]*4+[True]*7+[False]*7
blocks=[np.full(BLOCK,1000+i,np.int16) for i in range(len(levels))]
class Mic:
    def __init__(self):self.i=0
    def read(self):
        time.sleep(.005)
        if self.i>=len(blocks):return None
        result=blocks[self.i];self.i+=1;return result
class Filter:
    cancelling=False
    def __init__(self):self.i=0
    def feed(self,x,ref):
        active=levels[self.i];self.i+=1
        return x,[1.0 if active else 0.0]
class STT:
    def __call__(self,a,hint):return 'Jarvis set a timer for ten minutes' if len(a)<BLOCK*20 else 'Jarvis set a timer for fifteen minutes'
    def again(self,a):return ''
heard=[];ear=Ears(Mic(),None,STT(),heard.append)
ear.canceller=Filter();ear.prefix_wake=False;ear.is_complete=lambda text:True
ear.start();ear.join(5);ear.shutdown()
for thread in ear.threads:thread.join(2)
assert len(heard)==1 and 'fifteen' in heard[0].text,[(h.text,h.started,h.ended) for h in heard]
assert heard[0].started<=4*BLOCK/SR,'lead-in was clipped'
assert not any(t.is_alive() for t in ear.threads)
print('V3 CAPTURE: pre-roll retained, 512ms pause did not prematurely commit, one full command delivered')

# A lost input stream is a boundary, not permission to join two separate clips.
# Otherwise an old wake before unplugging can authorise new room speech later.
class BrokenMic:
    def __init__(self):self.generation=1;self.items=iter([0]*4+[1000]*6+[OSError('owned fake input gap')]+[2000]*6+[0]*7)
    def read(self):
        item=next(self.items,None)
        if isinstance(item,Exception):self.generation+=1;raise item
        return None if item is None else np.full(BLOCK,item,np.int16)
class GapFilter:
    cancelling=False
    def feed(self,x,ref):return x,[float(bool(x[0]))]
    def reset(self):pass
class GapSTT:
    def __call__(self,a,hint):
        # Different marker values represent words either side of the gap.
        return 'Jarvis open notepad' if 1000 in a and 2000 in a else 'open notepad' if 2000 in a else 'Jarvis'
    def again(self,a):return ''
class GapReference:
    def __init__(self):self.syncs=0;self.requests=[]
    def sync(self):self.syncs+=1
    def get(self,start,n):self.requests.append((start,n));return np.zeros(n,np.float32)
reference=GapReference()
broken_heard=[];problems=[];ear=Ears(BrokenMic(),reference,GapSTT(),broken_heard.append)
ear.prefix_wake=False;ear.canceller=GapFilter();ear.on_problem=problems.append
with patch('jarvis3.engine.ears.time.sleep',lambda seconds:None):
    ear.start();ear.join(5);ear.shutdown()
assert not broken_heard,'speech on opposite sides of a microphone failure was stitched into a command'
assert len(problems)==1,'microphone failure was silently hidden from the app'
assert reference.syncs==2,'loopback clock kept its pre-gap origin after missing input time'
assert ear.capture_epoch==1,'read failure followed by a successful reopen invalidated the same gap twice'
ear.lag=400;ear._aligned_ref(12)
assert reference.requests[-1]==(BLOCK,2*BLOCK),'recovered loopback read used the old absolute sample clock'
ear.history.clear();ear.history.extend(np.zeros(BLOCK,np.int16) for _ in range(48));ear._find_lag(60)
assert reference.requests[-1]==(3*BLOCK,48*BLOCK),'delay estimation used a different recovered reference origin'
assert not any(t.is_alive() for t in ear.threads)
print('V3 CAPTURE: interrupted microphone clip is discarded, no stale wake crosses gap, one visible problem')

# A transcription already running when the input fails must also be revoked.
entered=threading.Event();release=threading.Event();late_heard=[];late_wakes=[];late_problems=[]
class OnceBroken:
    def __init__(self):self.n=0
    def read(self):
        self.n+=1
        if self.n<=2:raise OSError('owned repeated fake gap')
        return None
def delayed(a,h):
    entered.set();assert release.wait(2)
    return 'Jarvis open notepad'
ear=Ears(OnceBroken(),None,delayed,late_heard.append);ear.canceller=GapFilter()
ear.on_wake=late_wakes.append
ear.on_problem=lambda text:(late_problems.append(text),release.set())
old=Job(np.zeros(BLOCK,np.int16),0,1);old.final=True;old.final_at=time.monotonic()
ear.jobs.put(old);worker=threading.Thread(target=ear._worker);worker.start();assert entered.wait(2)
with patch('jarvis3.engine.ears.time.sleep',lambda seconds:None):ear._run()
ear.jobs.join();worker.join(2);ear.shutdown()
assert not late_heard and not late_wakes,'a pre-gap transcription delivered after recovery'
assert len(late_problems)==1,'one disconnected episode spammed repeated problems'
assert not worker.is_alive()
print('V3 CAPTURE: running pre-gap transcription revoked; repeated failures notify once')

# Even a quick off/on between blocks must discard an active pre-toggle clip.
class ToggleMic:
    def __init__(self):self.i=0
    def read(self):
        if self.i==10:ear.invalidate_capture()
        values=[0]*4+[1000]*6+[2000]*6+[0]*7
        if self.i>=len(values):return None
        result=np.full(BLOCK,values[self.i],np.int16);self.i+=1;return result
toggled=[];ear=Ears(ToggleMic(),None,GapSTT(),toggled.append);ear.prefix_wake=False;ear.canceller=GapFilter()
ear.start();ear.join(5);ear.shutdown()
assert not toggled,'quick microphone off/on joined a stale wake to later speech'
assert not any(t.is_alive() for t in ear.threads)
print('V3 CAPTURE: explicit microphone invalidation discards active clips even after fast off/on')

# PortAudio may reopen successfully on a new default input without throwing.
# That still separates the old microphone's words from the new one's words.
class SwappedMic:
    def __init__(self):self.i=0;self.generation=1
    def read(self):
        values=[0]*4+[1000]*6+[2000]*6+[0]*7
        if self.i>=len(values):return None
        if self.i==10:self.generation+=1
        result=np.full(BLOCK,values[self.i],np.int16);self.i+=1;return result
swapped=[];swap_problems=[];swap_ref=GapReference()
ear=Ears(SwappedMic(),swap_ref,GapSTT(),swapped.append);ear.prefix_wake=False;ear.canceller=GapFilter();ear.on_problem=swap_problems.append
ear.start();ear.join(5);ear.shutdown()
assert not swapped,'successful default-device reopen stitched different microphones into one command'
assert len(swap_problems)==1,'interrupted command at device change was silently lost'
assert swap_ref.syncs==2,'successful device change did not restart the loopback origin'
ear.lag=400;ear._aligned_ref(13)
assert swap_ref.requests[-1]==(BLOCK,2*BLOCK),'successful reopen used the old reference origin'
assert not any(t.is_alive() for t in ear.threads)
print('V3 CAPTURE: successful default-device swap revokes old audio and asks once to repeat')

# A switch while idle must retain the first block of a fresh named command.
class IdleSwap:
    def __init__(self):self.i=0;self.generation=1
    def read(self):
        values=[0]*4+[3000]+[2000]*5+[0]*7
        if self.i>=len(values):return None
        if self.i==4:self.generation+=1
        result=np.full(BLOCK,values[self.i],np.int16);self.i+=1;return result
class NewDeviceSTT:
    def __call__(self,a,h):return 'Jarvis open notepad' if 3000 in a else 'open notepad'
    def again(self,a):return ''
fresh=[];idle_problems=[];ear=Ears(IdleSwap(),None,NewDeviceSTT(),fresh.append)
ear.prefix_wake=False;ear.canceller=GapFilter();ear.on_problem=idle_problems.append
ear.start();ear.join(5);ear.shutdown()
assert len(fresh)==1 and fresh[0].text=='open notepad','idle device change clipped the new command beginning'
assert fresh[0].capture_epoch==ear.capture_epoch==1 and not idle_problems
assert not any(t.is_alive() for t in ear.threads)

# Exercise the real source's generation accounting with an injected no-device
# PortAudio facade: only a successfully started stream advances its identity.
class OwnedStream:
    def __init__(self,fail=False):self.fail=fail;self.closed=False
    def start(self):
        if self.fail:raise OSError('owned fake open failure')
    def close(self):self.closed=True
made=[];fail=[False]
def stream(**kwargs):
    value=OwnedStream(fail[0]);made.append(value);return value
source=MicStream.__new__(MicStream);source.s=None;source.before=lambda:None;source.generation=0
sound=NS(InputStream=stream,query_devices=lambda **k:{'name':'owned fake microphone'})
with patch.dict(sys.modules,{'sounddevice':sound}):
    source._open_stream(False);assert source.generation==1
    fail[0]=True
    try:source._open_stream(False);raise AssertionError('fake failed stream started')
    except OSError:pass
    assert source.generation==1,'failed stream start advanced device identity'
for item in made:item.close()
assert all(item.closed for item in made)
print('V3 CAPTURE: idle swap keeps first word; source generation advances only after a successful fake start')

# An optional second decode must not erase a valid primary decode for this
# exact prefix-confirmed capture just because the fallback model call fails.
class RetryFailure:
    def __call__(self,a,h):return 'Jarvis open' if len(a)==BLOCK else 'open notepad'
    def again(self,a):raise RuntimeError('owned fake second-decode failure')
fallback_heard=[];ear=Ears(None,None,RetryFailure(),fallback_heard.append);ear.is_complete=lambda t:t=='open notepad'
probe=Job(np.zeros(BLOCK,np.int16),1,2);probe.voice_a=1.2;probe.kind='wake_probe'
final=Job(np.zeros(SR,np.int16),1,2);final.voice_a=1.2;final.final=True;final.final_at=time.monotonic()
ear.jobs.put(probe);ear.jobs.put(final);worker=threading.Thread(target=ear._worker);worker.start();ear.jobs.join()
ear.stop=True;worker.join(2);ear.shutdown()
assert len(fallback_heard)==1 and fallback_heard[0].text=='open notepad','failed optional decode erased valid primary speech'
assert not worker.is_alive()
print('V3 CAPTURE: failed optional retry retains valid primary decode for exact addressed capture')

# Once wake has been acknowledged, a real decode failure must be exposed as
# failure, not quietly disappear or emit an empty command/success.
class PrimaryFailure:
    def __call__(self,a,h):
        if len(a)==BLOCK:return 'Jarvis open'
        raise RuntimeError('owned fake primary-decode failure')
failed_heard=[];failed_problems=[];ear=Ears(None,None,PrimaryFailure(),failed_heard.append);ear.on_problem=failed_problems.append
probe=Job(np.zeros(BLOCK,np.int16),1,2);probe.voice_a=1.2;probe.kind='wake_probe'
final=Job(np.zeros(SR,np.int16),1,2);final.voice_a=1.2;final.final=True;final.final_at=time.monotonic()
ear.jobs.put(probe);ear.jobs.put(final);worker=threading.Thread(target=ear._worker);worker.start();ear.jobs.join()
ear._decide(final)  # repeated delivery/check cannot repeat the failure notice
ear.stop=True;worker.join(2);ear.shutdown()
assert not failed_heard and len(failed_problems)==1,'addressed primary decode failure silently disappeared or notified twice'
assert not worker.is_alive()
print('V3 CAPTURE: acknowledged wake plus failed primary decode reports once and performs no action')

scoped=[];ear=Ears(None,None,None,lambda h:(_ for _ in ()).throw(AssertionError('failed speech executed')));ear.on_problem=scoped.append
def failed_job(onset):
    item=Job(np.zeros(BLOCK,np.int16),onset,onset+.5);item.voice_a=onset;item.stt_failed=True;return item
ear._decide(failed_job(1));assert not scoped,'unaddressed background decode error produced a request failure'
ear.arm(since=2);eligible=failed_job(2.1);ear._decide(eligible);ear._decide(eligible)
assert len(scoped)==1,'eligible failed followup was hidden or repeated'
old=failed_job(2.2);ear.invalidate_capture();ear._decide(old)
assert len(scoped)==1,'cancelled old speech produced a failure after mic off'
ear.shutdown()
print('V3 CAPTURE: failure notice limited to addressed/eligible live captures, never stale/background jobs')

retries=[]
class ClosingSTT:
    def __call__(self,a,h):ear.cancel_output.set();return 'open notepad'
    def again(self,a):retries.append(True);return 'Jarvis open notepad'
ear=Ears(None,None,ClosingSTT(),lambda h:(_ for _ in ()).throw(AssertionError('closed speech delivered')))
item=Job(np.zeros(SR,np.int16),1,2);item.final=True;item.final_at=time.monotonic();ear.jobs.put(item)
worker=threading.Thread(target=ear._worker);worker.start();ear.jobs.join();ear.stop=True;worker.join(2);ear.shutdown()
assert not retries,'shutdown launched an unnecessary second model decode after the active decode returned'
assert not worker.is_alive()
print('V3 CAPTURE: shutdown never starts optional second decode after in-flight recognition returns')

# A delayed reply belongs to the question active at speech onset, not whichever
# question happens to be current when its transcription eventually completes.
generation=[11];generation_reads=[];stamped=[];session_heard=[]
class SessionMic:
    def __init__(self):self.i=0
    def read(self):
        values=[0]*4+[1000]*6+[0]*7+[2000]*6+[0]*7
        if self.i>=len(values):return None
        if self.i==8:generation[0]=12
        result=np.full(BLOCK,values[self.i],np.int16);self.i+=1;return result
class SessionSTT:
    def __call__(self,a,h):return 'Jarvis open notepad' if 1000 in a else 'Jarvis open chrome'
    def again(self,a):return ''
ear=Ears(SessionMic(),None,SessionSTT(),session_heard.append);ear.canceller=GapFilter()
def session():generation_reads.append(generation[0]);return generation[0]
ear.conversation_generation=session;original_submit=ear._submit
def tagged(*args,**kwargs):
    item=original_submit(*args,**kwargs);stamped.append(item.conversation_generation);return item
ear._submit=tagged;ear.start();ear.join(5);ear.shutdown()
assert [h.conversation_generation for h in session_heard]==[11,12],'speech inherited the question current at final decoding instead of onset'
assert generation_reads==[11,12],'conversation identity was not captured exactly once per speech onset'
assert stamped and set(stamped)=={11,12},'prefix/early/final jobs did not retain captured question identity'
assert not any(t.is_alive() for t in ear.threads)
print('V3 CAPTURE: question identity stamped at true speech onset, retained through prefix/early/final delivery')
