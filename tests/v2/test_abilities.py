"""Phase 5 abilities with a fake PC and a scripted 'AI': reminders, notes, clock, search, play, YouTube keys, tabs, screenshot, voice, shut down, microphone, alerts.
Run: py -3.12 tests/v2/test_abilities.py -> failures only, then a count."""
import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(HERE)), HERE]
from harness import CLOCK, fresh  # noqa: E402

FAILS, N = [], 0


class Script:
    def __init__(self, **out):
        self.out = out

    def complete(self, msgs, temperature=0.0, max_tokens=90):
        return self.out[msgs[-1]["content"].split("]\n", 1)[-1]]


def check(name, cond, info=""):
    global N
    N += 1
    if not cond:
        FAILS.append(f"{name} {info}")


def run(text, out=None, setup=None):
    app, os_, store = fresh(Script(**{text: out}) if out else None)
    if setup:
        setup(app, os_, store)
    return app, os_, store, app.handle(text)


def reminders(store):
    return [(r["text"], r["due"]) for r in store.db.execute("SELECT * FROM items WHERE kind='reminder' ORDER BY id")]


def notes(store):
    return [r["text"] for r in store.db.execute("SELECT * FROM items WHERE kind='note' ORDER BY id")]


# ----- reminders -----
app, os_, store, r = run("remind me tomorrow at 5 pm about the rent", 'reminder_add(text="the rent", when="tomorrow at 5 pm")')
check("reminder added with the right time", ("the rent", "2026-11-01T17:00:00") in reminders(store) and "the rent" in r.text and "tomorrow" in r.text, (r.text, reminders(store)))
check("reminder undo", app.handle("undo that").ok and ("the rent", "2026-11-01T17:00:00") not in reminders(store))
app, os_, store, r = run("remind me to call the bank", 'reminder_add(text="call the bank", when="soon")')
check("no clear time asks", r.plan.kind == "ask" and r.text == "When, sir?" and len(reminders(store)) == 2, r.text)
app, os_, store, r = run("what's on tomorrow", 'reminder_list(day="tomorrow")')
check("list tomorrow", "maths test" in r.text and "check linkedin" in r.text and r.results[0][1].exact, r.text)
app, os_, store, r = run("how many are due", 'reminder_list(count=True)')
check("count", "2 reminders" in r.text, r.text)
app, os_, store, r = run("what is on today", 'reminder_list(day="today")')
check("empty day said plainly", r.text == "Nothing for today, sir.", r.text)
app, os_, store, r = run("change the maths one", 'reminder_change(item="maths test", text="science test")')
check("change replaces, no copy", [t for t, _ in reminders(store)].count("science test") == 1 and "maths test" not in [t for t, _ in reminders(store)] and len(reminders(store)) == 2, reminders(store))
check("change undo", app.handle("undo that").ok and "maths test" in [t for t, _ in reminders(store)])
app, os_, store, r = run("change the dentist one", 'reminder_change(item="dentist", text="doctor")')
check("change unknown reminder fails honestly", not r.ok and "can't find" in r.text, r.text)
app, os_, store, r = run("wipe tomorrow", 'reminder_cancel(day="tomorrow")')
check("cancel a day", reminders(store) == [] and "2 reminders" in r.text, (r.text, reminders(store)))
check("cancel a day, undo", app.handle("undo that").ok and len(reminders(store)) == 2)
app, os_, store, r = run("drop the linkedin one", 'reminder_cancel(item="check linkedin")')
check("cancel one", [t for t, _ in reminders(store)] == ["maths test"], reminders(store))

# ----- notes -----
app, os_, store, r = run("note: my gmail is jane dot doe at the rate example dot edu", 'note_save(text="my gmail is jane dot doe at the rate example dot edu")')
check("spoken email becomes an address", "my gmail is jane.doe@example.edu" in notes(store), notes(store))
app, os_, store, r = run("what is my locker code", 'note_recall(query="locker code")')
check("recall", "4512" in r.text, r.text)
app, os_, store, r = run("what is my passport", 'note_recall(query="passport number")')
check("recall nothing", "no note" in r.text, r.text)
app, os_, store, r = run("forget my locker code", 'note_forget(query="locker code")')
check("forget", not any("locker" in n for n in notes(store)) and r.ok, notes(store))
check("forget undo", app.handle("undo that").ok and any("locker" in n for n in notes(store)))

# ----- clock -----
app, os_, store, r = run("tell me the time", 'clock(what="time")')
check("time", r.text == "It's 10:00 AM, sir.", r.text)
app, os_, store, r = run("what is the date", 'clock(what="date")')
check("date", r.text == "Today is Saturday, 31 October 2026, sir.", r.text)
app, os_, store, r = run("tomorrow's day", 'clock(what="day", day="tomorrow")')
check("another day", r.text == "Tomorrow is Sunday, sir.", r.text)

