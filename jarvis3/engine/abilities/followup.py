"""repeat, undo, recap: they act on the last turn that did something (ctx.app.last_acts = [(Call, Result)])."""
from jarvis3.legacy.actions import merge_replies

from ..registry import ABILITIES, Result, ability

SELF = ("repeat", "undo", "recap", "correction", "forget_alias", "learned_clear", "knowledge_summary", "learning", "routine_save", "routine_run", "routine_resume", "routine_forget", "skill_teach", "wish_add", "wish_list")   # these never become "the last thing"


@ability("repeat", "do the last thing again", phrases={p: {} for p in ("again", "do that again", "repeat that", "once more", "do it again")})
def repeat(args, ctx):
    last = ctx.app.last_acts
    if not last:
        return Result(False, "I haven't done anything yet to repeat, sir.")
    if any(ABILITIES[c.ability].risk!='safe' for c,_ in last):
        return Result(False,'Please request that sensitive action again so I can ask for fresh confirmation, sir.',exact=True)
    out = []
    for c, _ in last:
        result=ABILITIES[c.ability].fn(c.args,ctx)
        out.append((c,result))
        if not result.ok:break
    ctx.app.last_acts = out
    text=merge_replies([r.plain for _, r in out])
    if len(out)<len(last):text+=f' Stopped after {len(out)-1} of {len(last)} steps, sir.'
    return Result(all(r.ok for _, r in out), text, {"count": len(out)})


@ability("undo", "undo the last thing", phrases={p: {} for p in ("undo", "undo that", "take that back", "undo it", "scratch that", "undo last action", "undo the last action")})
def undo(args, ctx):
    if hasattr(ctx.app,'ledger'):
        ok,text=ctx.app.ledger.undo(ctx.store)
        if ok:ctx.app.last_acts=[]
        return Result(ok,text,exact=True)
    last = [r for _, r in ctx.app.last_acts if r.undo]
    if not last:
        return Result(False, "There's nothing I can undo, sir.")
    out = [r.undo() for r in reversed(last)]
    ctx.app.last_acts=[]
    return Result(all(r.ok for r in out), merge_replies([r.plain for r in out]))


@ability("recap", "say what was just done", phrases={p: {} for p in ("what did you just do", "what was that", "what did you do", "what have you just done")})
def recap(args, ctx):
    h = [x for x in ctx.app.history if x["ability"]]
    if not h:
        return Result(True, "I haven't done anything yet, sir.", exact=True)
    return Result(True, "A moment ago I did this: " + h[-1]["reply"].replace(", sir.", "") + ", sir.", exact=True)
