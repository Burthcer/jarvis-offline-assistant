"""Core checks with a fake PC and a scripted 'AI' (no model needed): instant route, parse, guards, abilities, questions, failures.
Run: py -3.12 tests/v2/test_core.py   -> prints failures only, then a count."""
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(HERE)), HERE]
from harness import CLOCK, Speech, fresh  # noqa: E402
from gold_text import ALL  # noqa: E402

from jarvis2 import understand  # noqa: E402
from jarvis2.registry import ABILITIES  # noqa: E402

FAILS, N = [], 0


class Script:
    """Stands in for the AI: returns what the test says for a sentence, and counts calls."""

    def __init__(self, **out):
        self.out, self.calls = out, 0

    def complete(self, msgs, temperature=0.0, max_tokens=90):
        self.calls += 1
        text = msgs[-1]["content"].split("]\n", 1)[-1]
        o = self.out[text]
        return o[min(self.calls - 1, len(o) - 1)] if isinstance(o, list) else o


def check(name, cond, info=""):
    global N
    N += 1
    if not cond:
        FAILS.append(f"{name} {info}")


def say(ai, text, setup=None):
    app, os_, store = fresh(ai)
    if setup:
        setup(os_, store)
    return app, os_, store, app.handle(text)


# ----- instant route: no AI at all -----
app, os_, store, r = say(None, "open youtube")
check("open youtube", r.plan.source == "shape" and ("open", "youtube", "site", 1, None) in os_.log and r.text == "Done, sir.", (r.text, os_.log))
app, os_, store, r = say(None, "Hey Jarvis, close edge, chrome and discord")
check("close three", [x[1] for x in os_.log if x[0] == "close"] == ["edge", "chrome", "discord"] and r.text == "Done, sir.", (r.text, os_.log))
app, os_, store, r = say(None, "clues discord")
check("misheard verb goes to the AI, not guessed", r.plan.source == "ai" and not os_.log, r.plan)
app, os_, store, r = say(None, "pause")
check("pause", ("media", "pause") in os_.log and r.text == "Done, sir." and os_.playing["playing"] is False, r.text)
app, os_, store, r = say(None, "play", lambda o, s: setattr(o, "playing", None))
check("nothing playing is a failure, said plainly", not r.ok and "Nothing is playing" in r.text, r.text)
app, os_, store, r = say(None, "volume 70")
check("volume 70", os_.vol == 70 and r.text == "Volume set to 70 percent, sir.", (os_.vol, r.text))
app, os_, store, r = say(None, "volume up")
check("volume up +10", os_.vol == 60, os_.vol)
app, os_, store, r = say(None, "mute")
check("mute", os_.mute and r.text == "Muted, sir.", r.text)
app.handle("mute")
check("mute twice", app.history[-1]["reply"] == "Already muted, sir.")
app, os_, store, r = say(None, "shut the fuck up")
check("stop talking is silent and stops speech", r.text == "" and app.speech.stopped == 1 and r.ok, r.text)

# ----- the scripted AI: parse, guards, abilities -----
ai = Script(**{"keep a ten second timer": 'timer_set(duration="ten second")', "one more": 'timer_set(duration="1 minute")',
               "kill my timer": 'timer_control(action="cancel")', "hold the one minute one": 'timer_control(action="pause", which="1 minute")',
               "wipe every timer": 'timer_control(action="cancel", which="all")', "how long is left": 'timer_control(action="status")',
               "tell a joke": "CHAT: I'm afraid I only know the one, sir.", "do it": "CHAT: Done, sir.",
               "open prome": 'open(target="prome")', "open a thing": 'open(target="spotify")', "explode": 'self_destruct(now=True)',
               "weird youtube": ["open(", 'open(target="youtube")'], "bad value": 'media(action="eject")', "no arg": "open()",
               "set a timer": 'timer_set(duration="soon")', "change the volume of youtube": 'volume(action="set", app="youtube")',
               "stuff": 'open(target="youtube", count=99)'})
