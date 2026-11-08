"""timer_set, timer_control: timers live in V1's Store (kind 'timer'), so the old window and alerts keep working."""
import re
from datetime import timedelta

from jarvis.actions import _left, label_secs

from ..registry import Ask, Choice, Duration, Result, Which, ability

MAX = 24 * 3600


def say(r):
    return r["text"].replace("-", " ") + " timer"


def done(rows, what):
    return f"{say(rows[0]).capitalize()} {what}, sir." if len(rows) == 1 else ("Both timers " if len(rows) == 2 else f"All {len(rows)} timers ") + f"{what}, sir."


@ability("timer_set", "start one timer; duration = the user's words. Several timers: several calls",
         required={"duration": Duration()}, examples=[("keep a ten second timer", 'timer_set(duration="ten second")')])
def timer_set(args, ctx):
    secs = args["duration"]
    if secs > MAX:
        return Result(False, "Timers go up to 24 hours, sir. For longer, set a reminder.", {})
    h, m, s = secs // 3600, secs % 3600 // 60, secs % 60
    label = " and ".join(f"{v}-{u}" for v, u in ((h, "hour"), (m, "minute"), (s, "second")) if v)
    row, merged = ctx.store.add(label, ctx.now + timedelta(seconds=secs), kind="timer")
    return Result(True, f"{'Restarted the' if merged else 'Timer set:'} {label.replace('-', ' ')} timer, sir.", {"seconds": secs, "restarted": merged},
                  undo=None if merged else lambda: (ctx.store.delete(row["id"]), Result(True, "Timer removed, sir."))[1])


@ability("timer_control", "existing timers. which = its length in the user's words, or 'all' (all, both, every). Leave which out if none named",
         required={"action": Choice("pause", "resume", "cancel", "status", evidence={
             "pause": r"pause|hold|freeze|stop|wait", "resume": r"resume|continue|unpause|restart|start|go on|again|unfreeze",
             "cancel": r"cancel|stop|delete|remove|kill|clear|wipe|end|drop|get rid|forget|reset|abort"})}, optional={"which": Which()},
         examples=[("hold the forty second timer", 'timer_control(action="pause", which="forty second")'), ("wipe all timers", 'timer_control(action="cancel", which="all")')])
def timer_control(args, ctx):
    act, which, st = args["action"], args.get("which"), ctx.store
    pool = {"cancel": st.all_timers, "pause": st.timers, "status": st.timers, "resume": lambda: [r for r in st.all_timers() if r["status"] == "paused"]}[act]()
    if which and which != "all":
        rows = [r for r in pool if label_secs(r["text"]) == int(which)]
        if not rows:
            return Result(False, f"You have no timer of that length to {act}, sir." if act != "status" else "You have no timer of that length, sir.", {})
    elif which == "all" or len(pool) <= 1 or act == "status" or re.search(r"\b(both|all|every|each)\b", ctx.text.lower()):
        rows = pool
    else:
        raise Ask("Which timer, sir: " + " or ".join("the " + r["text"].replace("-", " ") for r in pool) + "?")
    if act == "status":
        if not rows:
            return Result(True, "You have no timers running, sir.", {}, exact=True)
        return Result(True, "\n".join(f"{r['text'].replace('-', ' ')} timer, {_left(r['due'], ctx.now)} left" for r in rows), {"count": len(rows)}, exact=True)
    if not rows:
        return Result(True, "No timer is paused, sir." if act == "resume" else "You have no timers running, sir.", {"changed": False})
    for r in rows:
        {"cancel": lambda r: st.delete(r["id"]), "pause": lambda r: st.pause_timer(r["id"], ctx.now), "resume": lambda r: st.resume_timer(r["id"], ctx.now)}[act](r)
    return Result(True, done(rows, {"cancel": "cancelled", "pause": "paused", "resume": "running again"}[act]), {"count": len(rows)})
