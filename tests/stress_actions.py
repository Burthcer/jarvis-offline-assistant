"""M2 action tests with a fake backend (nothing really opens). Run: py -3.12 tests\\stress_actions.py"""
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis import actions
from jarvis.core import announce_due, handle
from jarvis.store import Store

NOW = datetime(2026, 10, 31, 10, 0)
total = 0
fails = []


class Rec:
    def __init__(self): self.calls = []
    def open_url(self, b, u): self.calls.append(("url", b, u)); return b
    def launch(self, t): self.calls.append(("launch", t))
    def key(self, n, c=1): self.calls.append(("key", n, c))
    def running(self): return []
    def target(self, lnk): return None
    def close(self, exe): self.calls.append(("close", exe)); return True
    def close_tab(self, p=None): self.calls.append(("tab", p)); return 1
    def close_folders(self, p=None): self.calls.append(("folders", p)); return 1
    def screenshot(self): self.calls.append(("shot",)); return "x.png"
    def video_key(self, vk, shift=False): self.calls.append(("video", vk)); return True
    def first_video(self, wait=0): return True


def run(text, store=None):
    actions.backend = Rec(); actions.muted = False; actions.last_site = None
    out = handle(text, store or Store(":memory:"), NOW)
    return out, actions.backend.calls


def check(text, calls, reply=""):
    global total
    total += 1
    out, got = run(text)
    if got != calls or reply.lower() not in out.lower():
        fails.append(f"{text!r} -> {out!r} {got} want {calls} {reply!r}")


