"""Bounded exact-state local rollback. External irreversible actions are barriers."""
from collections import deque
import re,time
LOCAL={'timer_set','timer_control','reminder_add','reminder_change','reminder_cancel','note_save','note_forget','assignment','recurring_reminder'}
READS={'clock','volume_read','note_recall','reminder_list','briefing','knowledge_summary','recap','capabilities'}
# These direct calls cannot mutate the local Store. In a mixed group they stay
# external barriers; only the exact local database delta may be restored.
MIXED_EXTERNAL={'open','close','focus','window_state'}
class Ledger:
    def __init__(self,clock=time.monotonic):self.clock=clock;self.entries=deque(maxlen=30)
    @staticmethod
    def snapshot(store):
        rows={}
        for table,key in (('items','id'),('note_meta','note_id'),('repeats','item_id')):
            values=store.db.execute('SELECT * FROM '+table+' LIMIT 2001').fetchall()
            if len(values)>2000:raise ValueError('Undo snapshot too large')
            rows[table]={r[key]:dict(r) for r in values}
        return rows
    @staticmethod
    def external(app,plan):
        if len(plan.calls)!=1:return None
        call=plan.calls[0]
        if call.ability=='volume' and not call.args.get('app'):
            def read():
                value,muted=app.os.volume(),app.os.muted()
                if type(value) not in (int,float) or not 0<=value<=100 or type(muted) is not bool:raise ValueError('Audio state unavailable')
                return value,muted
            def restore(value):app.os.set_volume(value[0]);app.os.set_muted(value[1])
        elif call.ability=='voice_tune' and getattr(app.speech,'v',None):
            sp=app.speech;read=lambda:(sp.v.speed,sp.v.volume)
            def restore(value):
                sp.v.set_speed(value[0]);sp.v.set_volume(value[1]);sp.on_tune({'tts_speed':sp.v.speed,'tts_volume':sp.v.volume})
        else:return None
        try:return {'read':read,'restore':restore,'before':read(),'scope':lambda:call.ability!='volume' or not call.args.get('app')}
        except Exception:return None
    def record(self,results,before=None,after=None,extra=None):
        actions=[c for c,r in results if c.ability not in READS and not (c.ability=='timer_control' and c.args['action']=='status')]
        if not actions or all(c.ability in ('undo','repeat','correction') for c in actions):return
        if not extra and len(results)==1:
            from .window_undo import CheckedUndo
            undo=results[0][1].undo
            if isinstance(undo,CheckedUndo):extra={'read':undo.read,'restore':undo.restore,'before':undo.before,'after':undo.after,'scope':lambda:True}
        if extra:
            try:
                if not extra['scope']():raise ValueError('Resolved audio target changed')
                extra['after']=extra['read']()
                if extra['before']==extra['after']:return
            except Exception:extra=None
        change={};guards={};remaining=[]
        if before is not None and after is not None:
            for call in actions:
                if call.ability in MIXED_EXTERNAL:
                    action=call.args.get('action',call.ability) if call.ability=='window_state' else call.ability
                    remaining.append(str(action)+' '+str(call.args.get('target') or 'the selected window'))
            for table in before:
                diff={i:(before[table].get(i),after[table].get(i)) for i in before[table].keys()|after[table].keys() if before[table].get(i)!=after[table].get(i)}
                if diff:change[table]=diff
            if not change and not remaining:return
            # Do not retain secret notes in a rollback ledger.
            from .engine.knowledge import describe
            for pair in change.get('items',{}).values():
                if any(r and r['kind']=='note' and describe(r['text'])['secret'] for r in pair):change={};break
            # A later alias/source/repeat edit must protect its item even when
            # that metadata row did not exist (or change) during this action.
            for table in ('note_meta','repeats'):
                guards[table]={ident:after[table].get(ident) for ident in change.get('items',{})}
        self.entries.append({'at':self.clock(),'change':change,'guards':guards,'extra':extra,'remaining':remaining,'actions':[c.ability for c in actions]})
    def undo(self,store):
        if not self.entries:return False,'There is nothing recent to undo, sir.'
        entry=self.entries[-1]
        if self.clock()-entry['at']>120:return False,'That undo window has expired, sir.'
        if entry.get('extra'):
            extra=entry['extra']
            try:
                if extra['read']()!=extra['after']:return False,'That setting changed afterwards, sir. I left it alone.'
                extra['restore'](extra['before'])
                if extra['read']()!=extra['before']:return False,'I could not fully restore that setting, sir.'
                self.entries.pop();return True,'Undone, sir.'
            except Exception:return False,'I could not safely restore that setting, sir.'
        if not entry['change']:
            if entry.get('remaining'):return False,'Those app/window actions are left unchanged, sir: '+', '.join(entry['remaining'])+'. I cannot safely undo them.'
            return False,'I cannot safely undo that action, sir.'
        with store.lock:
            db=store.db
            try:
                db.execute('BEGIN IMMEDIATE')
                for table,rows in entry.get('guards',{}).items():
                    key='note_id' if table=='note_meta' else 'item_id'
                    for ident,expected in rows.items():
                        row=db.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(ident,)).fetchone()
                        if (dict(row) if row else None)!=expected:
                            db.rollback();return False,'That item changed afterwards, sir. I left it alone.'
                for table,changes in entry['change'].items():
                    key='id' if table=='items' else 'note_id' if table=='note_meta' else 'item_id'
                    for ident,(old,new) in changes.items():
                        row=db.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(ident,)).fetchone()
                        if (dict(row) if row else None)!=new:
                            db.rollback();return False,'That item changed afterwards, sir. I left it alone.'
                for table,changes in entry['change'].items():
                    key='id' if table=='items' else 'note_id' if table=='note_meta' else 'item_id'
                    for ident,(old,new) in changes.items():
                        db.execute('DELETE FROM '+table+' WHERE '+key+'=?',(ident,))
                        if old:
                            keys=list(old);db.execute('INSERT INTO '+table+' ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',[old[k] for k in keys])
                db.commit()
                if entry.get('remaining'):
                    entry['change']={};entry['guards']={}
                    return True,'Local changes undone, sir. App/window actions left unchanged: '+', '.join(entry['remaining'])+'.'
                self.entries.pop()
                return True,'Undone, sir.'
            except Exception:
                db.rollback();return False,'I could not undo that safely, sir.'
