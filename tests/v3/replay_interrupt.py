"""Current TTS -> memory -> current Whisper/real capture flow. No live device/output."""
import os,sys,tempfile,time,subprocess,json
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-interrupt-replay-')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy.signal import resample_poly
import psutil
from jarvis3.engine.speaker import Speaker
from jarvis3.engine.ears import Ears,Transcriber,ArraySource,SR,BLOCK_S
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
speaker=Speaker();stt=Transcriber();ear=None;store=Store(':memory:');pc=Fake();app=App(pc,store,None,natural=False)
try:
    speaker.v._load_tts()
    audio=speaker.v._synth('Stop talking. Actually, open Notepad.')
    audio=np.clip(resample_poly(audio,SR,speaker.v.sr)*32767,-32768,32767).astype(np.int16)
    stt.load()
    stream=ArraySource(np.concatenate([np.zeros(SR//2,np.int16),audio,np.zeros(2*SR,np.int16)]))
    original=stream.read
    def realtime():time.sleep(BLOCK_S);return original()
    stream.read=realtime;busy=[True];events=[];heard=[];wake=[]
    def interrupted(event):
        assert not pc.log,'PC action ran before complete capture'
        busy[0]=False;events.append(event)
    def command(h):
        heard.append(h)
        if h.text:assert app.handle(h.text,h.trigger).ok,(h.text,h.trigger)
    ear=Ears(stream,None,stt,command,hint=app.names.hint)
    ear.prefix_wake=False;ear.can_interrupt=lambda:busy[0];ear.on_interrupt=interrupted;ear.is_complete=app.is_complete;ear.on_wake=wake.append
    started=time.perf_counter();ear.start();ear.join(30);ear.shutdown()
    for t in ear.threads:t.join(3)
    assert len(events)==1 and not wake,'No single unnamed early stop'
    assert events[0]['detected_at']-started<.5+len(audio)/SR,'Interruption waited for the complete sentence'
    assert len(heard)==1 and heard[0].text.lower().strip(' .!')=='open notepad',[(h.text,h.trigger) for h in heard]
    assert pc.log==[('open','notepad','app',1,None)],pc.log
    result={'synthetic_audio_s':round(len(audio)/SR,2),'prefix_from_audio_start_ms':round((events[0]['detected_at']-started-.5)*1000),'full_command_end_to_delivery_ms':heard[0].wait_ms,'ram_mb':round(psutil.Process().memory_info().rss/2**20),'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu','--format=csv,noheader'],text=True).strip()}
    (ROOT/'data/v3-dev-checks/interrupt-replay.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('SYNTHETIC SILENT INTERRUPTION passed',result,flush=True)
finally:
    if ear:ear.shutdown()
    stt.unload();speaker.shutdown();store.db.close();app.memory.db.close()