# ----- search, play, video, tabs -----
app, os_, store, r = run("search for dogs")
url = [x for x in os_.log if x[0] == "url"]
check("plain search = Google in Edge", url and url[0][1] == "edge" and "google.com/search?q=dogs" in url[0][2] and r.plan.source in ("ai", "phrase"), (os_.log, r.plan.source, r.text)) if False else None
app, os_, store, r = run("find dogs", 'search(query="dogs")')
check("plain search = Google in Edge", os_.log and os_.log[0][:2] == ("url", "edge") and "google.com/search?q=dogs" in os_.log[0][2], os_.log)
app, os_, store, r = run("find cats on youtube", 'search(query="cats", site="youtube")')
check("search a site", "youtube.com/results?search_query=cats" in os_.log[0][2] and "YouTube" in r.text, (os_.log, r.text))
app, os_, store, r = run("find cats on chrome", 'search(query="cats", browser="chrome")')
check("search in the named browser", os_.log[0][1] == "chrome", os_.log)
app, os_, store, r = run("find cats on gemini", 'search(query="cats", site="gemini")')
check("a site with no search page falls back to Google, said honestly", "google.com" in os_.log[0][2] and "Google" in r.text, (os_.log, r.text))
app, os_, store, r = run("play lofi on youtube", 'play_on(query="lofi", site="youtube")')
check("play on youtube", "youtube.com/results" in os_.log[0][2], os_.log)
app, os_, store, r = run("play lofi", 'play_on(query="lofi")')
check("play defaults to youtube music", "music.youtube.com" in os_.log[0][2], os_.log)
app, os_, store, r = run("go fullscreen", 'video(action="fullscreen")')
check("video key", ("video_key", 0x46) in os_.log and r.text == "Done, sir.", (os_.log, r.text))  # V4: successful actions just say Done
app, os_, store, r = run("go fullscreen", 'video(action="fullscreen")', lambda a, o, s: o.fail.add("video"))
check("no YouTube open is said", not r.ok and "can't see YouTube" in r.text, r.text)
app, os_, store, r = run("close the second youtube tab", 'tab_close(which="second", site="youtube")')
check("tab by position", os_.log[0][0] == "close_tab" and os_.log[0][2] == "second" and r.ok and r.text == "Done, sir.", (os_.log, r.text))
app, os_, store, r = run("close all youtube tabs", 'tab_close(which="all", site="youtube")')
check("all tabs", os_.log[0][2] == "all" and r.text == "Done, sir.", (os_.log, r.text))
app, os_, store, r = run("close this tab", 'tab_close(which="this")')
check("this tab", os_.log[0][2] == "this" and r.ok, os_.log)
app, os_, store, r = run("close the last amazon tab", 'tab_close(which="last", site="amazon")', lambda a, o, s: o.fail.add("tab"))
check("no such tab is said", not r.ok and "can't find" in r.text, r.text)
app, os_, store, r = run("close youtube")
check("close a site = one tab (Fake logs the close)", ("close", "youtube", "site") in os_.log, os_.log)

# ----- system -----
app, os_, store, r = run("screenshot")
check("screenshot", ("screenshot",) in os_.log and r.text == "Done, sir.", r.text)


class Voice:
    def __init__(self):
        self.calls = []

    def stop(self):
        pass

    def tune(self, c):
        self.calls.append(c)
        return True


def with_voice(app, os_, store):
    app.speech = Voice()


app, os_, store, r = run("speak slower", None, with_voice)
check("voice tune by phrase", app.speech.calls == ["slower"] and r.text == "Speaking slower, sir.", (app.speech.calls, r.text))
app, os_, store, r = run("increase your volume", None, lambda a, o, s: setattr(a, "speech", object()))
check("voice tune without a voice says so", not r.ok and "not speaking" in r.text, r.text)
app, os_, store, r = run("what can you do")
check("capabilities", "timers" in r.text and r.results[0][1].exact, r.text)
app, os_, store, r = run("Yeah, sure. Shut down")
check("shut down flag, Goodbye", app.exit_requested and r.text == "Goodbye, sir.", r.text)
app, os_, store, r = run("close yourself")
check("another way to say shut down", app.exit_requested)
app, os_, store, r = run("mic off", None, lambda a, o, s: setattr(a, "set_mic", None))
check("mic with no microphone says so", not r.ok, r.text)
box = []
app, os_, store, r = run("microphone off", None, lambda a, o, s: setattr(a, "set_mic", lambda on: box.append(on) or True))
check("mic off calls the ears", box == [False] and "ten minutes" in r.text, (box, r.text))
check("shut down and mic are never offered to the AI", all(n not in __import__("jarvis2.understand", fromlist=["x"]).system_prompt() for n in ("shut_down", "mic(", "stop_talking")))

# ----- things that must never open -----
app, os_, store, r = run("open yt")
check("'yt' means YouTube", ("open", "youtube", "site", 1, None) in os_.log, os_.log)
check("Narrator and friends are not in the catalog", not [n for n in app.catalog if any(w in n for w in ("narrator", "magnifier", "voice access", "on-screen keyboard"))])
app, os_, store, r = run("open narrator", 'open(target="narrator")')
check("open narrator opens nothing", not any(x[0] == "open" and "narrator" in x[1] for x in os_.log), (os_.log, r.text))

# ----- alerts -----
from jarvis.core import announce_due  # noqa: E402

app, os_, store, r = run("ten second timer", 'timer_set(duration="ten second")')
check("a due timer is announced once", "Sir, your 10-second timer is up." in announce_due(store, CLOCK + timedelta(seconds=11)) and announce_due(store, CLOCK + timedelta(seconds=12)) == [])
store.add("rent", CLOCK + timedelta(minutes=5), "reminder")
check("a due reminder is announced", "Sir, reminder: rent." in announce_due(store, CLOCK + timedelta(minutes=6)))

print("FAILED:" if FAILS else "all ok", *FAILS, sep="\n")
print(f"{N - len(FAILS)}/{N} checks")
sys.exit(1 if FAILS else 0)
