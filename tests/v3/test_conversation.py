"""Conversation/arrival through real UI+ears bridge, no models/devices or PC actions."""
import os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-conversation-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.paths import enter
enter()
from jarvis3.conversation import Conversation,Arrival
from jarvis3.engine import ui
from jarvis3.engine.osapi import Fake
from jarvis3.engine.ears import Ears,Heard
clock=[0];c=Conversation(lambda:clock[0]);c.open('reply')
assert c.allowed('open notepad',lambda t:t=='open notepad') and not c.allowed('I told my friend to open notepad')
clock[0]=9;assert not c.allowed('open notepad',lambda t:True)
c.open('question');assert c.allowed('fifteen minutes');c.dismiss();assert not c.allowed('yes')

# A command started before the deadline may finish decoding after it. A status
# refresh in between must neither drop that command nor bypass its room filter.
clock[0]=0;c.open('reply');late=Ears(None,None,None,lambda h:None)
bridge=ui.UiApp.__new__(ui.UiApp);bridge.voice=SimpleNamespace(ears=late)
bridge.conversation=c;bridge.expect_answer=False;bridge.engine=SimpleNamespace(is_complete=lambda t:t=='close notepad')
late.followup_filter=bridge._followup_allowed
with patch('jarvis3.engine.ears.time.monotonic',lambda:0):late.arm(since=0)
clock[0]=9
assert late.in_followup(7,9)
assert late.decide('close notepad',now=9,started=7)==('close notepad','follow_up'),'late decoding lost an eligible command'
assert c.snapshot()=={'state':'standby','reason':None,'seconds_left':0}
assert late.decide('close notepad',now=9,started=7)==('close notepad','follow_up'),'status refresh dropped earlier eligible speech'
assert late.decide('my friend said close notepad',now=9,started=7) is None,'status refresh bypassed room filter'
assert late.decide('close notepad',now=9,started=8) is None,'new speech after deadline was accepted'
c.dismiss();assert late.decide('close notepad',now=9,started=7) is None,'dismissed window authorised delayed speech'
c.begin();assert not c.allowed('close notepad',lambda t:True,eligible=True),'executing state admitted another command'
late.shutdown()
a=Arrival(lambda:clock[0]);assert not a.poll(400,True);assert a.poll(0,True);assert not a.poll(0,True)
a.poll(400,True);assert not a.poll(0,True),'cooldown ignored'
clock[0]+=1000;a.poll(400,True);assert not a.poll(0,False),'suppressed arrival greeted'
class NoAI:
    loaded=False
    def complete(self,*a,**k):return 'ASK: Which app, sir?'
    def unload(self):pass
