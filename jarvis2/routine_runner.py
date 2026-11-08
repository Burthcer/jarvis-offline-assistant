"""Persist safe checked call progress; resume only when explicitly requested."""
import hashlib,json
from datetime import datetime
from .registry import ABILITIES,Result,Duration,Which,When

def encode(value):
    if isinstance(value,datetime):return {'__datetime__':value.isoformat()}
    raise TypeError('Unsupported saved argument')
def decode(value):
    return datetime.fromisoformat(value['__datetime__']) if set(value)=={'__datetime__'} else value

def checked(step):
    """Stored values are already converted: validate them without reinterpreting them."""
    ab=ABILITIES.get(step['a']); args=step['args']
    if not ab or not isinstance(args,dict):raise ValueError('Invalid saved call')
    types={**ab.required,**ab.optional}
    if set(args)-set(types) or set(ab.required)-set(args):raise ValueError('Invalid saved arguments')
    for name,value in args.items():
        kind=types[name]
        if isinstance(kind,Which):
            if not isinstance(value,str) or not (value=='all' or value.isdecimal()):raise ValueError('Invalid timer selector')
        elif isinstance(kind,Duration):
            if type(value)!=int or value<=0:raise ValueError('Invalid saved duration')
        elif isinstance(kind,When):
            if not isinstance(value,datetime):raise ValueError('Invalid saved date')
        else:kind.check(value)

def run(name,ctx,resume=False):
    from . import understand
    from .abilities.skills import NOT_IN_SKILL
    steps=ctx.memory.routine_get(name)
    if not steps:return Result(False,'That routine was not found, sir.',exact=True)
    digest=hashlib.sha256(json.dumps(steps,sort_keys=True).encode()).hexdigest()
    calls=[]; cursor=0
    row=ctx.memory._q('SELECT fingerprint,calls,cursor,state FROM routine_progress WHERE name=?',name)
    if resume:
        if not row or row[0][0]!=digest or row[0][3]!='paused':return Result(False,'There is no unchanged paused routine to resume, sir.',exact=True)
        calls=json.loads(row[0][1],object_hook=decode); cursor=row[0][2]
    else:
        for step in steps:
            if step['a']=='say':
                plan=understand.resolve(step['args']['text'],ctx.snapshot,ctx.app.names,ctx.app.ai,ctx.now,False,None)
                if plan.kind!='act':return Result(False,'A routine step needs clarification. Nothing ran, sir.',exact=True)
                calls.extend({'a':c.ability,'args':c.args} for c in plan.calls)
            else:calls.append(step)
        if any(s['a'] not in ABILITIES or ABILITIES[s['a']].risk!='safe' or s['a'] in NOT_IN_SKILL for s in calls):
            return Result(False,f'I stopped before an unsafe routine step. Stopped after 0 of {len(calls)} steps, sir.',exact=True)
        try:json.dumps(calls,default=encode)
        except TypeError:return Result(False,'A routine argument could not be safely saved, sir.',exact=True)
    try:
        for step in calls[cursor:]:checked(step)
    except (ValueError,TypeError,KeyError):return Result(False,'A saved routine argument is no longer valid. Please edit the routine, sir. Nothing ran.',exact=True)
    out=[]
    def save(state):
        ctx.memory._w('INSERT OR REPLACE INTO routine_progress VALUES(?,?,?,?,?,?)',name,digest,json.dumps(calls,default=encode),cursor,state,ctx.now.isoformat())
    while cursor<len(calls):
        step=calls[cursor]; ab=ABILITIES.get(step['a'])
        if not ab or ab.risk!='safe' or step['a'] in NOT_IN_SKILL:return Result(False,'Routine permissions changed; please edit it, sir.',exact=True)
        save('running')
        try:result=ab.fn(dict(step['args']),ctx)
        except Exception:result=Result(False,'The routine step failed, sir.')
        out.append(result.plain)
        if not result.ok:
            save('paused')
            return Result(False,' '.join(out)+f' Stopped after {cursor} of {len(calls)} steps, sir. Say resume routine {name} to retry the failed step.',{'steps':cursor,'total':len(calls)},exact=True)
        cursor+=1; save('paused' if cursor<len(calls) else 'done')
    return Result(True,' '.join(out) or 'Routine already complete, sir.',{'steps':cursor,'total':len(calls)},exact=True)
