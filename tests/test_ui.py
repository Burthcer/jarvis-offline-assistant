"""UI logic check: drives the app like a user would, with no window. Settings go to a temp file. Run: py -3.12 tests\\test_ui.py"""
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis import actions, settings, ui
from jarvis.store import Store

_tmp = tempfile.mkdtemp()
settings.PATH = os.path.join(_tmp, "settings.json")  # never touch the real settings
os.chdir(_tmp)  # logs/ goes to the temp folder too
auto = []
settings.set_autostart = lambda on: auto.append(on)  # nor the real Windows startup list


class Rec:
    calls = []
    def open_url(self, b, u): self.calls.append((b, u)); return b
    def launch(self, t): self.calls.append(t)
    def key(self, n, c=1): self.calls.append((n, c))


actions.backend = Rec()
fails, total = [], 0


def check(ok, what):
    global total
    total += 1
    if not ok:
        fails.append(what)


app = ui.App(Store(":memory:"), tray=False, load_settings=False)
s = lambda: app.snapshot()
check(s()["state"] == "idle" and not s()["booting"], "starts idle")
app.booting = True; check(s()["booting"], "says it is starting")
class V:
    said = []; listening = True; talk = True; level = 0
    def speak(self, t): self.said.append(t)
app.voice = V(); app._voice_msg("ready", "GPU"); check(not s()["booting"] and V.said == ["Ready, sir."], "says when it is ready")
app.voice = None
app.submit("remind me to call mom tomorrow at 5pm")
check("Noted" in s()["text"] and "Call mom" in s()["text"], f"reminder reply shows: {s()['text']!r}")
check(s()["state"] == "speaking", "state speaking while reply shows")
check(any(r["text"] == "Call mom" for r in s()["reminders"]), "reminder appears in the side list")
app.submit("what's on tomorrow"); check("Call mom" in s()["text"], "agenda reply")
app.submit("open youtube"); check(Rec.calls[-1][0] == "edge" and "YouTube" in s()["text"], "open youtube")
app.submit("   "); app.submit(""); check("YouTube" in s()["text"], "empty input ignored")
app.submit("zzzz qqqq"); check("afraid" in s()["text"] and "zzzz" in s()["text"], "unknown command reply says what it heard")
check(app.history[-1][3] == "err", "unknown command marked as error")
app.submit("x" * 3000)  # huge input must not crash
app.submit("remind me to \u0939\u093f\u0928\u094d\u0926\u0940 \U0001F600 tomorrow at 5pm"); check("Noted" in s()["text"], "unicode input")
app.hide_at = 0; app._tick(1); check(s()["text"] == "" and s()["state"] == "idle", "reply hides, back to idle")
for name in ("listening", "thinking", "speaking", "idle"):
    app.state(name); check(s()["state"] == name, f"state {name}")
app.q.put(("typed", "open youtube")); app._tick(1); check("YouTube" in s()["text"], "typing from the page reaches the same path")
check(["You", "open youtube"] in [h[1:3] for h in app.history], "history keeps what was said")
check(os.path.exists("logs/conversation.log") and "open youtube" in open("logs/conversation.log", encoding="utf-8").read(), "log file written")

# timers, like the clock app
app.submit("set a timer for 10 minutes")
t = s()["timers"][0]
check(t["name"] == "10 minute timer" and t["total"] == 600 and 598 <= t["left"] <= 600 and t["on"], f"timer shows: {t}")
app.q.put(("timer", ("toggle", t["id"]))); app._tick(1)
t2 = s()["timers"][0]; check(not t2["on"] and 598 <= t2["left"] <= 600, f"pause keeps the time: {t2}")
time.sleep(1.1); check(s()["timers"][0]["left"] == t2["left"], "a paused timer doesn't count down")
app.q.put(("timer", ("plus", t["id"]))); app._tick(1)
t3 = s()["timers"][0]; check(t3["left"] == t2["left"] + 60 and not t3["on"] and t3["total"] >= t3["left"], f"+1:00 while paused: {t3}")
app.q.put(("timer", ("toggle", t["id"]))); app._tick(1); check(s()["timers"][0]["on"], "start again")
app.q.put(("timer", ("reset", t["id"]))); app._tick(1)
t4 = s()["timers"][0]; check(t4["left"] == 600 and not t4["on"], f"reset: {t4}")
check(not app.store.due_now(datetime.now() + timedelta(hours=1)), "a paused timer never goes off")
app.submit("resume the timer"); check(s()["timers"][0]["on"] and "again" in s()["text"], "resume by voice")
app.submit("pause the timer"); check(not s()["timers"][0]["on"], "pause by voice")
app.q.put(("timer", ("delete", t["id"]))); app._tick(1); check(not s()["timers"], "delete")
app.q.put(("add_timer", 300)); app._tick(1)
check(s()["timers"][0]["total"] == 300 and app.history[-1][1] != "You", "a preset button starts a timer silently")
app.submit("cancel the timer"); check(not s()["timers"], "cancel by voice")

# several timers: the right one, by its length
for m in (1, 3):
    app.submit(f"set a timer for {m} minutes")
