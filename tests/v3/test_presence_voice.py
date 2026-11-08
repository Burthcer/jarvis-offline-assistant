"""Owner-voice gate, hands-free window and camera movement: silent, no mic/camera/playback.
Voice check uses the approved CPU ONNX export on the owner's saved recordings only."""
import json,os,sys,tempfile,time,wave
from pathlib import Path
import numpy as np
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
home=tempfile.mkdtemp(prefix='jarvis-v3-presence-');os.environ['JARVIS_V3_HOME']=home
from jarvis3.voice_gate import VoiceGate
from jarvis3.camera_presence import CameraPresence,motion

# ---- voice gate on saved recordings (never a mic) ----
gate=VoiceGate(profile=Path(home)/'voice_profile.json')
assert gate.available,'approved voice-check export missing under data/v3/lab/model'
assert gate.ready() and gate.profile_path.exists(),gate.error
with wave.open(str(ROOT/'data/gold/audio/quiet.wav')) as w:owner=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)
takes=json.loads((ROOT/'data/gold/audio/session.json').read_text(encoding='utf-8'))['sections']['quiet']['takes']
clip=lambda t:owner[round(t['start']*16000):round(t['end']*16000)]
t0=time.perf_counter();ok,score=gate.check(clip(takes[5]));ms=(time.perf_counter()-t0)*1000
assert ok and score>=.25,('owner rejected',score)
assert gate.check(clip(takes[5])[:8000]) is None,'under one second must pass unscored'
others=sorted((ROOT/'voice_samples').glob('*.wav'))[:3]
import soundfile as sf
for path in others:
    audio,rate=sf.read(str(path),dtype='float32')
    if audio.ndim>1:audio=audio.mean(axis=1)
    if rate!=16000:
        from scipy.signal import resample_poly;import math
        g=math.gcd(rate,16000);audio=resample_poly(audio,16000//g,rate//g)
    ok2,score2=gate.check(audio[:4*16000]*32768)
    assert not ok2,('other voice accepted',path.name,score2)
fresh=VoiceGate(profile=gate.profile_path);assert fresh.load_profile() and np.allclose(fresh.profile,gate.profile)
print(f'VOICE GATE: owner {score:.2f} accepted in {ms:.0f} ms, {len(others)} other voices rejected, profile reloads')

# ---- hands-free window attributes ----
from jarvis3.engine.ears import Ears
e=Ears.__new__(Ears);assert not e.hands_free_active(now=5.0)
e.hands_free_s=120;e.hands_free_until=100.0;assert e.hands_free_active(now=5.0) and not e.hands_free_active(now=100.0)
assert Ears.voice_gate is None and Ears.hands_free_s==0

# ---- camera state machine on synthetic frames ----
now=[1000.0];clock=lambda:now[0]
cam=CameraPresence(opener=lambda:None,clock=clock,interval=0,absent_after=600,confirm=2,prepare=lambda f:f)
still=np.full((120,160),100,np.uint8);moving=lambda k:np.roll(np.tile(np.arange(160,dtype=np.uint8),(120,1)),k*7,axis=1)
assert motion(still,still) is False and motion(None,still) is False and motion(moving(0),moving(1))
for _ in range(3):cam.observe(still);now[0]+=2
assert cam.present and not cam.take(),'startup must not greet'
now[0]+=700;cam.observe(still);assert not cam.present,'ten still minutes = absent'
cam.observe(moving(1));assert not cam.take(),'one moving frame is not yet an arrival'
cam.observe(moving(2));assert cam.present and cam.take() and not cam.take(),'arrival once, consumed'
cam.observe(moving(3));assert not cam.take(),'staying is not arriving again'
cam.start();time.sleep(.3);assert cam.status=='unavailable';cam.close();assert cam.status=='off'
class FakeCap:
    def __init__(s):s.n=0;s.released=False
    def read(s):s.n+=1;return True,(moving(s.n) if s.n%2 else still)
    def release(s):s.released=True
cap=FakeCap();live=CameraPresence(opener=lambda:cap,clock=time.monotonic,interval=.01,prepare=lambda f:f)
live.start();time.sleep(.3);assert live.status=='watching' and live.samples>5;live.close();assert cap.released and live.status=='off'
print('CAMERA: no startup greeting, absent after ten still minutes, one consumed arrival, unavailable/close paths')

# ---- settings keys ----
from jarvis3.engine import settings as s3
from jarvis3.legacy import settings as S
Path(S.PATH).parent.mkdir(parents=True,exist_ok=True)
Path(S.PATH).write_text(json.dumps({'only_my_voice':True,'camera_arrival':'yes','hands_free_minutes':900}),encoding='utf-8')
cfg=S.load();assert cfg['only_my_voice'] is True and cfg['camera_arrival'] is False and cfg['hands_free_minutes']==60
print('SETTINGS: new keys load with clamps; PRESENCE/VOICE ALL PASSED')

# ---- real ears decision path with a fake gate and the hands-free window ----
import threading
from jarvis3.engine.ears import Job,BLOCK
class STT:
    def __init__(s):s.text='Jarvis open notepad'
    def __call__(s,a,h):return s.text
    def again(s,a):return ''
class FakeGate:
    def __init__(s,ok):s.ok=ok;s.calls=0
    def check(s,audio):s.calls+=1;return (s.ok,.9 if s.ok else .05)
stt=STT();heard=[];foreign=[];ear=Ears(None,None,stt,heard.append);ear.on_wake=lambda e:None;ear.on_foreign=lambda t,sc:foreign.append((t,sc))
ear.is_complete=lambda t:True;ear.followup_filter=lambda t,**k:t=='pause'
def job(onset,seconds=1.0):
    j=Job(np.zeros(int(16000*seconds),np.int16),onset-.2,onset+seconds);j.voice_a=onset;j.final=True;j.final_at=time.monotonic();j.speech_end_wall=j.final_at;return j
worker=threading.Thread(target=ear._worker);worker.start()
try:
    ear.voice_gate=FakeGate(False);ear.jobs.put(job(1.0));ear.jobs.join()
    assert not heard and foreign==[('open notepad',.05)] and ear.stats['foreign']==1,'another voice must be ignored'
    ear.voice_gate=FakeGate(True);ear.jobs.put(job(3.0));ear.jobs.join()
    assert len(heard)==1 and heard[0].text=='open notepad' and ear.armed_until==0,'owner command must run; no window without hands-free'
    ear.voice_gate=None;ear.hands_free_s=120;ear.jobs.put(job(5.0));ear.jobs.join()
    assert len(heard)==2 and ear.hands_free_active() and ear.armed_until>time.monotonic()+100,'hands-free must arm after a command'
    stt.text='pause';ear.clock=8.0;ear.jobs.put(job(7.0));ear.jobs.join()
    assert len(heard)==3 and heard[2].text=='pause' and heard[2].trigger=='follow_up','known name-free command inside the window'
    stt.text='what do you think about that';ear.clock=10.0;ear.jobs.put(job(9.0));ear.jobs.join()
    assert len(heard)==3,'room talk inside the window must be ignored'
    from jarvis3.conversation import DISMISS
    ear.followup_filter=lambda t,**k:bool(DISMISS.fullmatch(t)) or t=='pause'
    for phrase in ('dismissed','let it go','never mind'):
        ear.arm(120,since=0);ear.hands_free_until=ear.armed_until
        stt.text=phrase;ear.jobs.put(job(10.0));ear.jobs.join()
        assert heard[-1].text==phrase and not ear.armed_until and not ear.hands_free_active(),'dismissal rearmed hands-free'
        count=len(heard);stt.text='pause';ear.jobs.put(job(11.0));ear.jobs.join()
        assert len(heard)==count,'name-free command survived dismissal'
    count=len(heard)
    ear.hands_free_s=0;ear.armed_until=0;stt.text='pause';ear.jobs.put(job(12.0));ear.jobs.join()
    assert len(heard)==count,'no window once hands-free is off'
finally:ear.stop=True;worker.join(2);ear.shutdown()
print('EARS: foreign voice ignored, owner runs, hands-free admits known commands only and closes when off')