Y, YM = "https://www.youtube.com", "https://music.youtube.com"
for t, c in [
    ("open youtube", [("url", "edge", Y)]), ("Open YouTube.", [("url", "edge", Y)]), ("open you tube", [("url", "edge", Y)]), ("open yt", [("url", "edge", Y)]),
    ("hey jarvis open youtube", [("url", "edge", Y)]), ("can you open youtube", [("url", "edge", Y)]), ("could you please open youtube", [("url", "edge", Y)]),
    ("open youtube please", [("url", "edge", Y)]), ("open youtube sir", [("url", "edge", Y)]), ("launch youtube", [("url", "edge", Y)]),
    ("go to youtube", [("url", "edge", Y)]), ("take me to youtube", [("url", "edge", Y)]), ("open the youtube website", [("url", "edge", Y)]),
    ("open youtube music", [("url", "edge", YM)]), ("open yt music", [("url", "edge", YM)]), ("open YouTube Music", [("url", "edge", YM)]),
    ("open gemini", [("url", "edge", "https://gemini.google.com")]), ("open netflix", [("url", "edge", "https://www.netflix.com")]),
    ("open amazon", [("url", "edge", "https://www.amazon.in")]), ("open claude console", [("url", "edge", "https://console.anthropic.com")]),
    ("open anthropic console", [("url", "edge", "https://console.anthropic.com")]),
    ("open linkedin", [("url", "chrome", "https://www.linkedin.com")]), ("open linked in", [("url", "chrome", "https://www.linkedin.com")]),
    ("open dev.to", [("url", "chrome", "https://dev.to")]), ("open dev dot to", [("url", "chrome", "https://dev.to")]), ("open dev to", [("url", "chrome", "https://dev.to")]),
    ("open luma", [("url", "chrome", "https://lu.ma")]), ("open youtube in chrome", [("url", "chrome", Y)]), ("open linkedin in edge", [("url", "edge", "https://www.linkedin.com")]),
    ("open youtube on chrome", [("url", "chrome", Y)]), ("open chrome", [("launch", "chrome")]), ("open google chrome", [("launch", "chrome")]),
    ("open edge", [("launch", "edge")]), ("open microsoft edge", [("launch", "edge")]), ("open notepad", [("launch", "notepad.exe")]),
    ("open calculator", [("launch", "calc.exe")]), ("open file explorer", [("launch", "explorer.exe")]), ("open settings", [("launch", "ms-settings:")]),
    ("open paint", [("launch", "mspaint.exe")]),
    ("search lo-fi on youtube", [("url", "edge", Y + "/results?search_query=lo-fi")]),
    ("search for lo fi beats on youtube", [("url", "edge", Y + "/results?search_query=lo+fi+beats")]),
    ("search youtube for lo-fi", [("url", "edge", Y + "/results?search_query=lo-fi")]),
    ("search on youtube for python tutorial", [("url", "edge", Y + "/results?search_query=python+tutorial")]),
    ("search lo-fi on youtube in chrome", [("url", "chrome", Y + "/results?search_query=lo-fi")]),
    ("search python jobs on linkedin", [("url", "chrome", "https://www.linkedin.com/search/results/all/?keywords=python+jobs")]),
    ("search headphones on amazon", [("url", "edge", "https://www.amazon.in/s?k=headphones")]),
    ("search flask on dev.to", [("url", "chrome", "https://dev.to/search?q=flask")]),
    ("search weather in pune", [("url", "edge", "https://www.google.com/search?q=weather+in+pune")]),
    ("google python dictionaries", [("url", "edge", "https://www.google.com/search?q=python+dictionaries")]),
    ("look up cs syllabus", [("url", "edge", "https://www.google.com/search?q=cs+syllabus")]),
    ("search c++ & java", [("url", "edge", "https://www.google.com/search?q=c%2B%2B+%26+java")]),
    ("search python on stack overflow", [("url", "edge", "https://www.google.com/search?q=python+on+stack+overflow")]),
    ("play lo-fi beats", [("url", "edge", YM + "/search?q=lo-fi+beats")]), ("play arijit singh on youtube music", [("url", "edge", YM + "/search?q=arijit+singh")]),
    ("play despacito on youtube", [("url", "edge", Y + "/results?search_query=despacito")]), ("play some music", [("url", "edge", YM)]),
    ("what can you open", []), ("pause", [("key", "play", 1)]), ("pause the music", [("key", "play", 1)]), ("play", [("key", "play", 1)]),
    ("resume", [("key", "play", 1)]), ("stop the music", [("key", "play", 1)]), ("next song", [("key", "next", 1)]), ("skip", [("key", "next", 1)]),
    ("play the next song", [("key", "next", 1)]), ("next track", [("key", "next", 1)]), ("previous song", [("key", "prev", 1)]),
    ("go back", [("key", "prev", 1)]), ("play the previous track", [("key", "prev", 1)]),
    ("volume up", [("key", "up", 5)]), ("increase the volume", [("key", "up", 5)]), ("turn the volume up", [("key", "up", 5)]), ("turn up the volume", [("key", "up", 5)]),
    ("raise volume", [("key", "up", 5)]), ("louder", [("key", "up", 5)]), ("volume down", [("key", "down", 5)]), ("lower the volume", [("key", "down", 5)]),
    ("decrease the volume", [("key", "down", 5)]), ("turn it down", [("key", "down", 5)]), ("quieter", [("key", "down", 5)]), ("reduce volume", [("key", "down", 5)]),
    ("increase volume by 20", [("key", "up", 10)]), ("decrease the volume by ten", [("key", "down", 5)]),
    ("set volume to 40", [("key", "down", 50), ("key", "up", 20)]), ("set the volume to forty percent", [("key", "down", 50), ("key", "up", 20)]),
    ("volume 30", [("key", "down", 50), ("key", "up", 15)]), ("volume to fifty", [("key", "down", 50), ("key", "up", 25)]),
    ("volume to 0", [("key", "down", 50), ("key", "up", 0)]), ("volume to 100", [("key", "down", 50), ("key", "up", 50)]), ("volume 500", [("key", "down", 50), ("key", "up", 50)]),
    ("max volume", [("key", "down", 50), ("key", "up", 50)]), ("half volume", [("key", "down", 50), ("key", "up", 25)]),
    ("set volume to twenty five", [("key", "down", 50), ("key", "up", 12)]),
    ("mute", [("key", "mute", 1)]), ("mute the sound", [("key", "mute", 1)]), ("unmute", []),
    ("make edge my default browser", [("launch", "ms-settings:defaultapps")]), ("set chrome as default browser", [("launch", "ms-settings:defaultapps")]),
    ("change my default browser", [("launch", "ms-settings:defaultapps")]),
]:
    check(t, c)

