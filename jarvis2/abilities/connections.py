"""Read-only connected summaries are explicit requests, not background sync."""
from ..registry import Choice,Result,ability
@ability('google_read',None,required={'service':Choice('gmail','calendar')},phrases={
    'check my gmail':{'service':'gmail'},'read my unread emails':{'service':'gmail'},
    'check my google calendar':{'service':'calendar'},'check my calendar':{'service':'calendar'},'my google calendar':{'service':'calendar'}})
def google_read(args,ctx):
    connection=getattr(ctx.app,'google',None)
    if connection is None:return Result(False,'Connect Google in Settings first, sir.',exact=True)
    try:items=connection.read(args['service'])
    except Exception:return Result(False,'I could not read Google. Check your connection in Settings, sir.',exact=True)
    lines=[item['title']+' — '+item.get('when',item.get('from','')) for item in items]
    return Result(True,('; '.join(lines) if lines else 'Nothing found')+', sir.',{'count':len(items)},exact=True)
