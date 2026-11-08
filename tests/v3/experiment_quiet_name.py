"""Saved quiet takes at lower and lower volume: where does the voice detector or Whisper lose the name?
Also tries boosting quiet segments before Whisper. Silent, saved audio only."""
import os,sys,json,wave,time
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from jarvis3.engine.ears import Transcriber,name_split,BLOCK,SR,THR
from jarvis3.engine.canceller import Canceller
with wave.open(str(ROOT/'data/gold/audio/quiet.wav')) as w:audio=np.frombuffer(w.readframes(w.getnframes()),np.int16)
takes=json.loads((ROOT/'data/gold/audio/session.json').read_text(encoding='utf-8'))['sections']['quiet']['takes']
stt=Transcriber();stt.load()
def boost(clip):
    peak=np.abs(clip).max()
    return clip if peak==0 or peak>=3000 else (clip.astype(np.float32)*(8000/peak)).astype(np.int16)   # quiet speech up to a normal level
def vad_max(clip):
    c=Canceller();best=0.0
    for i in range(0,len(clip)-BLOCK+1,BLOCK):
        _,probs=c.feed(clip[i:i+BLOCK],np.zeros(2*BLOCK,np.float32));best=max(best,float(max(probs)))
    return best
clips=[audio[round(t['start']*SR):round(t['end']*SR)] for t in takes]
named=[i for i,c in enumerate(clips) if name_split(stt(c,'Jarvis.'))[0]]
print(f'takes with the name at full volume: {len(named)} of {len(clips)}')
report=[]
for gain in (1.0,.5,.3,.2,.1,.05):
    vad_ok=vad_low=whisper_ok=boosted_ok=0
    for i in named:
        clip=(clips[i].astype(np.float32)*gain).astype(np.int16)
        v=vad_max(clip);vad_ok+=v>THR;vad_low+=v>.2
        whisper_ok+=name_split(stt(clip,'Jarvis.'))[0]
        boosted_ok+=name_split(stt(boost(clip),'Jarvis.'))[0]
    rms=int(np.sqrt(np.mean((clips[named[0]].astype(np.float32)*gain)**2)))
    row=dict(gain=gain,rms_first_take=rms,vad_passes_035=vad_ok,vad_passes_020=vad_low,whisper_name=whisper_ok,whisper_name_boosted=boosted_ok,of=len(named))
    report.append(row);print(row,flush=True)
(ROOT/'data/v3-dev-checks/quiet-name.json').write_text(json.dumps(report,indent=1),encoding='utf-8')
stt.unload();print('QUIET NAME EXPERIMENT DONE')