ids = {t["name"]: t["id"] for t in s()["timers"]}
app.submit("pause the one minute timer")
state = {t["name"]: t["on"] for t in s()["timers"]}
check(state == {"1 minute timer": False, "3 minute timer": True}, f"pause only the one named: {state}")
app.submit("cancel it 3 minute timer"); check([t["name"] for t in s()["timers"]] == ["1 minute timer"], f"cancel only the one named: {s()['timers']}")
app.submit("cancel the 9 minute timer"); check("no timer" in s()["text"], "no such timer is said, and nothing happens")
app.submit("set a timer for 2 minutes")
app.submit("cancel the timer"); check("Which timer" in s()["text"] and len(s()["timers"]) == 2, "with several it asks which")
app.submit("2 minute"); check([t["name"] for t in s()["timers"]] == ["1 minute timer"], "and the short answer picks it")
app.submit("set a timer for 2 minutes")
app.submit("cancel all the timers"); check(not s()["timers"], "cancel all")
# all of a day's reminders
for x in ("call dad", "buy milk"):
    app.submit(f"remind me to {x} tomorrow at 9am")
app.submit("remind me to pay rent on 25 december at 9am")
n = len(s()["reminders"])
app.submit("cancel all the reminders for tomorrow"); r = [x["text"] for x in s()["reminders"]]
check("Call dad" not in r and "Buy milk" not in r and "Pay rent" in r and "Cancelled" in s()["text"], f"cancelled at once, only tomorrow's: {r} {s()['text']}")
app.submit("cancel the reminders for tomorrow"); check("no reminders" in s()["text"].lower(), s()["text"])
app.submit("take a screenshot") if False else None

# something goes off: the window opens by itself, with an alert
opened = []
app.open_main = lambda: opened.append(1)
app.store.add("Take medicine", datetime.now() - timedelta(minutes=1))
app._tick(0)
check("Take medicine" in s()["text"] and opened, "due reminder is announced and opens the window")
a = s()["alert"]; check(a and a["kind"] == "reminder" and a["title"] == "Take medicine", f"reminder alert: {a}")
app.q.put(("alert", "stop")); app._tick(1)
check(not s()["alert"] and app.store.get(a["id"])["status"] == "done", "Done closes it for good")
app.store.add("5-minute", datetime.now() - timedelta(seconds=1), kind="timer")
app._tick(0)
a = s()["alert"]; check(a and a["title"] == "Your 5 minute timer is up" and a["face"] == "00:00", f"timer alert: {a}")
app.q.put(("alert", "snooze")); app._tick(1)
r = app.store.get(a["id"]); check(not s()["alert"] and r["status"] == "open" and r["due"] > datetime.now().isoformat(), "snooze brings it back later")

# reminders from the app
app.q.put(("typed", "remind me to water plants tomorrow at 9am")); app._tick(1)
rid = next(r["id"] for r in s()["reminders"] if "Water plants" in r["text"])
app.q.put(("reminder", ("delete", rid))); app._tick(1)
check(not any(r["id"] == rid for r in s()["reminders"]), "cancel a reminder from the app, with no question asked")
app.submit("remind me to feed the cat tomorrow at 9am")
rid = next(r["id"] for r in s()["reminders"] if "Feed the cat" in r["text"])
app.q.put(("reminder", ("done", rid))); app._tick(1)
check(not any(r["id"] == rid for r in s()["reminders"]) and app.store.get(rid)["status"] == "done", "tick a reminder off from the app")
ui.Api(app).add_reminder("call dad tomorrow at 6pm"); app._tick(1)
check(any("Call dad" in r["text"] for r in s()["reminders"]), "add a reminder from the app")
app.q.put(("reminder", ("delete", 99999))); app._tick(1)

# the page cannot run anything but what the API offers, and bad data can't hurt
api = ui.Api(app)
b = api.boot(); check(b["history"] and b["snap"]["state"], "the page gets history and state when it opens")
check(not [n for n in dir(api) if not n.startswith("_") and n not in ("boot", "submit", "toggle_mic", "timer", "add_timer", "alert", "reminder", "add_reminder", "hear_voice", "settings", "save_settings")], "the page's API is only what's listed")
api.timer("toggle", 99999); app._tick(1)
api.alert("stop"); app._tick(1)

# settings
check(api.settings()["cfg"]["wake_replies"] and {"key": "youtube", "name": "YouTube"} in api.settings()["sites"], "settings reach the page")
check(api.save_settings({"wake_replies": ["  ", "Yes, sir"], "browsers": {"linkedin": "edge", "youtube": "firefox"}, "tts_volume": 0.5, "tts_speed": 1.2, "voice_on": True, "speak_replies": True, "tts_voice": "jarvis"}) == "Saved, sir.", "save")
c = settings.load()
check(c["wake_replies"] == ["Yes, sir"] and c["browsers"]["linkedin"] == "edge" and c["browsers"]["youtube"] != "firefox" and c["tts_volume"] == 0.5, f"settings saved and bad values refused: {c}")
check(auto == [False], f"autostart off by default {auto}")
actions.SITES["linkedin"] = ("chrome", *actions.SITES["linkedin"][1:])
open(settings.PATH, "w").write("{not json"); check(settings.load()["wake_replies"][0] == "At your service, sir", "damaged settings file -> defaults")
open(settings.PATH, "w").write('{"browsers": {"youtube": "chrome", "evil": "x", "netflix": "firefox"}, "wake_replies": "no"}')
c = settings.load(); check(c["browsers"]["youtube"] == "chrome" and "evil" not in c["browsers"] and c["browsers"]["netflix"] == "edge", "bad settings values ignored")
settings.apply({**c, "start_with_windows": False}); check(actions.SITES["youtube"][0] == "chrome", "browser change applied to actions")
actions.SITES["youtube"] = ("edge", *actions.SITES["youtube"][1:])

app.quit()
print(f"UI: {total - len(fails)}/{total}  {'PASS' if not fails else 'FAIL'}")
for f in fails:
    print("  ", f.encode("ascii", "backslashreplace").decode())
sys.exit(1 if fails else 0)
