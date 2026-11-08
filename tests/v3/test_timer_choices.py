"""Timer clarification is bound to ordered records, never guessed from history."""
import os,sys,tempfile,contextlib
from pathlib import Path
from datetime import datetime,timedelta
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='v3-timer-choices-') as home,contextlib.ExitStack() as cleanup:
    os.environ['JARVIS_V3_HOME']=home
    from jarvis3.paths import enter
    enter();cleanup.callback(os.chdir,ROOT)
    from jarvis3.engine.app import App
    from jarvis3.engine.osapi import Fake
    from jarvis3.legacy.store import Store
    class PC(Fake):
        def catalog(self):return {'notepad':'app'}
    class AI:
        def __init__(self,action):self.action=action;self.calls=0
        def complete(self,*a,**k):self.calls+=1;return 'timer_control(action="'+self.action+'")'
    apps=[]
    def fresh(action='cancel',duplicate=False):
        clock=[datetime(2031,2,3,10)];store=Store(':memory:');ai=AI(action)
        app=App(PC(),store,ai,natural=False,clock=lambda:clock[0]);apps.append(app)
        for seconds in (420,420 if duplicate else 660):
            row,_=store.add(f'{seconds//60}-minute',clock[0]+timedelta(seconds=seconds),kind='timer',merge=False)
            if action=='resume':store.pause_timer(row['id'],clock[0])
        return app,store,ai,clock
    try:
        app,store,ai,clock=fresh();before=[dict(r) for r in store.all_timers()]
        reply=app.handle('cancel a timer');assert reply.plan.kind=='ask' and len(store.all_timers())==2
        reply=app.handle('the second one')
        assert reply.ok and store.get(before[1]['id']) is None and store.get(before[0]['id']) is not None,'ordinal reply did not select the second spoken stable timer identity'
        assert ai.calls==1,'ordinal timer answer went back through the model'
        for action in ('pause','resume'):
            from jarvis3.engine.dialogue import timer_pool
            app,store,ai,clock=fresh(action);ordered=[dict(row) for row in timer_pool(store,action)]
            assert app.handle(action+' a timer').plan.kind=='ask'
            reply=app.handle('the first timer')
            assert reply.ok and reply.results[0][1].facts['ids']==[ordered[0]['id']]
            assert store.get(ordered[0]['id'])['status']==('paused' if action=='pause' else 'open')
            assert store.get(ordered[1]['id'])['status']==ordered[1]['status'] and ai.calls==1
        app,store,ai,clock=fresh(duplicate=True);ordered=[dict(row) for row in store.all_timers()]
        app.handle('cancel a timer');reply=app.handle('2nd one')
        assert reply.ok and reply.results[0][1].facts['ids']==[ordered[1]['id']]
        assert store.get(ordered[0]['id']) is not None and store.get(ordered[1]['id']) is None,'equal lengths selected more than one timer'
        app,store,ai,clock=fresh();app.handle('cancel a timer');snapshot=[dict(row) for row in store.all_timers()]
        for text in ('the ninth one','0th one','999th timer'):
            assert app.handle(text).plan.kind=='ask' and [dict(row) for row in store.all_timers()]==snapshot
            assert app.dialogue.timer_question is not None and ai.calls==1,'invalid ordinal cancelled the question or used AI'
        assert app.handle('last one').ok and store.get(snapshot[-1]['id']) is None
        app,store,ai,clock=fresh();app.handle('cancel a timer');snapshot=[dict(row) for row in store.all_timers()]
        clock[0]+=timedelta(seconds=121)
        reply=app.handle('first one')
        assert reply.plan.kind=='ask' and ai.calls==1 and app.dialogue.timer_question is None
        assert [dict(row) for row in store.all_timers()]==snapshot,'expired question changed a timer'
        for change in ('add','remove','left','pause','text','order'):
            app,store,ai,clock=fresh();app.handle('cancel a timer');rows=store.all_timers()
            if change=='add':store.add('13-minute',clock[0]+timedelta(minutes=13),'timer',merge=False)
            if change=='remove':store.delete(rows[0]['id'])
            if change=='left':store.set_timer_left(rows[0]['id'],500,clock[0],False)
            if change=='pause':store.pause_timer(rows[0]['id'],clock[0])
            if change=='text':store.db.execute("UPDATE items SET text='different label' WHERE id=?",(rows[0]['id'],));store.db.commit()
            if change=='order':store.db.execute('UPDATE items SET due=? WHERE id=?',((clock[0]+timedelta(seconds=1)).isoformat(),rows[0]['id']));store.db.commit()
            changed=[dict(row) for row in store.all_timers()]
            reply=app.handle('second one')
            assert reply.plan.kind=='ask' and [dict(row) for row in store.all_timers()]==changed and ai.calls==1,change
        # Mutate after preparing the plan: the ability must recheck under lock.
        app,store,ai,clock=fresh();app.handle('cancel a timer')
        plan,_=app.dialogue.request('first one',clock[0]);store.pause_timer(store.all_timers()[0]['id'],clock[0])
        changed=[dict(row) for row in store.all_timers()]
        reply=app._run(plan,'first one','typed',clock[0],{})
        assert not reply.ok and [dict(row) for row in store.all_timers()]==changed
        app,store,ai,clock=fresh();app.handle('cancel a timer');plan,_=app.dialogue.request('second one',clock[0])
        plan.calls[0].args['action']='pause';snapshot=[dict(row) for row in store.all_timers()]
        assert not app._run(plan,'second one','typed',clock[0],{}).ok and [dict(row) for row in store.all_timers()]==snapshot,'choice action could be swapped'
        other,other_store,_,_=fresh()
        assert not other._run(plan,'second one','typed',clock[0],{}).ok and len(other_store.all_timers())==2,'choice crossed store identity'
        app,store,ai,clock=fresh();app.handle('cancel a timer');app.handle('open notepad')
        assert app.dialogue.timer_question is None
        assert app.handle('the second one').plan.kind=='ask' and len(store.all_timers())==2,'unrelated command retained old timer selection'
        app,store,ai,clock=fresh()
        app.history.append({'at':clock[0],'said':'cancel a timer','reply':'Which one, first or second?','ability':['ctx'],'ok':True})
        assert app.handle('the second one').plan.kind=='ask' and len(store.all_timers())==2,'free-text history invented a stable timer binding'

        # Cancellation from the real UI/mic lifecycle revokes the engine ticket.
        from jarvis3.engine import ui
        from jarvis3.engine.ears import Ears
        with patch.object(ui,'Real',PC),patch.object(ui,'AI',lambda *a,**k:AI('cancel')),patch.object(ui.UiApp,'_boot',lambda self:None),patch.object(ui.settings,'set_autostart',lambda on:None):
            window=ui.UiApp(gui=False,tray=False);window.engine.clock=lambda:datetime(2031,2,3,10)
            window.say=lambda *a,**k:None;window.voice.ears=Ears(None,None,None,lambda h:None)
            try:
                for minutes in (7,11):window.store.add(f'{minutes}-minute',window.engine.clock()+timedelta(minutes=minutes),'timer',merge=False)
                window.submit('cancel a timer',spoken=True);assert window.engine.dialogue.timer_question
                window.submit('nothing right now');assert window.engine.dialogue.timer_question is None
                window.engine.handle('cancel a timer');assert window.engine.dialogue.timer_question
                window.voice.set_listening(False);window.voice.set_listening(True)
                assert window.engine.dialogue.timer_question is None and len(window.store.all_timers())==2
                window.engine.handle('cancel a timer');assert window.engine.dialogue.timer_question
                window.voice.shutdown();assert window.engine.dialogue.timer_question is None
            finally:window.voice.shutdown();window.store.db.close();window.engine.memory.db.close()
    finally:
        for app in apps:app.store.db.close();app.memory.db.close()
print('TIMER CHOICES: ordered/duplicate IDs, pause/resume/action/store binding, invalid/expired/changed/racing choices, unrelated/history-only refusal, UI/mic/shutdown revocation passed')
