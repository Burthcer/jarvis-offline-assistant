"""Opt-in idle/unlock greetings via injected source, real UI and fake devices."""
import os,sys,tempfile,contextlib,threading
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='v3-arrival-sessions-') as home,contextlib.ExitStack() as cleanup:
    os.environ['JARVIS_V3_HOME']=home
    from jarvis3.paths import enter
    enter();cleanup.callback(os.chdir,ROOT)
    from jarvis3.engine import ui
    from jarvis3.engine.osapi import Fake
    from jarvis3.engine.ears import Ears
    from jarvis3.conversation import Arrival

    class NoAI:
        loaded=False
        def complete(self,*a,**k):return 'ASK: Which app, sir?'
        def unload(self):pass
    class Source:
        instances=[];fail=False
        def __init__(self):
            self.available=False;self.locked=False;self.generation=0;self.pending=False
            self.starts=0;self.closes=0;self.takes=0;self.error=''
            self.instances.append(self)
        def start(self):self.starts+=1;self.available=not self.fail;return self.available
        def take(self):
            self.takes+=1;result=self.available and self.pending;self.pending=False;return result
        def lock(self):self.locked=True;self.generation+=1;self.pending=False
        def unlock(self):
            assert self.locked
            self.locked=False;self.generation+=1;self.pending=True
        def close(self):self.closes+=1;self.available=False;self.pending=False;return True

    clock=[100.0];idle=[0]
    with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None),patch('jarvis3.session_return.SessionReturn',Source),patch('jarvis3.conversation.desktop_idle',lambda:idle[0]),patch('jarvis3.engine.ui.time.monotonic',lambda:clock[0]):
        app=ui.UiApp(gui=False,tray=False);ear=Ears(None,None,None,lambda h:None);app.voice.ears=ear
        said=[];app.say=lambda text,*a:said.append(text);app.voice.speaker=NS(busy=False,shutdown=lambda:None)
        app.arrival=Arrival(lambda:clock[0]);app.state_name='idle';app.voice.talk=True
        def clear():
            while not app.q.empty():app.q.get_nowait()
        def ticket(kind='unlock'):
            clear();payload=app._queue_arrival(kind)
            clear();assert payload is not None;return payload
        def finish():
            app.conversation.dismiss();ear.armed_until=0;app.state_name='idle';clear()
        def pair(source):source.lock();source.unlock()
        def arrivals():
            found=[]
            while not app.q.empty():
                event=app.q.get_nowait()
                if isinstance(event,tuple) and event[0]=='arrival':found.append(event[1])
            return found
        try:
            app._arrival_tick();assert not Source.instances,'disabled option created a native watcher'
            ui.Api(app).v3_status({'arrival_greeting':True});app._arrival_tick()
            source=Source.instances[-1];assert source.starts==1 and not arrivals()
            pair(source);app._arrival_tick();pending=arrivals();assert len(pending)==1 and pending[0]['source']=='unlock'
            app._voice_msg('arrival',pending[0]);app._voice_msg('arrival',pending[0])
            assert len(said)==1 and app.conversation.reason=='arrival' and ear.armed_until,'fresh unlock was lost or duplicate greeted'
            finish()
            idle[0]=400;app._arrival_tick();idle[0]=0;app._arrival_tick()
            pair(source);app._arrival_tick();assert not arrivals(),'unlock and idle return did not share cooldown'
            clock[0]+=901
            for flag in ('do_not_disturb','paused','quiet','active'):
                if flag=='do_not_disturb':app.cfg['do_not_disturb']=True
                if flag=='paused':ear.paused_until=float('inf')
                if flag=='active':ear.arm(since=ear.clock)
                pair(source)
                with patch('jarvis3.engine.preferences.quiet',lambda cfg:flag=='quiet'):app._arrival_tick()
                assert not arrivals() and not source.pending,'suppressed unlock was retained for a surprise greeting'
                app.cfg['do_not_disturb']=False;ear.paused_until=0;ear.armed_until=0
                app._arrival_tick();assert not arrivals(),'clearing suppression revived an old unlock'
            pair(source);payload=ticket();source.lock();count=len(said)
            app._voice_msg('arrival',payload);assert len(said)==count,'queued unlock greeted after relock'
            source.unlock();payload=ticket();pair(source)
            app._voice_msg('arrival',payload);assert len(said)==count,'old queued greeting survived a later lock/unlock pair'
            source.pending=False
            payload=ticket();app.conversation.begin();app._voice_msg('arrival',payload)
            assert len(said)==count,'queued greeting survived a new task'
            payload=ticket();app.conversation.dismiss();app._voice_msg('arrival',payload)
            assert len(said)==count,'queued greeting survived dismissal'
            payload=ticket();clock[0]+=16;app._voice_msg('arrival',payload)
            assert len(said)==count,'expired queue ticket greeted'
            payload=ticket();idle[0]=None;app._voice_msg('arrival',payload);idle[0]=0
            assert len(said)==count,'unavailable input desktop still greeted'
            payload=ticket();ui.Api(app).v3_status({'arrival_greeting':False})
            assert source.closes==1 and app._arrival_source is None,'opt-out kept the notification source open'
            ui.Api(app).v3_status({'arrival_greeting':True});app._voice_msg('arrival',payload)
            assert len(said)==count,'quick off/on revived an old queued greeting'
            app._arrival_tick();current=Source.instances[-1];assert current is not source and current.starts==1
            ui.Api(app).v3_status({'arrival_greeting':False});assert current.closes==1
            Source.fail=True;ui.Api(app).v3_status({'arrival_greeting':True});app._arrival_tick()
            failed=Source.instances[-1];assert not failed.available and failed.starts==1
            app._arrival_tick();app._arrival_tick();assert failed.starts==1,'failed native registration retried every tick'
            app.arrival=Arrival(lambda:clock[0]);idle[0]=400;app._arrival_tick();idle[0]=0;app._arrival_tick()
            fallback=arrivals();assert len(fallback)==1 and fallback[0]['source']=='idle'
            app._voice_msg('arrival',fallback[0]);assert len(said)==count+1,'unavailable native source disabled idle fallback'
            app._arrival_thread=threading.Thread(target=app._arrival_watch);app._arrival_thread.start()
            app.voice.shutdown()
            assert failed.closes==1 and not app._arrival_thread.is_alive(),'voice shutdown leaked source/watcher'
            before=len(Source.instances);app._arrival_tick();assert len(Source.instances)==before,'shutdown restarted native source'
        finally:
            app.voice.shutdown();app.store.db.close();app.engine.memory.db.close()
print('ARRIVAL SESSIONS: opt-in, unlock+idle shared cooldown, suppression consumption, single-use/stale/task/off-on/relock tickets, failed-source fallback and shutdown passed')
