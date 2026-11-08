"""A queued answer belongs to its original question, never a replacement.

Fake PC, scripted models and silent bridge; no microphone or account access.
"""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
with tempfile.TemporaryDirectory(prefix='v3-question-generation-') as home:
    os.environ['JARVIS_V3_HOME']=home
    from jarvis3.paths import enter
    enter()
    from jarvis3.engine import ui
    from jarvis3.engine.osapi import Fake
    from jarvis3.engine.ears import Ears,Heard
    from jarvis3.workspaces import save

    class NoAI:
        loaded=False
        def complete(self,*a,**k):return 'ASK: Which app, sir?'
        def unload(self):pass

    with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None):
        app=ui.UiApp(gui=False,tray=False);ear=Ears(None,None,None,lambda h:None)
        app.voice.ears=ear;app.say=lambda *args:None;app.engine.os._running.clear()
        def heard(text,generation):
            return Heard(text,'follow_up','',1,2,capture_epoch=ear.capture_epoch,conversation_generation=generation)
        def queued():
            while not app.q.empty():
                event=app.q.get_nowait()
                if isinstance(event,tuple) and event[0]=='heard':return event
            raise AssertionError('Expected an accepted speech event')
        try:
            save(app.engine.memory,'alpha',['notepad'],[],'edge',app.engine.catalog)
            save(app.engine.memory,'beta',['chrome'],[],'edge',app.engine.catalog)
            app.submit('start workspace alpha',spoken=True)
            first=app.conversation.generation
            app._heard(heard('yes',first));old=queued()
            app.submit('start workspace beta',spoken=True)
            second=app.conversation.generation
            assert second!=first and app.engine.pending.pending['workspace']=='beta'
            app._voice_msg(*old)
            assert not app.engine.os.log and app.engine.pending.pending['workspace']=='beta','old queued yes approved a replacement question'
            app._heard(heard('yes',first))
            app._heard(heard('shutdown',first))
            assert app.q.empty() and not app._shutdown_requested.is_set(),'old STT or urgent exit entered the new session'
            app._heard(heard('yes',second));fresh=queued();app._voice_msg(*fresh)
            assert [x[:2] for x in app.engine.os.log]==[('open','chrome')],'new yes did not execute only the new profile'
            before=list(app.engine.os.log);app._voice_msg(*fresh)
            assert app.engine.os.log==before,'consumed speech event executed twice'
            app.submit('start workspace alpha',spoken=True)
            dismissed=app.conversation.generation
            app._heard(heard('yes',dismissed));old=queued()
            app.submit('nothing right now',spoken=True)
            app._voice_msg(*old);app._reply_over()
            assert app.engine.os.log==before and not ear.armed_until and app.conversation.reason is None,'dismissed question reopened or executed'
            # Independently named full requests survive another task beginning,
            # but neither duplicates nor explicit dismissal can replay them.
            generation=app.conversation.generation
            def named(text,start,generation=generation):
                return Heard(text,'name','',start,start+1,capture_epoch=ear.capture_epoch,conversation_generation=generation)
            first_named=named('open notepad',10);second_named=named('open chrome',12)
            app._heard(first_named);first_event=queued()
            app._heard(second_named);second_event=queued()
            app._voice_msg(*first_event);app._voice_msg(*second_event)
            after=list(app.engine.os.log)
            assert after[len(before):]==[('open','notepad','app',1,None),('open','chrome','app',1,None)]
            app._voice_msg(*second_event)
            assert app.engine.os.log==after,'independent named event replayed after consumption'
            for text in ('yes','undo that','the second one'):
                assert not app.voice.accepts(named(text,30)),'old question-bound named text escaped its session'
            generation=app.conversation.generation
            pending=named('open notepad',40,generation);app._heard(pending);pending_event=queued()
            app.submit('nothing right now',spoken=True);app._voice_msg(*pending_event)
            assert not app.voice.accepts(pending) and app.engine.os.log==after,'dismissal failed to revoke an older independent command'
        finally:
            ear.shutdown();app.store.db.close();app.engine.memory.db.close()
            os.chdir(Path(__file__).resolve().parents[2])
print('CONVERSATION GENERATION: old queued/delayed yes and exit refused, fresh confirmation once, dismissal not reopened')