# refusals: nothing may run
for t, why in [("open the bank", "isn't on my list"), ("open cmd", "isn't on my list"), ("open powershell", "isn't on my list"), ("open C:\\Windows\\System32", "isn't on my list"),
               ("open https://evil.example.com", "isn't on my list"), ("open evil.com", "isn't on my list"), ("launch regedit", "isn't on my list"),
               ("search", "Search for what"), ("search gemini for cats", "can't search"), ("search cats on luma", "can't search"),
               ("increase your volume", "my own voice"), ("speak slower", "my own voice"), ("decrease your speech speed", "my own voice"),
               ("volume", "Up or down"), ("shut down the laptop", "afraid"), ("delete my files", "couldn't find"), ("format c drive", "afraid")]:
    check(t, [], why)

# asking about a timer, however it's worded, shows the status; "set a timer" alone still asks how long
total += 1; s = Store(":memory:"); handle("set a timer for 10 minutes", s, NOW)
for q in ("how much time is left on my timer", "how much time is left in the timer", "how much time is left", "how long is left on the timer", "what's left on the timer",
          "how much time do I have left", "timer status", "check the timer", "hpw mcuh time i n timer", "timer", "time remaining on the timer", "show my timers"):
    total += 1
    o = handle(q, s, NOW + timedelta(minutes=3))
    if "7 minutes" not in o: fails.append(f"timer status {q!r} -> {o!r}")
for q, want in [("set a timer", "How long"), ("start a timer", "How long")]:
    total += 1
    o = handle(q, Store(":memory:"), NOW)
    if want not in o: fails.append(f"timer ask {q!r} -> {o!r}")
for q in ("hey jarvis", "Hey, Jarvis!", "jarvis", "ok jarvis."):
    total += 1
    o = handle(q, Store(":memory:"), NOW)
    if "At your service" not in o: fails.append(f"bare wake {q!r} -> {o!r}")

for q, want in [("Hey Jarvis, can you hear me?", "Loud and clear"), ("can you hear me", "Loud and clear"), ("hello jarvis", "Hello, sir"), ("how are you?", "Very well"),
                ("thank you", "My pleasure"), ("Thanks!", "My pleasure"), ("who are you", "I'm Jarvis"), ("are you there", "Always"), ("never mind", "Of course")]:
    total += 1
    o = handle(q, Store(":memory:"), NOW)
    if want not in o: fails.append(f"chat {q!r} -> {o!r}")

# Jarvis asks "when?" and then the time alone is enough
for ans, due in [("5 pm", "2026-10-31T17:00:00"), ("tomorrow at five thirty pm", "2026-11-01T17:30:00"), ("in two hours", "2026-10-31T12:00:00"),
                 ("tomorrow", "2026-11-01T09:00:00"), ("on friday at 3", "2026-11-06T15:00:00"), ("at 6 in the evening", "2026-10-31T18:00:00")]:
    total += 1; s = Store(":memory:"); q = handle("remind me to call mom", s, NOW); o = handle(ans, s, NOW); r = s.db.execute("SELECT text,due FROM items").fetchall()
    if not (q.startswith("When would you like") and "Noted" in o and len(r) == 1 and r[0]["text"] == "Call mom" and r[0]["due"] == due):
        fails.append(f"follow-up {ans!r}: {q!r} {o!r} {[tuple(x) for x in r]}")
