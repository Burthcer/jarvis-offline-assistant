"""Approved offline lab evaluation. Read saved clips; never record/play/export a profile."""
import os,sys,time,json,statistics,math,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
os.environ['JARVIS_SILENT']='1';os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['HF_HUB_OFFLINE']='1'
os.environ['HF_HOME']=str(ROOT/'data/v3/lab/cache')
# Reuse existing ABI-compatible torch/torchaudio read-only; no huge extra download.
sys.path.append(r'C:\Users\USER\Desktop\Wisperno-pro\.venv\Lib\site-packages')
use_onnx='--onnx' in sys.argv
if not use_onnx:
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
import numpy as np
import soundfile as sf
import psutil
from scipy.signal import resample_poly
from jarvis3.lab.voice_check import VoiceCheck
LAB=ROOT/'data/v3/lab';started=time.perf_counter()
if use_onnx:
    from jarvis3.lab.voice_check_onnx import OnnxVoiceCheck
    model=OnnxVoiceCheck(LAB/'model')
else:model=VoiceCheck(LAB/'model')
def read(path):
    audio,rate=sf.read(str(path),dtype='float32')
    if audio.ndim>1:audio=audio.mean(axis=1)
    if rate!=16000:
        g=math.gcd(rate,16000);audio=resample_poly(audio,16000//g,rate//g)
    return audio
data=json.loads((ROOT/'data/gold/audio/session.json').read_text(encoding='utf-8'))['sections']
quiet=read(ROOT/'data/gold/audio/quiet.wav')
enrollment=data['quiet']['takes'][:3]
model.enroll([quiet[round(t['start']*16000):round(t['end']*16000)] for t in enrollment])
threshold=.25  # fixed official verification example default; no tuning on holdout
rows=[];times=[]
for condition in ('quiet','music','earphones'):
    source=quiet if condition=='quiet' else read(ROOT/f'data/gold/audio/{condition}.wav')
    takes=data[condition]['takes'][3:] if condition=='quiet' else data[condition]['takes']
    for take in takes:
        clip=source[round(take['start']*16000):round(take['end']*16000)]
        t=time.perf_counter();score=model.score(clip);times.append((time.perf_counter()-t)*1000)
        rows.append({'condition':condition,'clip':take['id'],'owner':True,'score':score})
        time.sleep(.025)
    print(condition,'accepted',sum(r['score'] is not None and r['score']>=threshold for r in rows if r['condition']==condition),'of',len(takes),flush=True)
foreign=[]
for path in sorted((ROOT/'voice_samples').glob('*.wav'))[:12]:
    audio=read(path)[:4*16000]
    score=model.score(audio)
    rows.append({'condition':'other synthetic voice','clip':path.name,'owner':False,'score':score})
    foreign.append(audio)
negative=[r for r in rows if not r['owner']]
print('Other synthetic voices accepted',sum(r['score'] is not None and r['score']>=threshold for r in negative),'of',len(negative),flush=True)
# Mixed-speaker scores demonstrate why identity alone does not remove phone words.
mixtures=[]
take=data['quiet']['takes'][4];own=quiet[round(take['start']*16000):round(take['end']*16000)]
other=np.resize(foreign[0],len(own));own=own/(np.sqrt(np.mean(own**2))+1e-8);other=other/(np.sqrt(np.mean(other**2))+1e-8)
for snr in (10,0,-10):
    mixed=own+other*10**(-snr/20);mixed=mixed/(np.max(np.abs(mixed))+1e-8)*.6
    mixtures.append({'owner_to_other_db':snr,'score':model.score(mixed)})
result={'model':'speechbrain/spkrec-ecapa-voxceleb','enabled_in_assistant':False,'threshold':threshold,'enrollment_clips':3,'profile_saved':False,'evaluation':rows,'mixtures':mixtures,
        'median_ms':round(statistics.median(times),1),'p95_ms':round(sorted(times)[int(len(times)*.95)],1),'ram_mb':round(psutil.Process().memory_info().rss/2**20),'elapsed_s':round(time.perf_counter()-started,1),'cuda_visible':False if use_onnx else torch.cuda.is_available(),
        'model_devices':model.session.get_providers() if use_onnx else sorted({str(p.device) for p in model.model.parameters()}),'cuda_initialized':False if use_onnx else torch.cuda.is_initialized(),'cuda_allocated_bytes':0 if use_onnx else torch.cuda.memory_allocated(),
        'limitations':['Not a phone-room trial. Synthetic voices are not population false-accept statistics.','No actual tired-voice trial. Owner voice presence does not separate overlapping words.','Short wake-only clips are not accepted as enough identity evidence.','No voice profile saved, no automatic runtime enablement.']}
folder=LAB/'results';folder.mkdir(exist_ok=True)
if use_onnx:
    previous=json.loads((folder/'cpu_voice_check.json').read_text(encoding='utf-8'))
    pairs=list(zip(previous['evaluation'],rows));errors=[abs(a['score']-b['score']) for a,b in pairs if a['score'] is not None and b['score'] is not None]
    assert len(previous['evaluation'])==len(rows) and all(a['clip']==b['clip'] and (a['score'] is not None and a['score']>=threshold)==(b['score'] is not None and b['score']>=threshold) for a,b in pairs),'Voice-check decisions changed'
    assert max(errors)<.001,('Score drift',max(errors))
    result['max_score_difference']=max(errors);result['decision_parity']=True
(folder/('cpu_voice_check_onnx.json' if use_onnx else 'cpu_voice_check.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
print({k:result[k] for k in ('median_ms','p95_ms','ram_mb','elapsed_s','cuda_visible')},flush=True)
print('Mixture scores',mixtures,flush=True)
assert not result['cuda_visible'] and not result['cuda_allocated_bytes'],'Lab unexpectedly used/exposed a GPU'
