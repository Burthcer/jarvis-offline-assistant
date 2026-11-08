import re
from ..registry import Text,Bool,Result,ability
ORDINALS=dict(zip('first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth'.split(),range(1,13)))
POSITION=r'(?:\d{1,2}(?:st|nd|rd|th)?|'+'|'.join(ORDINALS)+')'
def service(ctx):
    selection=getattr(ctx.app,'selection',None)
    if selection is None:raise ValueError('Numbered choices are available in the V3 desktop app, sir.')
    return selection
GROUPS={'choices':'videos','results':'results','links':'results','options':'results','search results':'results','items':'results'}
def group_of(word):
    return GROUPS.get(word,word)
@ability('choices_show',None,optional={'group':Text()},patterns=[
    (r'(?:show|number|list) (?:the )?(?:visible |on screen )?(mixes|playlists|videos|choices|results|search results|links|options|items)(?: on (?:the )?screen)?',lambda m:{'group':group_of(m[1])})])
def choices_show(args,ctx):
    try:snapshot=service(ctx).show(args.get('group','videos'))
    except ValueError as e:return Result(False,str(e),exact=True)
    return Result(True,f'Numbered {len(snapshot.items)} choices, sir. Which one?',{'awaiting_choice':True,'verified':True},exact=True)
NOUN=r'(?: (?:one|mix(?: playlist)?|video|playlist|choice|result|link|card|item|song|option|search result))?'
def _group(said):
    for word,group in (('mix','mixes'),('playlist','playlists'),('video','videos'),('result','results'),('link','results'),('option','results'),('item','results')):
        if word in said:return {'group':group}
    return {}
@ability('choices_pick',None,required={'selector':Text()},optional={'group':Text(),'play':Bool()},patterns=[
    (rf'(?:play|pick|choose|select|click(?: on)?|tap(?: on)?|open|start|go to|press) (?:the |this |that |on the )?({POSITION}){NOUN}(?: on (?:the )?screen)?',lambda m:{'selector':m[1],'play':m[0].startswith('play '),**_group(m[0])}),
    (r'(?:pick|choose|select|open) (?:the )?item (?:called|named) (.+)',lambda m:{'selector':m[1]})])
def choices_pick(args,ctx):
    raw=args['selector'].strip().lower();selector=ORDINALS.get(raw)
    if selector is None:selector=int(re.sub(r'\D','',raw)) if re.fullmatch(r'\d{1,2}(?:st|nd|rd|th)?',raw) else raw
    try:return service(ctx).pick(selector,ctx.confirmed,getattr(ctx.app,'confirmation_data',{}),args.get('group'),args.get('play',False),direct=True)   # no 'Open X, sir?' first: he asked for it to just open
    except ValueError as e:return Result(False,str(e),exact=True)
@ability('choices_cancel',None,phrases={p:{} for p in ('cancel choices','hide choices','clear choices','cancel selection')})
def choices_cancel(args,ctx):
    service(ctx).cancel();return Result(True,'',{'silent':True},exact=True)
