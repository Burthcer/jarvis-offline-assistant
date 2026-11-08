"""Real cue queue and play boundary, fake output only. Never opens a device."""
import os,sys,tempfile,threading,time,queue
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-cue-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.speaker import Speaker
speaker=Speaker();speaker.ready=True
speaker.v.sr=24000  # normally assigned by load(); this fixture never loads speech
assert speaker.cue('wake') is False,'silent tests queued real audio'
speaker.silent=False  # _play and output check are replaced before any cue is queued
entered=threading.Event();release=threading.Event();played=[];spoken=[];failures=[]
def play(audio,started=None,**kwargs):
    entered.set();assert release.wait(2)
    started.set();played.append(len(audio))
with patch.object(speaker.v,'_play',side_effect=play),patch.object(speaker,'output_available',return_value=True),patch.object(speaker.v,'speak',side_effect=spoken.append):
    assert speaker.cue('wake',lambda:played.append('started'),lambda:failures.append('failed'))
    assert entered.wait(1)
    speaker.speak('deferred answer');assert not spoken,'speech jumped ahead of the wake cue'
    release.set()
    end=time.monotonic()+2
    while not spoken and time.monotonic()<end:time.sleep(.01)
    assert spoken==['deferred answer'] and played[0]=='started' and not failures
with patch.object(speaker,'output_available',return_value=False):
    assert speaker.cue('success',lambda:failures.append('false start'),lambda:failures.append('muted'))
    end=time.monotonic()+1
    while not failures and time.monotonic()<end:time.sleep(.01)
    assert failures==['muted'],'muted output was falsely reported started'
speaker.shutdown();speaker.cue_thread.join(2)
assert not speaker.cue_thread.is_alive()
print('V3 CUE OUTPUT: silent guard, play-boundary timing, cue priority, mute refusal and worker shutdown PASSED')
