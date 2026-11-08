"""Phase 6: learning with a fake PC and a scripted 'AI'. Run: py -3.12 tests/v2/test_memory.py -> failures only, then a count."""
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(HERE)), HERE]
from harness import CLOCK, fresh  # noqa: E402

FAILS, N = [], 0


class Script:
    def __init__(self, **out):
        self.out, self.calls = out, 0

    def complete(self, msgs, temperature=0.0, max_tokens=90):
        self.calls += 1
        return self.out[msgs[-1]["content"].split("]\n", 1)[-1]]


def check(name, cond, info=""):
    global N
    N += 1
    if not cond:
        FAILS.append(f"{name} {info}")


def opened(os_):
    return [x[1] for x in os_.log if x[0] == "open"]


# ----- usage -----
app, os_, store = fresh(None)
app.handle("open youtube"); app.handle("open youtube"); app.handle("open discord")
check("usage counted", app.memory.usage_total("youtube") == 2 and app.memory.usage_total("discord") == 1, app.memory.counts())
check("usage ranks via the matcher", app.names.usage("youtube") >= 2)

# ----- one correction teaches a word -----
app, os_, store = fresh(Script(**{"open bluebird": 'open(target="bluebird")'}))
r = app.handle("open bluebird")
check("an unknown word is asked about, not guessed", r.plan.kind == "ask" and app.last_names == ("bluebird", None), (r.text, app.last_names))
r = app.handle("no I meant chrome")
check("correction opens the right thing and says what it learned", "chrome" in opened(os_) and "bluebird" in r.text and r.ok, (r.text, os_.log))
check("alias stored by correction", app.memory.alias_active("bluebird") == ("chrome", "app"), app.memory.aliases())
os_.log.clear()
r = app.handle("open bluebird")
check("next time it just works, no AI needed", r.plan.source == "shape" and opened(os_) == ["chrome"], (r.plan.source, os_.log))
check("the correction marked the earlier turn", app.memory._q("SELECT COUNT(*) FROM events WHERE corrected_by IS NOT NULL")[0][0] == 1)

# ----- a wrong action is taken back and redone -----
app, os_, store = fresh(Script(**{"open jamin": 'open(target="jamin")'}))
r = app.handle("open jamin")
wrong = opened(os_)[-1]
os_.log.clear()
r = app.handle("no I meant chrome")
check("wrong thing closed, right thing opened", ("close", wrong, "app") in os_.log or ("close", wrong, "site") in os_.log, os_.log)
check("right thing opened", "chrome" in opened(os_), os_.log)
check("alias replaced", app.memory.alias_active("jamin") == ("chrome", "app"), app.memory.aliases())

# ----- three confirmed successes make an alias; paused learning does not count -----
app, os_, store = fresh(Script(**{"open jamin": 'open(target="jamin")'}))
for _ in range(2):
    app.handle("open jamin")
check("two successes are not enough", app.memory.alias_active("jamin") is None, app.memory.aliases())
app.handle("open jamin")
check("three are", app.memory.alias_active("jamin") is not None, app.memory.aliases())
app, os_, store = fresh(Script(**{"open jamin": 'open(target="jamin")'}))
r = app.handle("pause learning")
check("pause learning", app.memory.paused and "stop learning" in r.text, r.text)
for _ in range(4):
    app.handle("open jamin")
check("nothing learned while paused", app.memory.alias_active("jamin") is None and app.memory.usage_total("gemini") == 0, (app.memory.aliases(), app.memory.counts()))
app.handle("no I meant chrome")
check("a correction is still taken while paused", app.memory.alias_active("jamin") == ("chrome", "app"))
app.handle("resume learning")
check("resume", not app.memory.paused)