total += 1; s = Store(":memory:"); handle("remind me to call mom", s, NOW); o = handle("never mind", s, NOW)
if "Very well" not in o or s.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]: fails.append(f"follow-up cancelled {o!r}")
total += 1; s = Store(":memory:"); handle("remind me to call mom", s, NOW); actions.backend = Rec(); o = handle("open youtube", s, NOW)
if "Opening" not in o or s.pending or s.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]: fails.append(f"other command after a question {o!r}")
total += 1; s = Store(":memory:"); handle("remind me to call mom", s, NOW); o = handle("remind me to buy milk tomorrow at 5pm", s, NOW)
r = s.db.execute("SELECT text FROM items").fetchall()
if [x["text"] for x in r] != ["Buy milk"]: fails.append(f"new full reminder after a question {o!r} {[tuple(x) for x in r]}")
total += 1; s = Store(":memory:"); handle("remind me to call mom", s, NOW); o = handle("9 am", s, NOW)  # it's 10 am: 9 am means tomorrow
if "tomorrow 9:00 am" not in o or s.pending: fails.append(f"time already past today -> tomorrow {o!r}")

# clarifying questions: the short answer completes the request
for first, ans, check_ in [("volume", "up", lambda c: ("key", "up", 5) in c), ("search", "lo-fi beats on youtube", lambda c: any("search_query=lo-fi+beats" in x[2] for x in c if x[0] == "url")),
                           ("set a timer", "ten minutes", None), ("remind me", "call mom tomorrow at 5pm", None)]:
    total += 1; s = Store(":memory:"); actions.backend = Rec()
    q = handle(first, s, NOW); o = handle(ans, s, NOW)
    ok_ = (check_(actions.backend.calls) if check_ else ("Timer set" in o or "Noted" in o)) and not s.pending
    if not ok_: fails.append(f"clarify {first!r} -> {q!r}, {ans!r} -> {o!r} {actions.backend.calls}")
total += 1; s = Store(":memory:"); actions.backend = Rec(); handle("volume", s, NOW); o = handle("open youtube please and also play some music now", s, NOW)
if s.pending: fails.append(f"a long unrelated answer drops the question {o!r}")
total += 1; o1, o2 = handle("blorp the flim", Store(":memory:"), NOW), handle("blorp the flim", Store(":memory:"), NOW)
if o1 == o2 or "blorp the flim" not in o1: fails.append(f"unknown replies vary and say what was heard {o1!r} {o2!r}")

# speech-to-text mishearings of allowlisted names resolve; unknown things still don't
for t, calls in [("open loom", [("url", "chrome", "https://lu.ma")]), ("open notal", [("launch", "notepad.exe")]), ("open notetab", [("launch", "notepad.exe")]),
                 ("open calculater", [("launch", "calc.exe")]), ("open youtub", [("url", "edge", Y)]), ("open netflicks", [("url", "edge", "https://www.netflix.com")]),
                 ("make edge my default browse", [("launch", "ms-settings:defaultapps")]), ("open files", [("launch", "explorer.exe")]),
                 ("Could you open up YouTube?", [("url", "edge", Y)]), ("open up netflix for me", [("url", "edge", "https://www.netflix.com")]),
                 ("open bank", []), ("open regedit", []), ("open terminal", []), ("open powershell", []),("open note to him", [])]:
    check(t, calls)
for t, due in [("remind me to take medicine at 8.30 in the morning", "2026-11-01T08:30:00"), ("remind me to call mom at 5.30 pm", "2026-10-31T17:30:00"),
               ("remind me to read in 1.5 hours", "2026-10-31T11:30:00")]:
    total += 1; s = Store(":memory:"); handle(t, s, NOW); r = s.db.execute("SELECT due FROM items").fetchone()
    if not r or r["due"] != due: fails.append(f"decimal time {t!r} -> {r and r['due']} want {due}")
total += 1; s = Store(":memory:"); handle("remind me maths exam on 23 november", s, NOW); o = handle("move the maths exam to the 26.", s, NOW)
if "26 Nov" not in o: fails.append(f"'to the 26.' -> {o!r}")

