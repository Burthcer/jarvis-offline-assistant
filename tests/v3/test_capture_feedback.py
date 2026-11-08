"""Accepted wake-prefix visual feedback through real UI/pill interfaces.

No sound, models, microphone, native windows or PC actions. Prefixes still do
not execute commands or grant a name-free listening window.
"""
import os,sys,tempfile,contextlib,threading,time
from types import SimpleNamespace as NS
from pathlib import Path
from unittest.mock import patch
import numpy as np
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='v3-capture-feedback-') as home,contextlib.ExitStack() as cleanup:
    os.environ['JARVIS_V3_HOME']=home
    from jarvis3.paths import enter
    enter();cleanup.callback(os.chdir,ROOT)
    from jarvis3.engine import ui
    from jarvis3.engine.osapi import Fake
    from jarvis3.engine.ears import Ears,Job,BLOCK

    class NoAI:
        loaded=True
        def complete(self,*a,**k):return 'ASK: Which app, sir?'
        def unload(self):pass
    class Pill:
        def __init__(self):self.states=[]
        def set_panel(self,*args):pass
        def show(self,state,*args,**kwargs):self.states.append(state)

    with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None):
        app=ui.UiApp(gui=False,tray=False);heard=[];ear=Ears(None,None,lambda a,h:'Jarvis open notepad',heard.append)
        app.voice.ears=ear;app.booting=False;app.island=Pill();app.feedback.send=lambda *a:False
        ear.on_wake=app._wake;ear.on_state=app._warm_ai
        def prefix(onset=1.2):
            item=Job(np.zeros(BLOCK,np.int16),onset-.2,onset+1)
            item.voice_a=onset;item.kind='wake_probe';item.capture_epoch=ear.capture_epoch
            item.conversation_generation=app.conversation.generation
            ear.jobs.put(item);ear.jobs.join()
        def pump():
            while not app.q.empty():
                event=app.q.get_nowait()
                if isinstance(event,tuple):app._voice_msg(*event)
        worker=threading.Thread(target=ear._worker);worker.start()
        try:
            ear._capture_begin(1.2,app.conversation.generation)
            ear.on_state('hearing');app._render()
            assert app.snapshot()['state']=='idle','unaddressed voice activity was presented as an accepted command'
            prefix();pump()
            assert not heard and not app.engine.os.log and not ear.armed_until,'visual capture feedback granted early action/listening authority'
            visual=(app.snapshot()['state'],app.island.states[-1])
            assert visual==('listening','listening'),f'accepted wake prefix kept main/pill {visual!r} while recording the command'
            app.state_name='speaking';app.text='A reply';app.voice.speaker=NS(busy=True)
            app._render();assert app.snapshot()['state']=='speaking' and app.island.states[-1]=='speaking','capture hid actual speaking'
            app.voice.speaker.busy=False;app._render()
            assert app.snapshot()['state']=='listening' and app.island.states[-1]=='listening','finished speech label masked fresh recording'
            app.state_name='thinking';app._render();assert app.snapshot()['state']=='thinking','capture hid actual task execution'
            app.state_name='idle';app.text='';app.voice.speaker=None
            ear._capture_phase(1.2,'decoding');app._render()
            assert app.snapshot()['state']=='thinking' and app.island.states[-1]=='thinking','accepted final decoding looked idle'
            final=Job(np.zeros(BLOCK,np.int16),1,2);final.voice_a=1.2;final.text='Jarvis open notepad';final.final_at=time.monotonic()
            final.conversation_generation=app.conversation.generation
            ear._decide(final);app._render()
            assert len(heard)==1 and app.snapshot()['state']=='idle' and not ear.capture_feedback(),'final result did not clear capture feedback'
            ear._capture_begin(3.2,app.conversation.generation);prefix(3.2)
            ear._capture_begin(4.2,app.conversation.generation);before=app.note;pump();app._render()
            assert app.snapshot()['state']=='idle' and app.note==before,'old queued wake lit a different unaddressed utterance'
            ear._capture_begin(5.2,app.conversation.generation);prefix(5.2)
            app.voice.set_listening(False);app.voice.set_listening(True);before=app.note;pump();app._render()
            assert app.snapshot()['state']=='idle' and app.note==before,'old queued wake survived microphone off/on'
            ear._capture_begin(7.2,app.conversation.generation);prefix(7.2);pump()
            ignored=Job(np.zeros(BLOCK,np.int16),7,8);ignored.voice_a=7.2;ignored.text='unrecognised room text';ignored.capture_epoch=ear.capture_epoch
            ignored.conversation_generation=app.conversation.generation;ignored.final_at=time.monotonic()
            ear._decide(ignored);app._render()
            assert app.snapshot()['state']=='idle' and not ear.capture_feedback(),'ignored final text left a listening animation stuck'
            ear._capture_begin(8.2,app.conversation.generation);prefix(8.2);pump()
            ear._capture_finish(ignored);app._render()
            assert app.snapshot()['state']=='listening','old final cleanup hid a newer accepted capture'
            app.conversation.dismiss();app._render()
            assert app.snapshot()['state']=='idle','dismissed capture still looked active'
            assert not app.engine.os.log and not ear.armed_until,'visual state changed action/listening authority'
            print('CAPTURE FEEDBACK: accepted prefix shows listening in main and pill, without early action or free listening')
        finally:
            ear.stop=True;worker.join(2);ear.shutdown();assert not worker.is_alive()

        # Real capture-loop integration with scripted blocks held mid-sentence
        # and a fake delayed final decoder. No direct visual-state calls here.
        class Mic:
            def __init__(self):
                self.i=0;self.continue_speech=threading.Event();self.ended=threading.Event();self.closed=threading.Event()
            def read(self):
                values=[0]*4+[1000]*12+[0]*7
                if self.i==9:assert self.continue_speech.wait(4)
                if self.i>=len(values):self.ended.set();self.closed.wait(4);return None
                block=np.full(BLOCK,values[self.i],np.int16);self.i+=1;return block
            def close(self):self.continue_speech.set();self.closed.set()
        class Filter:
            cancelling=False
            def feed(self,x,ref):return x,[float(bool(x[0]))]
        class STT:
            def __init__(self):self.decoding=threading.Event();self.release=threading.Event()
            def __call__(self,a,h):
                if len(a)>=16*BLOCK:self.decoding.set();assert self.release.wait(4)
                return 'Jarvis open notepad'
            def again(self,a):return ''
        mic=Mic();stt=STT();accepted=threading.Event();delivered=threading.Event()
        run=Ears(mic,None,stt,lambda h:delivered.set());run.canceller=Filter();app.voice.ears=run
        run.conversation_generation=lambda:app.conversation.generation
        run.on_wake=lambda event:(app._wake(event),accepted.set())
        run.on_state=app._warm_ai;app.state_name='idle';app.text='';app.voice.speaker=None
        try:
            run.start();assert accepted.wait(4);pump();app._render()
            assert app.snapshot()['state']=='listening' and app.island.states[-1]=='listening','real capture loop did not show active recording'
            mic.continue_speech.set();assert mic.ended.wait(4) and stt.decoding.wait(4);app._render()
            assert app.snapshot()['state']=='thinking' and app.island.states[-1]=='thinking','real capture end did not show final decoding'
            stt.release.set();assert delivered.wait(4);run.jobs.join();app._render()
            assert app.snapshot()['state']=='idle' and not run.capture_feedback() and not app.engine.os.log
            print('CAPTURE FEEDBACK: real scripted capture transitions recording -> decoding -> cleared; stale/other/mic-off/state-priority cases passed')
        finally:
            stt.release.set();run.shutdown();assert not any(t.is_alive() for t in run.threads)
            app._stop_arrival_watch();app.store.db.close();app.engine.memory.db.close()
