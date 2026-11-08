"""Saved audio through unchanged Whisper; real-time fake mic, no speakers/PC effects."""
import os,sys,tempfile,time,threading,wave,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-replay-')
import numpy as np
import psutil
from jarvis3.engine.ears import Ears,Transcriber,ArraySource,SR,BLOCK_S
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
def read(path):
    with wave.open(str(path)) as f:
        assert f.getframerate()==SR
        return np.frombuffer(f.readframes(f.getnframes()),np.int16)
def gpu():return subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu','--format=csv,noheader,nounits'],text=True).strip()
stt=Transcriber();ear=None
try:
    stt.load()
    wake=read(ROOT/'data/feedback-audio/wake.wav');full=read(ROOT/'data/feedback-audio/command.wav')
    segments,_=stt.model.transcribe(full.astype(np.float32)/32768,language='en',beam_size=1,word_timestamps=True)
    words=[w for s in segments for w in (s.words or [])]
    start=next(w.start for w in words if re.sub(r'\W','',w.word).lower()=='open')
    command=full[max(0,int((start-.06)*SR)):]
    for gap in (.8,1.6):
        store=Store(':memory:');pc=Fake();app=App(pc,store,None,natural=False)
        source=ArraySource(np.concatenate([np.zeros(SR//2,np.int16),wake,np.zeros(int(gap*SR),np.int16),command,np.zeros(2*SR,np.int16)]))
        original=source.read
        def slow():time.sleep(BLOCK_S);return original()
        source.read=slow
        got=[];signals=[]
        def heard(h):
            got.append(h)
            if h.text:
                reply=app.handle(h.text,h.trigger)
                print('gap',gap,'trigger',h.trigger,'delivery_ms',h.wait_ms,'ok',reply.ok,flush=True)
        ear=Ears(source,None,stt,heard,hint=app.names.hint);ear.on_wake=signals.append;ear.is_complete=app.is_complete
        ear.start();ear.join(35);ear.shutdown()
        for thread in ear.threads:thread.join(3)
        assert len([h for h in got if h.text])==1 and any(h.trigger=='follow_up' and h.text for h in got),[(h.text,h.trigger) for h in got]
        assert pc.log.count(('open','youtube','site',1,None))==1,pc.log
        print('Wake signals',len(signals),'early',sum(s['source']=='wake_probe' for s in signals),'GPU MiB/C',gpu(),flush=True)
        store.db.close();app.memory.db.close()
    print('V3 RECORDED FIRST-ATTEMPT FOLLOW-UP PASSED; RAM MB',round(psutil.Process().memory_info().rss/2**20),flush=True)
finally:
    if ear:ear.shutdown()
    stt.unload()
