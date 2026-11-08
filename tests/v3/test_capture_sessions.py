"""Threaded fake capture into the actual UI queue; no models or devices.

Explicitly addressed commands stay independent while queued; short answers
remain bound to the question at their onset (covered by generation tests).
"""
import os,sys,tempfile,threading,contextlib
from pathlib import Path
from unittest.mock import patch
import numpy as np
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))

with tempfile.TemporaryDirectory(prefix='v3-capture-sessions-') as home,contextlib.ExitStack() as cleanup:
    os.environ['JARVIS_V3_HOME']=home
    from jarvis3.paths import enter
    enter()
    cleanup.callback(os.chdir,ROOT)
    from jarvis3.engine import ui
    from jarvis3.engine.osapi import Fake
    from jarvis3.engine.ears import Ears,BLOCK

    class NoAI:
        loaded=False
        def complete(self,*a,**k):return 'ASK: Which app, sir?'
        def unload(self):pass
    class Mic:
        def __init__(self):self.i=0;self.release=threading.Event()
        def read(self):
            values=[0]*4+[1000]*6+[0]*7+[2000]*6+[0]*7
            if self.i>=len(values):self.release.wait(5);return None
            result=np.full(BLOCK,values[self.i],np.int16);self.i+=1;return result
        def close(self):self.release.set()
    class Filter:
        cancelling=False
        def feed(self,x,ref):return x,[float(bool(x[0]))]
        def reset(self):pass
    class STT:
        def __init__(self,first,second):self.first=first;self.second=second
        def __call__(self,a,h):return self.first if 1000 in a else self.second
        def again(self,a):return ''

    def queued_capture(first,second):
        app=ui.UiApp(gui=False,tray=False);app.say=lambda *a:None
        app.engine.os._running.clear();mic=Mic();delivered=[];ready=threading.Event()
        def heard(item):
            delivered.append(item);app._heard(item)
            if len(delivered)==2:ready.set()
        ear=Ears(mic,None,STT(first,second),heard);ear.canceller=Filter();ear.prefix_wake=False
        app.voice.ears=ear;ear.followup_filter=app._followup_allowed
        ear.conversation_generation=lambda:app.conversation.generation
        ear.is_complete=app.engine.is_complete
        try:
            ear.start();assert ready.wait(4),'two scripted captures were not delivered'
            events=[]
            while not app.q.empty():
                event=app.q.get_nowait()
                if isinstance(event,tuple) and event[0]=='heard':events.append(event)
            assert len(events)==2,'capture could not queue both valid requests while UI was busy'
            assert [h.conversation_generation for h in delivered]==[0,0]
            for event in events:app._voice_msg(*event)
            return list(app.engine.os.log),delivered
        finally:
            ear.shutdown();assert not any(t.is_alive() for t in ear.threads)
            app.store.db.close();app.engine.memory.db.close()

    with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None):
        log,heard=queued_capture('Jarvis','open notepad')
        assert [h.trigger for h in heard]==['name','follow_up']
        assert [x[:2] for x in log]==[('open','notepad')],'wake-alone plus first name-free command was dropped'
        print('CAPTURE SESSIONS: queued wake-alone and first overlapping name-free command accepted once')
        log,heard=queued_capture('Jarvis open notepad','Jarvis open chrome')
        assert [h.trigger for h in heard]==['name','name']
        assert [x[:2] for x in log]==[('open','notepad'),('open','chrome')],'second explicit named command was dropped behind the first UI request'
        print('CAPTURE SESSIONS: two independently named queued commands execute once in order')
    os.chdir(ROOT)
