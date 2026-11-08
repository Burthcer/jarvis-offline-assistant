"""Learning, in his hands (plan 4.7): a correction teaches a word at once, he can see and delete everything, learning can be paused, and a routine is what he saves from his own last
sentence. None of these is offered to the AI (no `says`): they act on Jarvis's memory, so they must be asked for plainly."""
import json
import re

from ..names import clean
from ..registry import ABILITIES, Bool, Name, Result, Text, ability


def _plain_args(args):
    """Only plain values can be stored in a routine (a time or a name object cannot)."""
    try:
        json.dumps(args)
        return True
    except TypeError:
        return False


def _from_last_sentence(app):
    """The last thing he said was '<open/close/focus> <something Jarvis could not place>': what he meant is that something. Sets app.last_verb."""
    app.last_verb = None
    if not app.history:
        return None
    said = app.history[-1]["said"].lower().strip(" .,!?")
    said = re.sub(r"^(?:(?:hey|ok|okay)\s+)?jarvis[, ]*|^(?:please|can you|could you)\s+", "", said)
    for ab in ABILITIES.values():
        for v in sorted(ab.verbs, key=len, reverse=True):
            if said.startswith(v + " ") and "target" in ab.required and not v.startswith(("no ", "i ")):
                rest = said[len(v):].strip()
                if 1 <= len(rest.split()) <= 4:
                    app.last_verb = ab.name
                    return clean(rest), None
    return None


# ---------- "no, I meant Chrome" ----------
@ability("correction", None, required={"target": Name()},
         verbs=("no i meant", "i meant", "no i said", "i said", "i mean", "no i mean", "no it was", "no it is", "not that i meant", "no the"))
def correction(args, ctx):
    from ..app import Ctx  # noqa: F401
    from .. import understand
    app, new = ctx.app, args["target"]
    pair = app.last_names or _from_last_sentence(app)
    if not pair:
        return Result(False, "I'm not sure what I got wrong, sir.")
    heard, wrong = pair
    ctx.memory.alias_correct(heard, new, ctx.kind(new), ctx.now)      # learned at once, even while learning is paused: he said it outright
    ctx.memory.mark_corrected(app.last_event, ctx.memory.next_id())
    for c, r in app.last_acts:                                          # take the wrong action back first
        if wrong and (c.args.get("target") == wrong or c.args.get("app") == wrong or c.args.get("site") == wrong) and r.undo:
            r.undo()
    plan = app.last_plan
    done = []
    src = ([(c.ability, c.spoken) for c in plan.calls] or plan.raw) if plan and app.last_names else None      # the words as he said them
    if not src and app.last_verb:                                         # the AI could not use the sentence ("open bluebird"): redo it with the right name
        src = [(app.last_verb, {"target": heard})]
    if src:
        raw = [(a, {k: (new if isinstance(v, str) and clean(v) == heard else v) for k, v in ar.items()}) for a, ar in src]
        env = understand.Env(ctx.text, app.names, ctx.now, followup=True)
        for call in understand.convert(raw, env):
            res = ABILITIES[call.ability].fn(call.args, ctx)
            done.append((call, res))
        app.last_acts = done or app.last_acts
    from .apps import pretty
    said = f"Understood, sir. When you say '{heard}', I'll take it as {pretty(new)}."
    ok = all(r.ok for _, r in done)
    return Result(ok, said + ("" if not done else " " + " ".join(r.plain for _, r in done)), {"heard": heard, "name": new}, exact=True)


@ability("forget_alias", None, required={"heard": Text()}, patterns=[(r"(?:forget|unlearn) the word (.+)", lambda m: {"heard": m[1].strip()})])
def forget_alias(args, ctx):
    n = ctx.memory.alias_delete(clean(args["heard"]))
    return Result(bool(n), f"I've forgotten what '{args['heard']}' meant, sir." if n else f"I hadn't learned '{args['heard']}', sir.")


@ability("learned_clear", None, risk="confirm",
         phrases={p: {} for p in ("forget everything you learned", "forget everything you have learned", "forget everything you learned about me", "delete what you know about me",
                                  "clear what you learned", "reset your memory of me", "forget what you know about me")})
def learned_clear(args, ctx):
    n = ctx.memory.clear_learned()
    return Result(True, f"Done, sir. I've forgotten {n} thing{'s' if n != 1 else ''} I had learned.", {"count": n})


@ability("knowledge_summary", None, phrases={p: {} for p in ("what do you know about me", "what have you learned", "what did you learn about me", "tell me what you know about me",
                                                              "what have you learned about me", "what do you know")})
def knowledge_summary(args, ctx):
    from ..organizer import rows
    notes = [r['text'] for r in ctx.store.notes("") if not re.search(r'password|secret|pin\b', r['text'], re.I)]
    events = [r['title'] + (' on ' + r['happens'][:10] if r['happens'] else '') for r in rows(ctx.memory, 'commitments') if r['status'] == 'active'][:5]
    return Result(True, ("You told me: " + "; ".join(notes[:8]) + ". " if notes else "") + ("Your events: " + "; ".join(events) + ". " if events else "") + ctx.memory.summary(ctx.now), exact=True)