# Jarvis's own voice commands are recognised (and the PC volume ones are not confused with them)
for t, want in [("speak slower", ("speed", -1)), ("speak faster", ("speed", 1)), ("speak louder", ("volume", 1)), ("speak quieter", ("volume", -1)),
                ("talk softer", ("volume", -1)), ("speak a bit slower", ("speed", -1)), ("increase your volume", ("volume", 1)), ("decrease your volume", ("volume", -1)),
                ("Increase your speech volume.", ("volume", 1)), ("lower your voice volume", ("volume", -1)), ("increase your speed", ("speed", 1)),
                ("decrease your speech speed", ("speed", -1)), ("slow down", ("speed", -1)), ("speed up", ("speed", 1)), ("hey jarvis, speak slower please", ("speed", -1)),
                ("your volume up", ("volume", 1)), ("your speed down", ("speed", -1)), ("turn up your volume", ("volume", 1)), ("reduce your speaking speed", ("speed", -1)),
                ("increase the volume", None), ("volume up", None), ("turn it down", None), ("set volume to 40", None), ("play faster music", None), ("remind me to speak slower", None)]:
    total += 1
    if actions.voice_tune(t) != want:
        fails.append(f"voice_tune {t!r} -> {actions.voice_tune(t)} want {want}")

# the three sites the owner named for Chrome never go to Edge, and nothing else goes to Chrome
for site, br in [(k, v[0]) for k, v in actions.SITES.items()]:
    total += 1
    out, calls = run(f"open {site}")
    if calls[0][1] != br or (br == "chrome") != (site in ("linkedin", "dev.to", "luma")):
        fails.append(f"browser rule {site}: {calls}")

# unmute / mute state
total += 1
actions.backend = Rec(); actions.muted = False; s = Store(":memory:")
o = [handle(x, s, NOW) for x in ("mute", "mute", "unmute", "unmute")]
if actions.backend.calls != [("key", "mute", 1), ("key", "up", 1), ("key", "down", 1)] or "Already" not in o[1] or "Not muted" not in o[3]:
    fails.append(f"mute state {o} {actions.backend.calls}")

# timers
for t, secs, label in [("set a timer for 10 minutes", 600, "10-minute"), ("set a ten minute timer", 600, "10-minute"), ("timer for 5 minutes", 300, "5-minute"),
                       ("start a 2 hour timer", 7200, "2-hour"), ("set a timer for ninety seconds", 90, "1-minute and 30-second"), ("30 second timer", 30, "30-second"),
                       ("set a timer for an hour", 3600, "1-hour"), ("set a timer for half an hour", 1800, "30-minute"), ("set a timer for 1 hour 30 minutes", 5400, "1-hour and 30-minute"),
                       ("set a timer for 1.5 hours", 5400, "1-hour and 30-minute"), ("set a timer for twenty five minutes", 1500, "25-minute"),
                       ("hey jarvis set a timer for 3 minutes please", 180, "3-minute"), ("set a timer for 24 hours", 86400, "24-hour"),
                       ("can you set a timer for a minute", 60, "1-minute")]:
    total += 1
    s = Store(":memory:"); out = handle(t, s, NOW); rows = s.timers()
    if not (len(rows) == 1 and rows[0]["due"] == (NOW + timedelta(seconds=secs)).isoformat() and rows[0]["text"] == label and "Timer set" in out):
        fails.append(f"timer {t!r} -> {out!r} {[(r['text'], r['due']) for r in rows]}")
for t, want in [("set a timer", "How long"), ("set a timer for 25 hours", "24 hours"), ("set a timer for 99999999999 hours", "24 hours"), ("set a timer for 0 minutes", "How long")]:
    total += 1
    s = Store(":memory:"); out = handle(t, s, NOW)
    if want not in out or s.timers():
        fails.append(f"timer refuse {t!r} -> {out!r}")
