"""Silent A/B of post-idle eager AI warm-up, unchanged models and saved audio.

No live mic/audio/window/apps/clipboard/accounts. No production changes.
Run only through run_model_check.py after its coordinator grants model access.
"""
import json,os,queue,re,subprocess,sys,tempfile,threading,time,wave
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
os.environ['JARVIS_SILENT']='1'
HOME=tempfile.TemporaryDirectory(prefix='v3-owned-prewarm-');os.environ['JARVIS_V3_HOME']=HOME.name
from jarvis3.paths import enter
enter()
import numpy as np
import psutil
from jarvis3.engine import ui
from jarvis3.engine.ears import Ears,Transcriber,ArraySource,SR,BLOCK_S
from jarvis3.engine.osapi import Fake
from jarvis3.engine.memory import Memory
from jarvis3.legacy.store import Store
from jarvis3.control import CANCEL_INFERENCE

WAKE_ONLY='--wake-only' in sys.argv
REPORT=ROOT/('data/v3-dev-checks/prewarm-wake-only.json' if WAKE_ONLY else 'data/v3-dev-checks/prewarm-experiment.json')

def read(path):
    with wave.open(str(path)) as f:
        assert f.getframerate()==SR and f.getnchannels()==1 and f.getsampwidth()==2
        return np.frombuffer(f.readframes(f.getnframes()),np.int16)

class Resources:
    def __init__(self):
        self.stop=threading.Event();self.samples=[];self.error=None
        self.thread=threading.Thread(target=self.run,daemon=True)
    def run(self):
        while not self.stop.is_set():
            try:
                value=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu','--format=csv,noheader,nounits'],text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=3).strip().split(',')
                sample={'at':time.monotonic(),'vram_mib':int(value[0]),'temperature_c':int(value[1]),'rss_mb':round(psutil.Process().memory_info().rss/2**20)}
                self.samples.append(sample)
                if sample['vram_mib']>4096 or sample['temperature_c']>=78:self.error='Resource/temperature bound reached';return
            except Exception as error:self.error=str(error);return
            self.stop.wait(.5)
    def check(self):
        if self.error:raise RuntimeError(self.error)
    def summary(self,since=0):
        rows=[s for s in self.samples if s['at']>=since]
        return {k:max((s[k] for s in rows),default=None) for k in ('vram_mib','temperature_c','rss_mb')}

