"""Completion cues require a known postcondition, not merely a sent OS request."""
LOCAL={'timer_set','timer_control','reminder_add','reminder_change','reminder_cancel','note_save','note_forget','assignment','recurring_reminder'}
READBACK={'volume','volume_read','note_copy','window_state','browser_tabs','tab_close','tab_focus','tab_group_close','clock','reminder_list','note_recall','briefing','knowledge_summary'}
def status(call,result,app):
    if not result.ok:return False
    if call.ability=='voice_tune':
        v=getattr(app.speech,'v',None)
        if v is None:return None
        key='speed' if call.args['change'] in ('faster','slower') else 'volume'
        return getattr(v,key,None)==result.facts.get(key)
    if call.ability=='stop_talking':return True
    if call.ability in ('music_start','music_reject','workspace_run','workspace_resume'):return True if result.facts.get('verified') else None
    if call.ability in ('choices_show','choices_pick'):
        return True if result.facts.get('verified') else None
    if call.ability in LOCAL:
        return local_status(call,result,app.store)
    if call.ability in READBACK:return True
    if call.ability=='media' and call.args['action'] in ('play','pause'):return True
    if call.ability=='open':
        if call.args.get('count',1)!=1:return None
        try:return app.os.verify_open(call.args['target'],app.catalog[call.args['target']])
        except Exception:return None
    if call.ability=='close':return True  # close checks actual window/process absence
    if call.ability=='focus':return True  # focus checks actual foreground state
    return None

def local_status(call,result,store):
    """Read exact affected IDs back after commit, including absent/deleted records."""
    name,args,facts=call.ability,call.args,result.facts
    if name=='timer_control' and args['action']=='status':return True
    if facts.get('changed') is False:return True
    if name=='reminder_cancel' or name=='timer_control':
        ids=facts.get('ids')
        if not ids:return None
        rows=[store.get(i) for i in ids]
        if name=='reminder_cancel' or args['action']=='cancel':return all(r is None for r in rows)
        want='paused' if args['action']=='pause' else 'open'
        return all(r is not None and r['kind']=='timer' and r['status']==want for r in rows)
    ident=facts.get('id')
    if ident is None:return None
    row=store.get(ident)
    if name=='note_forget':return row is None
    kind='timer' if name=='timer_set' else 'note' if name=='note_save' else 'reminder'
    if row is None or row['kind']!=kind or row['status']!='open':return False
    due=args.get('when') if name=='reminder_change' else facts.get('due')
    if due is not None and row['due']!=(due.isoformat() if hasattr(due,'isoformat') else due):return False
    if name=='reminder_change' and 'text' in args and row['text']!=args['text']:return False
    if name=='note_save':
        from .engine.abilities.personal import spoken_symbols
        if row['text']!=(args['text'] if facts.get('literal') else spoken_symbols(args['text'])):return False
        if facts.get('literal'):
            with store.lock:meta=store.db.execute('SELECT source FROM note_meta WHERE note_id=?',(ident,)).fetchone()
            if not meta or meta[0]!=facts.get('source'):return False
    if name=='recurring_reminder':
        with store.lock:repeat=store.db.execute('SELECT days FROM repeats WHERE item_id=?',(ident,)).fetchone()
        return repeat is not None and repeat[0]==facts.get('repeat_days')
    return True
