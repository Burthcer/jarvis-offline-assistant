"""V4 multi-step tasks on any app or site (spec part 3): observe -> act -> verify, at most 5 steps.
'Go to Discord, open the Gaming Hub server, and click the general channel':
- each step he said is run in order; steps Jarvis already understands (open an app, click X, type Y, scroll) need no model;
- a step it cannot parse goes to the local model with the numbered screen, and the model may answer with ONE action as JSON
  (CLICK n, TYPE n text, SCROLL, DONE, ASK, DISAMBIGUATE). Its number must be on the screen, typed words must be his own words;
- after every click the screen must visibly change, else the task stops; risky buttons need his yes; 'which one?' answers continue the task.
Verified clicks found by the model are remembered in the site memory, so the same step is quicker next time."""
import json
import re
import time
from dataclasses import dataclass, field

from ..registry import ABILITIES, Ask, Result, Text, ability
from ..uia import Refused, risky

MAX_STEPS = 5
SETTLE_S = .3          # wait for the screen after a click
APP_SETTLE_S = 1.5     # wait for an app to come up
APP_STEPS = {"open", "focus", "window_state"}
SPLIT = re.compile(r"\s*,\s*(?:and\s+)?(?:then\s+)?|\s+(?:and\s+)?then\s+|\s+and\s+(?=(?:click|tap|press|select|choose|open|go to|type|scroll|play|start)\b)", re.I)
NOT_TASKS = re.compile(r"(?:remind|remember|note|make a note|set a|timer|message|text|reply|tell|search|look up|google|plan|goal|learn|when i say|teach)\b", re.I)   # V3's plans and taught skills keep their own routes


@dataclass
class Task:
    goal: str
    steps: list
    done: list = field(default_factory=list)


def split(text):
    return [p.strip(" .!?") for p in SPLIT.split((text or "").strip(" .!?")) if p and p.strip(" .!?")]


def _screen_step(part):
    from .screen import route as screen_route
    from ..understand import norm
    return bool(screen_route(norm(part)) or re.match(r"(?:type|scroll)\b", part, re.I))


def route(text):
    t = re.sub(r"^(?:jarvis[,.]?\s+)?(?:please\s+)?", "", (text or "").strip(), flags=re.I)
    if NOT_TASKS.match(t):
        return None
    parts = split(t)
    if len(parts) < 2 or not any(_screen_step(p) for p in parts):
        return None
    return [("task_run", {"goal": t})]


def _sig(screen, elements):
    return (screen.page, tuple(e.identity for e in elements))


