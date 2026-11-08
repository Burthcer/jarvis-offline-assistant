"""Skills taught by voice, and the wish list. A skill is a routine (learn.py) whose steps are the owner's own sentences ({"a": "say", "args": {"text": ...}}); when it runs, each sentence goes through the
same resolver and the same safe abilities as if he had said it, so no rail is bypassed. The wish list is a text file Claude reads in a later session: Jarvis NEVER edits its own code.
Neither is offered to the AI (no `says`): they must be asked for plainly."""
import os
import re

from .. import understand
from ..registry import ABILITIES, Result, Text, ability

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAX_STEPS = 8
# never inside a skill: skills themselves, wishes, things that need a fresh yes each time, and "the last thing" helpers
NOT_IN_SKILL = {"routine_run", "routine_resume", "routine_save", "routine_forget", "skill_teach", "wish_add", "wish_list", "send_to_app", "ui_click", "ui_type", "ui_press",
                "correction", "undo", "repeat", "recap", "learned_clear", "learning", "forget_alias", "shut_down"}
VERBS = ("open|close|focus|start|set|play|pause|mute|unmute|take|search|google|remind|turn|launch|stop|resume|cancel|volume|increase|decrease|lower|raise|"
         "what|read|tell|save|remember|note|switch|go|show|make|keep|skip|next|previous|screenshot|ask|send|message|type|click|press|write|shut|quit|exit")
SPLIT = re.compile(rf"\s+and then\s+|\s+then\s+|\s+and\s+(?=(?:{VERBS})s?\b)")
THIRD = re.compile(r"^(open|close|focus|start|set|play|pause|mute|unmute|take|search|remind|launch|stop|resume|cancel|show|read|tell|turn|switch)s\b")      # "a skill that opens notepad"
WHEN = rf"when i say (.+?) (?:you should |you can |you will |you |then |to )?((?:{VERBS}) .+)"
LEARN = r"(?:learn|create|make|add|teach yourself) (?:a |the )?(?:new )?skill (?:called |named |for )?(.+?) (?:that|to|which|that will|which will) (.+)"


def _requests_path():
    return os.environ.get("JARVIS_REQUESTS") or os.path.join(ROOT, "data", "requests.md")


def _check_step(piece, ctx):
    """One sentence of a skill -> None if it is fine, else why not (plain words)."""
    names, app = ctx.app.names, ctx.app
    hit = understand.instant(piece, names, app._routine_phrases())
    plan = None
    if hit:
        calls = [a for a, _ in hit[1]]
    else:
        if app.ai is None:
            return f"I can't tell what '{piece}' means without my thinking part"
        plan = understand.resolve(piece, ctx.snapshot, names, app.ai, ctx.now, False, app._routine_phrases())
        if plan.kind != "act":
            return f"I couldn't tell what '{piece}' means"
        calls = [c.ability for c in plan.calls]
    for name in calls:
        if name in NOT_IN_SKILL:
            return f"I can't keep '{piece}' in a skill, because it needs your yes each time or is about skills themselves"
        if ABILITIES[name].risk != "safe":
            return f"I can't keep '{piece}' in a skill, because it needs your yes"
    return None


@ability("skill_teach", None, required={"name": Text(), "steps": Text()},
         patterns=[(WHEN, lambda m: {"name": m[1].strip(), "steps": m[2].strip()}), (LEARN, lambda m: {"name": m[1].strip(), "steps": m[2].strip()})])
def skill_teach(args, ctx):
    name = args["name"].lower().strip()
    if not name or len(name.split()) > 6 or len(name) > 40:
        return Result(False, "That name is too long for me to keep, sir. Please use a short one.")
    if re.fullmatch(VERBS, name):
        return Result(False, f"'{name}' is one of my command words, sir. Please pick another name.")
    pieces = [THIRD.sub(r"\1", p.strip()) for p in SPLIT.split(args["steps"]) if p.strip()]
    if not pieces:
        return Result(False, "What should I do, sir?")
    if len(pieces) > MAX_STEPS:
        return Result(False, f"That's more than {MAX_STEPS} steps, sir. Please make it shorter.")
    owner = understand.instant(name, ctx.app.names, None)           # the name must not already be a phrase Jarvis knows (a fuzzy "focus <app>" guess does not count: his own phrase is checked first)
    if owner and owner[0] == "phrase" and name not in ctx.memory.routines():
        return Result(False, f"'{name}' already means something to me, sir. Please pick another name.")
    for p in pieces:
        why = _check_step(p, ctx)
        if why:
            return Result(False, why + ", sir. Nothing was saved.")
    ctx.memory.routine_save(name, [{"a": "say", "args": {"text": p}} for p in pieces], ctx.now)
    return Result(True, f"Learned, sir. When you say '{name}', I'll " + ", then ".join(pieces) + ".", {"steps": len(pieces)}, exact=True)


# ---------- the wish list ----------
@ability("wish_add", None, required={"text": Text()},
         patterns=[(r"(?:i wish you could|add a feature|add a feature to|learn to|you should be able to|i want you to be able to) (.+)", lambda m: {"text": m[1].strip()})])
def wish_add(args, ctx):
    text = args["text"].strip()[:200]
    path = _requests_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
    if f"] {ctx.now:%Y-%m-%d} {text}\n" in old + "\n" or any(l.endswith(" " + text) and l.startswith("- [ ]") for l in old.splitlines()):
        return Result(True, "That's already on my list, sir.", exact=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"- [ ] {ctx.now:%Y-%m-%d} {text}\n")
    return Result(True, "Noted on my wish list, sir. I can't change myself, but it's written down for my next update.", {"text": text}, exact=True)


@ability("wish_list", None, phrases={p: {} for p in ("what is on your wish list", "read your wish list", "what do i wish for", "what have i asked you to learn", "what features have i asked for",
                                                      "read my requests", "what are my requests")})
def wish_list(args, ctx):
    path = _requests_path()
    items = [l[6:].split(" ", 1)[-1] for l in (open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []) if l.startswith("- [ ]")]
    if not items:
        return Result(True, "My wish list is empty, sir.", exact=True)
    shown = items[-3:]
    more = f" That's the last {len(shown)} of {len(items)}." if len(items) > len(shown) else ""
    return Result(True, f"You have {len(items)} on my list, sir: " + "; ".join(shown) + "." + more, {"count": len(items)}, exact=True)