def trial(stt,audio,mode,scenario,monitor):
    CANCEL_INFERENCE.clear();app=None;ear=None;loads=[];errors=[];heard=[];wakes=[];actions=[]
    started=time.monotonic()
    # Constructor paths remain real except all PC/data/account surfaces and boot.
    with patch.object(ui,'Real',Fake),patch.object(ui,'Store',lambda *a,**k:Store(':memory:')),patch.object(ui,'Memory',lambda *a,**k:Memory(':memory:')),patch.object(ui.settings,'set_autostart',lambda on:None),patch.object(ui.UiApp,'_boot',lambda self:None),patch('jarvis3.engine.google_connection.GoogleConnection',lambda:SimpleNamespace()):
        app=ui.UiApp(gui=False,tray=False)
    try:
        app.cfg.update(cool_mode=False,natural_replies=False,conversation_followups=False,arrival_greeting=False,audible_cues=False,speak_replies=False)
        app.booting=False;app.engine.natural=False;app.voice.talk=False;app.voice.listening=True;app._warming=threading.Lock()
        real_load=app.engine.ai.load
        def measured_load():
            event={'start':time.monotonic()};loads.append(event)
            try:real_load()
            except Exception as error:errors.append(str(error));raise
            finally:event['end']=time.monotonic()
        app.engine.ai.load=measured_load
        # Keep historical comparisons reproducible after production policy
        # changes. Wake-only uses the current UiApp implementation unchanged.
        if mode=='no_prewarm':app._warm_ai=lambda *a,**k:None
        elif mode=='eager':
            def historical_warm(state,event=None):
                if app._closing.is_set() or app.cfg.get('cool_mode') or state!='hearing' or app.engine.ai.loaded or not app._warming.acquire(blocking=False):return
                def warm():
                    try:app.engine.ai.load()
                    finally:app._warming.release()
                threading.Thread(target=warm,daemon=True).start()
            app._warm_ai=historical_warm
        assert not app.engine.ai.loaded,'Trial did not start post-idle/cold action model'
        source=ArraySource(audio);original=source.read
        def realtime():time.sleep(BLOCK_S);return original()
        source.read=realtime
        def delivered(h):
            heard.append({'text':h.text,'trigger':h.trigger,'delivery_ms':h.wait_ms,'stt_ms':h.stt_ms,'at':time.monotonic()})
            app._heard(h)
        ear=Ears(source,None,stt,delivered,hint=lambda:app.engine.names.hint())
        app.voice.ears=ear;ear.is_complete=app.engine.is_complete
        ear.conversation_generation=lambda:app.conversation.generation
        def wake(event):
            wakes.append(event);app._wake(event)
        ear.on_wake=wake
        def state(value):
            if mode=='eager':app._warm_ai(value)
        ear.on_state=state
        ear.start();deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            monitor.check()
            try:
                message=app.q.get(timeout=.01)
                assert isinstance(message,tuple),'Unexpected UI control message'
                app._voice_msg(*message)
            except queue.Empty:pass
            if app.engine.os.log and not actions:
                actions.append(time.monotonic())
            if not ear.threads[-1].is_alive() and ear.jobs.unfinished_tasks==0 and app.q.empty():break
        else:raise AssertionError('Recorded trial exceeded its time bound')
        assert not errors,errors
        if scenario=='wake_command':
            assert app.engine.os.log==[('open','youtube','site',1,None)],app.engine.os.log
            assert len([h for h in heard if h['text']])==1,heard
        else:
            assert not app.engine.os.log and not [h for h in heard if h['text']],(app.engine.os.log,heard)
        command=next((h for h in heard if h['text']),None)
        result={'mode':mode,'scenario':scenario,'actions':len(app.engine.os.log),'commands':len([h for h in heard if h['text']]),'wake_signals':len(wakes),'delivery_ms':command['delivery_ms'] if command else None,'end_to_fake_action_ms':round(command['delivery_ms']+1000*(actions[0]-command['at'])) if command and actions else None,'load_attempts':len(loads),'load_ms':[round(1000*(e['end']-e['start'])) for e in loads if 'end' in e],'ai_loaded_after':app.engine.ai.loaded,'resource_peak':monitor.summary(started)}
        return result
    finally:
        if ear:
            ear.shutdown()
            for thread in ear.threads:thread.join(3)
            assert not any(t.is_alive() for t in ear.threads),'Owned capture thread remains'
        if app:
            app._closing.set()
            assert app._warming.acquire(timeout=30),'AI warm thread did not finish'
            app._warming.release()
            app.engine.ai.unload();app.engine.chat_ai.unload()
            app.store.db.close();app.engine.memory.db.close()

stt=Transcriber();monitor=Resources();results=[]
try:
    monitor.thread.start();stt.load();monitor.check()
    wake=read(ROOT/'data/feedback-audio/wake.wav');full=read(ROOT/'data/feedback-audio/command.wav')
    segments,_=stt.model.transcribe(full.astype(np.float32)/32768,language='en',beam_size=1,word_timestamps=True)
    words=[w for s in segments for w in (s.words or [])]
    start=next(w.start for w in words if re.sub(r'\W','',w.word).lower()=='open')
    command=full[max(0,int((start-.06)*SR)):]
    positive=np.concatenate([np.zeros(SR//2,np.int16),wake,np.zeros(int(.8*SR),np.int16),command,np.zeros(8*SR,np.int16)])
    negative=np.concatenate([np.zeros(SR//2,np.int16),command,np.zeros(8*SR,np.int16)])
    for mode in (('wake_only','wake_only') if WAKE_ONLY else ('eager','no_prewarm','no_prewarm','eager')):
        result=trial(stt,positive,mode,'wake_command',monitor);results.append(result);print(json.dumps(result),flush=True)
    for mode in (('wake_only',) if WAKE_ONLY else ('eager','no_prewarm')):
        result=trial(stt,negative,mode,'unaddressed_owner_command_crop',monitor);results.append(result);print(json.dumps(result),flush=True)
    monitor.check()
finally:
    stt.unload();monitor.stop.set()
    if monitor.thread.ident:monitor.thread.join(4)
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps({'status':'complete' if len(results)==(3 if WAKE_ONLY else 6) else 'incomplete','trials':results,'resource_peak':monitor.summary(),'negative_limit':'Saved owner command cropped to omit wake; not a phone, overlapping-voice or natural-room acceptance sample.'},indent=2),encoding='utf-8')
    os.chdir(ROOT);HOME.cleanup()
    print('Owned model/capture experiment closed. Report:',REPORT,flush=True)