with patch.object(ui,'Real',Fake),patch.object(ui,'AI',lambda *a,**k:NoAI()),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None):
    app=ui.UiApp(gui=False,tray=False);ear=Ears(None,None,None,lambda h:None);app.voice.ears=ear;ear.followup_filter=app._followup_allowed
    said=[];app.say=lambda text,*args:said.append(text)
    def arrive():
        app._sync_arrival_option();payload=app._queue_arrival('idle')
        while not app.q.empty():app.q.get_nowait()
        with patch('jarvis3.conversation.desktop_idle',lambda:0):app._voice_msg('arrival',payload)
    app.cfg['conversation_followups']=True;app.submit('open notepad',spoken=True)
    assert app.conversation.reason=='reply' and ear.decide('close notepad',started=ear.clock+.1)==('close notepad','follow_up')
    assert ear.decide('I was telling my friend to close notepad',started=ear.clock+.1) is None
    app.submit('nothing right now',spoken=True);assert not ear.armed_until and not app.engine.pending
    app._reply_over();assert not ear.armed_until,'late speech completion reopened dismissed session'
    for phrase in ('dismissed', 'Dismiss.', 'let it go', 'never mind', 'forget it', 'please let it go', 'dismissed, please!'):
        app.conversation.open('wake');ear.arm(since=ear.clock);ear.barge_until=999999999
        before=list(app.engine.os.log)
        assert ear.decide(phrase,started=ear.clock+.1) is not None,phrase
        app.submit(phrase,spoken=True)
        app._reply_over()
        assert not ear.armed_until and not ear.hands_free_until and not ear.barge_until,phrase
        assert app.conversation.state=='standby' and app.engine.os.log==before,phrase
    from jarvis3.conversation import DISMISS
    for phrase in ('play let it go', 'remind me to let it go tomorrow', 'dismissed the meeting', 'forget it and open notepad'):
        assert not DISMISS.fullmatch(phrase),phrase
    app.cfg['arrival_greeting']=True;app.state_name='idle';app.voice.speaker=SimpleNamespace(busy=False)
    arrive();app.voice.speaker=None
    assert 'What can I do' in said[-1] and app.conversation.reason=='arrival' and ear.armed_until
    ui.Api(app).v3_status({'arrival_greeting':False});assert not ear.armed_until
    app.cfg['minimal_feedback']=True;app.feedback.send=lambda *a:True
    count=len(said);app.submit('open notepad',spoken=True);assert len(said)==count,'minimal utility still spoke'
    app.feedback.send=lambda *a:False;app.submit('open notepad',spoken=True);assert len(said)==count+1,'no audible cue silently swallowed feedback'
    app.cfg['conversation_followups']=False;app.cfg['minimal_feedback']=False
    app.conversation.open('interrupt');ear.arm(since=ear.clock)
    app.submit('open notepad',spoken=True)
    assert app.conversation.reason=='interrupt' and ear.decide('close notepad',started=ear.clock+.1)==('close notepad','follow_up'),'interrupted speech lost the next complete command'
    assert not app._followup_allowed('my friend said close notepad'),'interrupt window accepted room talk'
    ui.Api(app).v3_status({'early_interrupts':False})
    assert not ear.armed_until and not ear.barge_until,'disabled interrupt window stayed open'

    app.cfg['arrival_greeting']=True;app.state_name='idle';app.voice.listening=True
    ear.paused_until=float('inf');count=len(said)
    arrive()
    assert len(said)==count and not ear.armed_until,'queued arrival greeted while mic was paused'
    # Watcher permission is tested independently from dispatch permission.
    permitted=[];old_arrival=app.arrival
    app.arrival=SimpleNamespace(poll=lambda idle,allowed,**kw:permitted.append(allowed))
    app.voice.speaker=SimpleNamespace(busy=False);app.voice.talk=True
    while not app.q.empty():app.q.get_nowait()
    source=SimpleNamespace(start=lambda:False,take=lambda:False,close=lambda:True,available=False,locked=False,generation=0)
    with patch('jarvis3.conversation.desktop_idle',lambda:0),patch('jarvis3.session_return.SessionReturn',lambda:source):app._arrival_tick()
    assert permitted==[False],'arrival watcher authorised a paused microphone'
    app.arrival=old_arrival;app.voice.speaker=None

    ear.paused_until=0;app.voice.set_listening(True)
    stale=Heard('open notepad','name','',0,1,capture_epoch=ear.capture_epoch,conversation_generation=app.conversation.generation)
    app._heard(stale);queued=app.q.get_nowait()
    app.engine.pending={'old':'question'};app.conversation.open('question');ear.arm(since=0)
    before=list(app.engine.os.log);old_epoch=ear.capture_epoch
    app.voice.set_listening(False)
    assert ear.capture_epoch==old_epoch+1 and not ear.armed_until and not app.engine.pending
    app.voice.set_listening(True)
    app._voice_msg(*queued)
    assert app.engine.os.log==before,'queued old command survived a quick mic off/on'
    stale_exit=Heard('shutdown','name','',0,1,capture_epoch=old_epoch,conversation_generation=app.conversation.generation)
    app._heard(stale_exit)
    assert not app._shutdown_requested.is_set(),'stale exit bypassed the mic boundary'
    fresh=Heard('open notepad','name','',1,2,capture_epoch=ear.capture_epoch,conversation_generation=app.conversation.generation)
    app._voice_msg('heard',fresh)
    assert len(app.engine.os.log)==len(before)+1,'fresh command after mic on was lost'

    app.engine.set_mic=app._set_mic
    app.submit('mic off')
    assert app.voice.listening and not app.voice.can_listen() and ear.paused_until>ui.time.monotonic(),'temporary mic off did not pause listening'
    count=len(said);app.state_name='idle';arrive()
    assert len(said)==count,'temporary mic-off allowed an arrival greeting'
    assert app._set_mic(True) and app.voice.can_listen()
    app.voice.shutdown();app.store.db.close();app.engine.memory.db.close()
print('CONVERSATION: bounded follow-up/late decoding/status safety, arrival/cooldown/mic pause, stale queued speech/exit revocation, disable and minimal fallback passed')
