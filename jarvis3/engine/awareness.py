"""The awareness snapshot (plan 13.6), built fresh for each turn. Phase 2 has: now, apps, front, playing, timers, last, mentioned.
Reminders, notes, tabs and profile come with their phases."""
import logging
import re

from datetime import datetime

from jarvis3.legacy.actions import _left
from jarvis3.legacy.timeparse import fmt

log = logging.getLogger("jarvis3.engine")


def build(os, store, catalog, now, history, mentioned, media=True, running=None):
    try:
        playing = os.media_state() if media else None
    except Exception:
        log.exception("media_state failed")  # shown in the log, never silent; the turn goes on without it
        playing = None
    timers = [{"length": r["text"].replace("-", " "), "left": _left(r["due"], now) if r["status"] == "open" else f"{r['left_s'] or 0} seconds", "state": "paused" if r["status"] == "paused" else "running"}
              for r in store.all_timers()]
    reminders = [{"text": r["text"], "due": fmt(datetime.fromisoformat(r["due"]), now)} for r in store.upcoming(now, 8)]
    notes = [r["text"].split(" is ")[0][:40] for r in store.notes("")][:8]            # only what each note is about, never its content
    return {"now": now, "apps": sorted(os.running_names(catalog) if running is None else running), "front": os.front(), "playing": playing, "timers": timers, "reminders": reminders, "notes": notes,
            "last": history[-3:], "mentioned": dict(mentioned)}


TIMER_WORDS = re.compile(r"\b(pause|resume|cancel|stop|hold|left|remaining|which|both|all|them|it|that|first|second|last|delete|kill|wipe|clear|status|going)\b", re.I)
REM_WORDS = re.compile(r"(remind|reminder|reminders|cancel|change|move|edit|delete|list|due|today|tomorrow|yesterday|schedule|missed|miss|have)", re.I)
NOTE_WORDS = re.compile(r"(my|note|notes|remember|forget|email|gmail|number|code|password|what's|what|where)", re.I)
PLAY_WORDS = re.compile(r"\b(pause|play|playing|next|previous|skip|song|video|music|resume|stop|it|that)\b", re.I)


def short(snap, text=""):
    """The few lines that go into the prompt (the changing part, put last so the fixed part stays cached)."""
    now = snap["now"]
    parts = [f"Now: {now.strftime('%A')} {now.day} {now.strftime('%B %Y, %H:%M')}.", "Running: " + (", ".join(snap["apps"]) or "nothing") + "."]
    if snap["playing"] and PLAY_WORDS.search(text):
        p = snap["playing"]
        parts.append(f"Playing: {p['title']} ({'playing' if p['playing'] else 'paused'}).")
    if snap["timers"] and TIMER_WORDS.search(text):  # shown only when the sentence could be about them: a running list pushed "ten minute timer" into "pause"
        parts.append("Timers: " + ", ".join(t["length"] + ("" if t["state"] == "running" else " (paused)") for t in snap["timers"]) + ".")
    if snap.get("reminders") and REM_WORDS.search(text):
        parts.append("Reminders: " + ", ".join(f"{r['text']} ({r['due']})" for r in snap["reminders"]) + ".")
    if snap.get("notes") and NOTE_WORDS.search(text):
        parts.append("Notes: " + ", ".join(snap["notes"]) + ".")
    if snap["mentioned"].get("app"):
        parts.append(f"Last app mentioned: {snap['mentioned']['app']}.")
    return " ".join(parts)