@ability("learning", None, required={"on": Bool()},
         phrases={**{p: {"on": False} for p in ("pause learning", "stop learning", "stop learning about me", "don't learn", "turn off learning")},
                  **{p: {"on": True} for p in ("resume learning", "start learning", "continue learning", "turn on learning")}})
def learning(args, ctx):
    ctx.memory.set_paused(not args["on"])
    return Result(True, "Learning resumed, sir." if args["on"] else "I'll stop learning from you for now, sir. What I know stays.", {"on": args["on"]})


# ---------- routines: what he saved from his own last sentence ----------
@ability("routine_save", None, required={"text": Text()},
         patterns=[(r"(?:save|remember|keep|store) (?:that|this|those|it|the last thing)(?: as| for)?(?: my| the)? (.+?)(?: routine)?", lambda m: {"text": m[1].strip()})])
def routine_save(args, ctx):
    steps = []
    for c, r in ctx.app.last_acts:
        ab = ABILITIES[c.ability]
        if ab.risk != "safe" or not _plain_args(c.args):
            return Result(False, f"I can't keep {c.ability.replace('_', ' ')} in a routine, sir.")
        steps.append({"a": c.ability, "args": c.args})
    if not steps:
        return Result(False, "There's nothing to save yet, sir.")
    ctx.memory.routine_save(args["text"].lower(), steps, ctx.now)
    return Result(True, f"Saved, sir. Say '{args['text']}' and I'll do all {len(steps)} of them." if len(steps) > 1 else f"Saved, sir. Say '{args['text']}' and I'll do it.", {"steps": len(steps)})


@ability("routine_run", None, required={"name": Text()},
         patterns=[(r"(?:run|start|do|begin|launch) (?:the |my )?(.+?) routine", lambda m: {"name": m[1].strip()}),
                   (r"(?:run|start|do|begin|launch) (?:the |my )?routine (?:called |named )?(.+)", lambda m: {"name": m[1].strip()})])
def routine_run(args, ctx):
    from ..routine_runner import run
    return run(args['name'],ctx)


@ability("routine_close", None, required={"name": Text()},
         patterns=[(r"(?:close|stop|end|shut|quit|exit|finish) (?:the |my )?routine (?:called |named )?(.+)", lambda m: {"name": m[1].strip()}),
                   (r"(?:close|stop|end|shut|quit|exit|finish) (?:the |my )?(.+?) routine", lambda m: {"name": m[1].strip()})])
def routine_close(args, ctx):
    """Close what the routine opened: every 'open X' step becomes 'close X' through the same close ability."""
    from .. import understand
    name = args["name"].lower().strip(); steps = ctx.memory.routine_get(name)
    if not steps:
        return Result(False, f"I have no routine called {name}, sir.", exact=True)
    targets = []
    for s in steps:
        text = s["args"].get("text", "") if s["a"] == "say" else ""
        m = re.match(r"(?:open|launch|start)(?: up)? (?:the |my )?(.+)", text.strip(" .!?"), re.I)
        if m:
            targets.append(m[1].strip())
        elif s["a"] == "open" and s["args"].get("target"):
            targets.append(str(s["args"]["target"]))
    if not targets:
        return Result(False, f"The {name} routine does not open anything, so there is nothing to close, sir.", exact=True)
    closed, problems = 0, []
    for t in targets:
        hit = understand.instant("close " + t, ctx.app.names, None)
        calls = [c for c in hit[1] if c[0] == "close"] if hit else []
        if not calls:
            problems.append(t); continue
        for _, a in calls:
            r = ABILITIES["close"].fn(dict(a), ctx)
            closed += bool(r.ok)
    text = f"Closed the {name} routine, sir." if closed == len(targets) else f"Closed {closed} of {len(targets)} for the {name} routine, sir."
    if problems:
        text += " I could not work out how to close " + ", ".join(problems) + "."
    return Result(closed > 0, text, {"closed": closed, "total": len(targets)}, exact=True)


@ability('routine_resume',None,required={'name':Text()},patterns=[(r'resume (?:my )?routine (.+)',lambda m:{'name':m[1]})])
def routine_resume(args,ctx):
    from ..routine_runner import run
    return run(args['name'],ctx,resume=True)


@ability("routine_forget", None, required={"name": Text()},
         patterns=[(r"(?:forget|delete|remove) (?:the |my )?(.+?) routine", lambda m: {"name": m[1].strip()})])
def routine_forget(args, ctx):
    n = ctx.memory.routine_forget(args["name"].lower())
    return Result(bool(n), f"The {args['name']} routine is gone, sir." if n else f"I have no routine called {args['name']}, sir.")