total += 1  # fires, announces, restarts, cancels, lists
s = Store(":memory:"); handle("set a timer for 10 minutes", s, NOW); handle("set a timer for 5 minutes", s, NOW)
a = handle("set a timer for 10 minutes", s, NOW + timedelta(minutes=1))
l = handle("how long is left on my timer", s, NOW + timedelta(minutes=2))
ann = announce_due(s, NOW + timedelta(minutes=6))
ann2 = announce_due(s, NOW + timedelta(minutes=6))
c = handle("cancel the timer", s, NOW + timedelta(minutes=6))
n = handle("cancel the timer", s, NOW + timedelta(minutes=6))
if not ("Restarted" in a and "3 minutes" in l and ann == ["Sir, your 5-minute timer is up."] and ann2 == [] and "cancelled" in c and "no timers" in n and not s.timers()):
    fails.append(f"timer flow {a!r} {l!r} {ann} {ann2} {c!r} {n!r}")
total += 1  # a reminder is never mistaken for a timer, and vice versa
s = Store(":memory:"); handle("remind me to check the oven timer tomorrow at 5pm", s, NOW); handle("remind me to open youtube at 6pm", s, NOW)
r = s.db.execute("SELECT kind,text FROM items").fetchall()
if [x["kind"] for x in r] != ["reminder", "reminder"] or "oven" not in r[0]["text"].lower():
    fails.append(f"reminder vs action {[tuple(x) for x in r]}")
total += 1  # reminders/notes still work and still win over actions
s = Store(":memory:")
o = [handle(x, s, NOW) for x in ("remember the wifi is open sesame", "what is the wifi", "remind me to search for the form tomorrow at 9am", "what's on tomorrow")]
if not ("Remembered" in o[0] and "sesame" in o[1] and "Noted" in o[2] and "search for the form" in o[3].lower()):
    fails.append(f"coexist {o}")

# a launch failure is reported, never raised
class Boom(Rec):
    def open_url(self, *a): raise FileNotFoundError("no browser")
    def launch(self, *a): raise OSError("blocked")
    def key(self, *a): raise OSError("blocked")
for t in ("open youtube", "open notepad", "search cats on youtube", "make edge my default browser"):
    total += 1
    actions.backend = Boom()
    try:
        out = handle(t, Store(":memory:"), NOW)
        if "couldn't" not in out:
            fails.append(f"boom {t!r} -> {out!r}")
    except Exception as e:
        fails.append(f"boom raised {t!r} {e!r}")

# fuzz: random mixtures must never crash or run anything outside the allowlist
random.seed(7)
words = "open search play volume timer set mute pause next youtube chrome edge linkedin for on in to the a an 5 ten minutes hour lo-fi cmd evil.com C:\\ http:// & | ; ` $( ) ' \" \\ % zero 99999999999 half".split()
bad = 0
for _ in range(20000):
    t = " ".join(random.choice(words) for _ in range(random.randint(1, 9)))
    actions.backend = Rec(); actions.muted = False; actions.last_site = None
    total += 1
    try:
        handle(t, Store(":memory:"), NOW)
    except Exception as e:
        fails.append(f"fuzz crash {t!r} {e!r}"); continue
    for c in actions.backend.calls:
        if c[0] == "url" and not (c[2].startswith(tuple(v[1] for v in actions.SITES.values())) or c[2].startswith(tuple(v[2] for v in actions.SITES.values() if v[2]))):
            fails.append(f"fuzz bad url {t!r} {c}")
        if c[0] == "launch" and c[1] not in (*actions.APPS.values(), "ms-settings:defaultapps"):
            fails.append(f"fuzz bad launch {t!r} {c}")
        if c[0] == "key" and (c[1] not in actions.VK or c[2] > 50):
            fails.append(f"fuzz bad key {t!r} {c}")

if __name__ == "__main__":
    print(f"M2 actions: {total - len(fails)}/{total}  {'PASS' if not fails else 'FAIL'}")
    for f in fails[:60]:
        print("  ", f.encode("ascii", "backslashreplace").decode())