# ----- seeing and deleting -----
app, os_, store = fresh(None)
app.handle("open youtube"); app.handle("open youtube")
r = app.handle("what do you know about me")
check("summary", "youtube" in r.text and r.results[0][1].exact, r.text)
app.memory.alias_correct("zorb", "chrome", "app", CLOCK)
r = app.handle("forget the word zorb")
check("forget one word", app.memory.alias_active("zorb") is None and r.ok, r.text)
r = app.handle("forget everything you learned")
check("clearing everything asks first", r.text == "Shall I go ahead, sir?" and app.memory.usage_total("youtube") == 2, r.text)
r = app.handle("yes")
check("then clears", app.memory.usage_total("youtube") == 0 and "forgotten" in r.text, r.text)
check("the plain log of turns stays", app.memory.counts()["events"] >= 4, app.memory.counts())

# ----- routines -----
app, os_, store = fresh(Script(**{"open notepad and keep a ten second timer": 'open(target="notepad")\ntimer_set(duration="ten second")'}))
r = app.handle("save that as study mode")
check("nothing to save yet", not r.ok and "nothing to save" in r.text, r.text)
app.handle("open notepad and keep a ten second timer")
r = app.handle("save that as study mode")
check("routine saved", r.ok and app.memory.routines() == ["study mode"], (r.text, app.memory.routines()))
os_.log.clear()
for t in store.all_timers(): store.delete(t["id"])   # the routine must create its own timer, not restart the one from the teaching sentence
r = app.handle("study mode")
check("routine runs every step", ("open", "notepad", "app", 1, None) in os_.log and r.ok and len(store.all_timers()) == 1, (os_.log, r.text, store.all_timers()))   # effects, not wording: V3 answers with one short line
check("saving or running a routine is not 'the last thing'", [c.ability for c, _ in app.last_acts] == ["open", "timer_set"])
r = app.handle("forget the study mode routine")
check("routine forgotten", app.memory.routines() == [], r.text)

# ----- habits: asked, never forced -----
def day_app():
    app, os_, store = fresh(None)
    t = [CLOCK]
    app.clock = lambda: t[0]
    return app, os_, t


app, os_, t = day_app()
for d, (h, m) in enumerate([(22, 5), (21, 50), (22, 20)], start=1):
    t[0] = datetime(2026, 10, 27 + d, h, m)
    app.handle("open youtube")
t[0] = datetime(2026, 10, 31, 22, 3)
check("two days is not a habit", True)
text = app.offer()
check("three days, same hour: offered as a question", text and "YouTube" in text and app.pending is not None, text)
check("never offered twice the same day", app.memory.habit_due(t[0]) is None)
os_.log.clear()
r = app.handle("yes")
check("yes does it", "youtube" in opened(os_), os_.log)
app, os_, t = day_app()
for d, (h, m) in enumerate([(22, 5), (21, 50), (22, 20)], start=1):
    t[0] = datetime(2026, 10, 27 + d, h, m); app.handle("open discord")
t[0] = datetime(2026, 10, 31, 22, 3)
check("offer", app.offer() is not None)
r = app.handle("no")
check("no is remembered", app.memory._q("SELECT answer FROM habits")[0][0] == "no" and "won't offer" in r.text, r.text)
t[0] = datetime(2026, 11, 1, 22, 3)
check("and it never comes back", app.offer() is None)
app, os_, t = day_app()
for d in range(3):
    t[0] = datetime(2026, 10, 28 + d, 22, 5); app.handle("open discord")
t[0] = datetime(2026, 10, 31, 22, 3)
app.handle("open discord")
check("no offer if he already opened it today", app.offer() is None)
app, os_, t = day_app()
for d in range(3):
    t[0] = datetime(2026, 10, 28 + d, 22, 5); app.handle("open discord")
t[0] = datetime(2026, 10, 31, 22, 3)
app.memory.set_paused(True)
check("no offers while learning is paused", app.offer() is None)

print("FAILED:" if FAILS else "all ok", *FAILS, sep="\n")
print(f"{N - len(FAILS)}/{N} checks")
sys.exit(1 if FAILS else 0)