app, os_, store, r = say(ai, "keep a ten second timer")
check("timer set", r.text == "Timer set: 10 second timer, sir." and any(t["text"] == "10-second" for t in store.all_timers()), r.text)
app.handle("keep a ten second timer") if False else None
app, os_, store, r = say(ai, "kill my timer")
check("cancel with two timers asks which", r.plan.kind == "ask" and "Which timer, sir" in r.text and len(store.all_timers()) == 2, r.text)
app, os_, store, r = say(ai, "hold the one minute one")
check("pause by length", r.text == "1 minute timer paused, sir." and [t["status"] for t in store.all_timers()].count("paused") == 1, r.text)
app, os_, store, r = say(ai, "wipe every timer")
check("cancel all", r.text == "Both timers cancelled, sir." and not store.all_timers(), r.text)
app, os_, store, r = say(ai, "how long is left")
check("status lists, exact", "1 minute timer" in r.text and "3 minute timer" in r.text and r.results[0][1].exact, r.text)
app, os_, store, r = say(ai, "set a timer")
check("timer with no clear length asks how long", r.plan.kind == "ask" and r.text == "How long, sir?", r.text)
app, os_, store, r = say(ai, "tell a joke")
check("chat", r.plan.kind == "chat" and not os_.log)
app, os_, store, r = say(ai, "do it")
check("chat may not claim an action", "haven't done anything" in r.text, r.text)
app, os_, store, r = say(ai, "open a thing")
check("name the user never said is refused", r.plan.kind == "ask" and not os_.log, (r.text, os_.log))
app, os_, store, r = say(ai, "explode")
check("unknown ability: parse fails, retried, asks to repeat, logged", r.plan.kind == "ask" and "again" in r.text and r.plan.error.startswith("parse"), r.plan)
app, os_, store, r = say(ai, "weird youtube")
check("parse failure then good retry", ("open", "youtube", "site", 1, None) in os_.log)
for t in ("bad value", "no arg", "stuff"):
    app, os_, store, r = say(ai, t)
    check("strict parse: " + t, r.plan.kind == "ask" and not os_.log and r.plan.error.startswith("parse"), (r.plan.kind, r.plan.error))
app, os_, store, r = say(ai, "change the volume of youtube")
check("one app, no direction: asks", r.text == "Louder or quieter, sir?" and os_.app_vol["edge"] == 100, r.text)

# ----- a question, then yes -----
app, os_, store, r = say(ai, "open prome")
if r.plan.kind == "ask" and r.plan.pending:
    r2 = app.handle("yes")
    check("do you mean X? yes", os_.log and os_.log[-1][0] == "open", (r.text, r2.text, os_.log))
else:
    check("open prome asks or resolves", r.plan.kind == "act" and os_.log, (r.text, r.plan))
app, os_, store, r = say(ai, "open prome")
if r.plan.pending:
    app.handle("no")
    check("do you mean X? no", not os_.log)

# ----- failures are said, not hidden -----
app, os_, store, r = say(None, "open discord", lambda o, s: o.fail.add("discord"))
check("a failed open is ok=False and says so", not r.ok and r.text == "I couldn't open Discord, sir.", r.text)
app, os_, store, r = say(None, "close edge", lambda o, s: o.fail.add("edge"))
check("a close that doesn't stick is ok=False", not r.ok, r.text)

# ----- the registry and prompt -----
check("stop_talking hidden from the AI", "stop_talking" not in understand.system_prompt() and "timer_set" in understand.system_prompt())
gold = {t.lower() for t, _, _ in ALL}
check("no example or shot is a gold sentence", not [u for u, _ in understand.shots() if u.split("]\n")[-1].lower() in gold], [u for u, _ in understand.shots() if u.split("]\n")[-1].lower() in gold])
check("registry", {"open", "close", "focus", "volume", "media", "timer_set", "timer_control", "stop_talking"} <= set(ABILITIES))
check("every ability has at most 2 examples", all(len(a.examples) <= 2 for a in ABILITIES.values()))

print("FAILED:" if FAILS else "all ok", *FAILS, sep="\n")
print(f"{N - len(FAILS)}/{N} checks")
sys.exit(1 if FAILS else 0)