def _join(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _stop(ctx, why):
    t, ctx.app.task = ctx.app.task, None
    so_far = f"Done so far: {_join(t.done)}. " if t and t.done else ""
    why = re.sub(r",? sir\.?$", ".", why.strip())
    return Result(False, f"{so_far}{why} I stopped there, sir.", exact=True)


def _verify(ctx, screen, before, label):
    """A middle step must change the screen (the next step depends on it). The last one may not (a Like button): it gets a note instead."""
    time.sleep(SETTLE_S)
    if _sig(screen, screen.scan()) == before:
        task = getattr(ctx.app, "task", None)
        if task is not None and len(task.steps) <= 1:
            return UNCHANGED
        return f"I clicked {label}, but nothing changed on the screen."
    return True


UNCHANGED = "unchanged"


def _click(ctx, label, allow_risky):
    screen = ctx.os.ui_screen()
    if screen is None:                                        # no screen index (old test PCs): plain click, nothing to compare
        found = ctx.os.ui_target(label, (), allow_risky)
        before = None
    else:
        before = _sig(screen, screen.scan())
        found = screen.target(label, (), allow_risky)
    if found["status"] == "risky":
        raise Ask(f"The next step presses '{found['label']}', sir. Shall I go ahead?", pending={"task_confirm": True})
    if found["status"] == "ambiguous":
        from jarvis3.screen_index import speak_names
        raise Ask(f"I see {found['count']} matches for {found['label']}, sir: {speak_names(found['names'])}. Which one?", pending={"screen_choice": True})
    return True if before is None else _verify(ctx, screen, before, found["label"])


def _listing(screen, step, limit=60):
    from jarvis3.screen_index import query_words, words, _same
    elements = screen.scan()
    want = query_words(step)[0]
    hits = lambda e: sum(1 for q in want for n in words(e.name) if _same(q, n))
    ranked = sorted(range(len(elements)), key=lambda i: (-hits(elements[i]), i))[:limit]
    chosen = [elements[i] for i in sorted(ranked)]                 # keep reading order, so numbers follow the screen
    return chosen, "\n".join(f"[{i}] {e.kind.replace('Control', '')}: {e.name[:70]}" for i, e in enumerate(chosen, 1))


RULES = ("You operate the computer screen for the user, ONE small action at a time. You get the user's whole goal, the step to do now, and the "
         "numbered controls visible on the screen. Answer with ONE JSON object and nothing else, one of:\n"
         '{"action":"CLICK","n":<number>}\n{"action":"TYPE","n":<number of the text box>,"text":"<only words the user said>"}\n'
         '{"action":"SCROLL","direction":"down"}  or "up"\n{"action":"DISAMBIGUATE","n":[<number>,<number>]} when two or more fit equally\n'
         '{"action":"ASK","question":"<short question>"} when you are not sure\n{"action":"DONE"} when this step is already done.\n'
         "Only use numbers from the list. Never guess.")


def _model_step(ctx, task, step, allow_risky):
    from jarvis3.screen_index import intent_of
    screen = ctx.os.ui_screen()
    if screen is None or ctx.ai is None:
        return f"I don't know how to '{step}' on this screen, sir."
    remembered = screen._remembered(intent_of(step), allow_risky)  # a step the model already solved here before, re-checked
    if remembered and remembered["status"] == "clicked":
        return True
    elements, listing = _listing(screen, step)
    before = _sig(screen, screen.elements)
    asked = f"GOAL: {task.goal}\nDONE SO FAR: {', '.join(task.done) or 'nothing'}\nSTEP NOW: {step}\nSCREEN:\n{listing}"
    try:
        raw = ctx.ai.complete([{"role": "system", "content": RULES}, {"role": "user", "content": asked}], temperature=0.1, max_tokens=60)
        m = re.search(r"\{.*\}", raw or "", re.S)
        act = json.loads(m[0]) if m else None
    except Exception:
        act = None
    kind = str(act.get("action", "")).upper() if isinstance(act, dict) else ""
    pick = lambda n: elements[n - 1] if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= len(elements) else None
    if kind == "DONE":
        return True
    if kind == "ASK":
        ctx.app.task = None
        raise Ask(str(act.get("question") or "What should I do next, sir?")[:200])
    if kind == "SCROLL" and act.get("direction") in ("down", "up"):
        ctx.os.ui_press("page " + act["direction"])
        return True
    if kind == "DISAMBIGUATE" and isinstance(act.get("n"), list):
        options = [pick(n) for n in act["n"]]
        if len(options) >= 2 and all(options):
            screen.shortlist, screen.label, screen.allow_risky, screen.at = options[:9], step, False, screen.clock()
            screen._show()
            from jarvis3.screen_index import speak_names
            raise Ask(f"For '{step}' I see {len(options)} options, sir: {speak_names([e.name for e in options])}. Which one?", pending={"screen_choice": True})
    target = pick(act.get("n")) if kind in ("CLICK", "TYPE") else None
    if kind == "CLICK" and target is not None and target.kind == "EditControl":
        target = None                                          # a text box is for TYPE; a bare click on one is a guess (seen with the real model)
    if target is None:
        return f"I couldn't work out how to '{step}' on this screen."
    if risky(target.name) and not allow_risky:
        return f"That step would press '{target.name}', which needs your say-so. Please ask for it on its own."
    if kind == "TYPE":
        text = str(act.get("text") or "")
        if not text or text.lower() not in task.goal.lower():
            return "I was about to type words you didn't say, so I didn't."
        screen._click(target)
        ctx.os.ui_type(text)
        return True
    screen._click(target)
    done = _verify(ctx, screen, before, target.name)
    if done in (True, UNCHANGED) and screen.memory is not None:
        try:
            screen.site = screen.source.site()
            screen._learn(intent_of(step), target, {})
        except Exception:
            pass
    return done


def _run_step(ctx, task, step, allow_risky):
    from .screen import route as screen_route
    from .. import understand
    m = re.fullmatch(r"(?:type|enter) (.+?)(?: (?:in|into) (?:the )?(.+? (?:box|field|bar)))?", step, re.I)
    if m:
        if m[2]:
            done = _click(ctx, m[2], allow_risky)
            if done is not True:
                return done
        ctx.os.ui_type(m[1])
        return True
    m = re.fullmatch(r"(?:scroll|go) (down|up)( a bit| a little| a lot| more| please)?(?: (?:in|on) (?:the|this) (\w+))?", step, re.I)
    if m:
        screen = ctx.os.ui_screen()
        if screen is None:
            ctx.os.ui_press("page " + m[1].lower())
        else:
            screen.scroll(m[1].lower(), "bit" if m[2] and ("bit" in m[2] or "little" in m[2]) else "lot" if m[2] and "lot" in m[2] else "", m[3] or "")
        time.sleep(SETTLE_S)
        return True
    m = re.fullmatch(r"(?:click|tap|select|open|play|start|choose|pick)(?: on)?(?: the)? (first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last)(?: (mix|playlist|channel|video|song|result|link|one))?", understand.norm(step))
    if m and ctx.os.ui_screen() is not None:                      # 'click the second mix' inside a task: the screen index, not V3's numbered overlay
        from .screen import ORDINALS
        screen = ctx.os.ui_screen()
        before = _sig(screen, screen.scan())
        noun = m[2] if m[2] in ("mix", "playlist", "channel") else ""
        found = screen.nth(ORDINALS[m[1]], noun, "")
        if found["status"] == "risky" and not allow_risky:
            raise Ask(f"The next step presses '{found['label']}', sir. Shall I go ahead?", pending={"task_confirm": True})
        return _verify(ctx, screen, before, found["label"]) if found["status"] == "clicked" else f"I couldn't do '{step}'."
    click = screen_route(understand.norm(step))
    if click and click[0][0] == "ui_nth":
        from .screen import ui_nth
        res = ui_nth(click[0][1], ctx)
        return True if res.ok else res.plain
    if click and click[0][0] == "ui_click":
        return _click(ctx, click[0][1]["label"], allow_risky)
    hit = understand.instant(step, ctx.app.names, compound=False)
    if hit is None and re.match(r"(?:go to|switch to|bring up|launch|start) ", step, re.I):
        hit = understand.instant(re.sub(r"^(?:go to|switch to|bring up|launch|start) ", "open ", step, flags=re.I), ctx.app.names, compound=False)
    if hit and all(a in APP_STEPS for a, _ in hit[1]):
        for a, args in hit[1]:
            res = ABILITIES[a].fn(args, ctx)
            if not res.ok:
                return res.plain
        time.sleep(APP_SETTLE_S)
        return True
    return _model_step(ctx, task, step, allow_risky)


def advance(ctx, allow_risky=False):
    task = ctx.app.task
    while task and task.steps:
        step = task.steps[0]
        try:
            outcome = _run_step(ctx, task, step, allow_risky)
        except Refused as e:
            return _stop(ctx, str(e))
        allow_risky = False
        if outcome is not True and outcome != UNCHANGED:
            return _stop(ctx, outcome)
        task.done.append(step[:1].lower() + step[1:] + (" (I saw no change on the screen)" if outcome == UNCHANGED else ""))
        task.steps.pop(0)
    ctx.app.task = None
    return Result(True, f"Done, sir: {_join(task.done)}." if task and task.done else "Done, sir.", exact=True)


def step_done(ctx):
    """His 'which one?' answer clicked the current step: tick it off and carry on."""
    task = ctx.app.task
    step = task.steps.pop(0)
    task.done.append(step[:1].lower() + step[1:])
    time.sleep(SETTLE_S)
    return advance(ctx)


@ability("task_run", None, required={"goal": Text()})
def task_run(args, ctx):
    steps = split(args["goal"])
    if len(steps) > MAX_STEPS:
        return Result(False, f"That is {len(steps)} steps, sir. I do at most {MAX_STEPS} at a time, so please split it up.", exact=True)
    ctx.app.task = Task(args["goal"], steps)
    return advance(ctx)


@ability("task_continue", None, optional={"risky": Text()})
def task_continue(args, ctx):
    """After 'shall I go ahead?' about a risky step: he said yes."""
    if getattr(ctx.app, "task", None) is None:
        return Result(False, "There is no task waiting, sir.")
    return advance(ctx, allow_risky=True)
