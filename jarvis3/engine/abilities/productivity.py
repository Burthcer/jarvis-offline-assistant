"""Recurring reminders and student briefing, all local and explicitly requested."""
from datetime import timedelta
import re
from ..registry import Text, Result, ability
from jarvis3.legacy.timeparse import parse_when

@ability('assignment',None,required={'text':Text(),'when':Text()},patterns=[(r'(?:track |add |my )?(?:assignment|homework) (.+?) (?:is )?due (.+)',lambda m:{'text':m[1],'when':m[2]})])
def assignment(args,ctx):
    from ..organizer import date
    due=date(args['when'],ctx.now)
    if not due:return Result(False,'Please give a clear future assignment deadline, sir.',exact=True)
    row,_=ctx.store.add('Assignment: '+args['text'],due,'reminder')
    return Result(True,f"Assignment saved for {due:%d %B at %H:%M}, sir: {args['text']}.",{'id':row['id'],'due':due},exact=True)

@ability('briefing',None,phrases={p:{} for p in ('daily briefing','my day','what should i do today','give me my briefing')})
def briefing(args,ctx):
    start=ctx.now.replace(hour=0,minute=0,second=0,microsecond=0)
    today=ctx.store.between(start,start+timedelta(days=1))
    from ..organizer import rows
    events=[r for r in rows(ctx.memory,'commitments') if r['status']=='active' and r['happens'] and r['happens'][:10]==ctx.now.date().isoformat()]
    text='Today, sir: '+ ('; '.join(r['text'] for r in today) if today else 'no scheduled reminders')
    if events:text+='; events: '+ '; '.join(r['title'] for r in events)
    return Result(True,text+'.',{'count':len(today)+len(events)},exact=True)

@ability('recurring_reminder',None,required={'text':Text(),'schedule':Text()},
         patterns=[(r'remind me (?:every day|daily) at (.+?) to (.+)',lambda m:{'text':m[2],'schedule':'daily at '+m[1]}),
                   (r'remind me (?:every week|weekly) at (.+?) to (.+)',lambda m:{'text':m[2],'schedule':'weekly at '+m[1]})])
def recurring_reminder(args,ctx):
    match=re.fullmatch(r'(daily|weekly) at (.+)',args['schedule'])
    if not match:return Result(False,'Please specify daily or weekly and a time, sir.',exact=True)
    _,due=parse_when('tomorrow at '+match[2],ctx.now)
    if due is None:return Result(False,'Please give a clear time, sir.',exact=True)
    candidate=due-timedelta(days=1)
    if candidate>ctx.now:due=candidate
    row,_=ctx.store.add(args['text'],due,'reminder')
    ctx.store.repeat(row['id'],1 if match[1]=='daily' else 7)
    return Result(True,f"Noted {match[1]}, sir: {args['text']}.",{'id':row['id'],'due':due,'repeat_days':1 if match[1]=='daily' else 7},exact=True)
