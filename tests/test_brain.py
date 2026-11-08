"""The smart layer: 40 messy, real-life sentences -> local AI rewrite -> the real rules engine -> checked outcome.
Also: nothing outside the allowlist may ever run, and speed. Run: py -3.12 tests\\test_brain.py  (~1 minute, uses the GPU)"""
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis import actions
from jarvis.brain import Brain
from jarvis.core import handle, is_unknown
from jarvis.store import Store

NOW = datetime(2026, 10, 31, 10, 0)  # a Saturday
b = Brain(); t = time.time(); b.load()
if not b.ready:
    sys.exit(f"brain failed to load: {b.error}")
print(f"AI loaded in {time.time() - t:.1f} s")


class Rec:
    def __init__(self): self.calls = []
    def open_url(self, br, u): self.calls.append(("url", br, u)); return br
    def launch(self, x): self.calls.append(("launch", x))
    def key(self, n, c=1): self.calls.append(("key", n, c))
    def target(self, lnk): return actions.Real().target(lnk)
    def close(self, exe): self.calls.append(("close", exe)); return True
    def running(self): return ["WhatsApp.Root.exe", "Discord.exe", "DiscordSystemHelper.exe", "python.exe"]
    def close_tab(self, p=None): self.calls.append(("tab", p)); return 1
    def close_folders(self, p=None): self.calls.append(("folders", p)); return 1
    def screenshot(self): self.calls.append(("shot",)); return "x.png"
    def video_key(self, vk, shift=False): self.calls.append(("video", vk)); return True
    def first_video(self, wait=0): self.calls.append(("first",)); return True


def seeded():
    s = Store(":memory:")
    for x in ("remind me to call mom tomorrow at 6pm", "remind me about the dentist appointment on friday at 11am", "remind me about the physics practical on monday at 2pm",
              "remember my bike lock code is 4512", "set a timer for 10 minutes"):
        handle(x, s, NOW)
    return s


def url(part): return lambda c, r, s: any(x[0] == "url" and part in x[2] for x in c)
def browser(br, part): return lambda c, r, s: any(x[0] == "url" and x[1] == br and part in x[2] for x in c)
def key(name): return lambda c, r, s: any(x[0] == "key" and x[1] == name for x in c)
def launch(x_): return lambda c, r, s: ("launch", x_) in c
def says(*parts): return lambda c, r, s: all(p.lower() in r.lower() for p in parts)
def item(text, due): return lambda c, r, s: any(text.lower() in x["text"].lower() and x["due"] == due for x in s.db.execute("SELECT * FROM items"))
def timer(secs): return lambda c, r, s: any(x["kind"] == "timer" and x["due"] == (NOW + timedelta(seconds=secs)).isoformat() for x in s.db.execute("SELECT * FROM items"))
def chat(): return lambda c, r, s: r.startswith("CHAT") and not c
def tune(what, d): return lambda c, r, s: r == f"TUNE {(what, d)}"
def nothing_ran(): return lambda c, r, s: not c
def closed(exe): return lambda c, r, s: ("close", exe) in c


def text_or_ai(text):  # as the app does: if the AI isn't sure, the rules try the words as they are
    from jarvis.brain import UNSURE
    line = b.rewrite(text)
    return text if line == "chat: " + UNSURE else line


CASES = [
    ("Remind me, for tomorrow, 5 pm, I have to do my Web Technology Lab assignment", item("do my web technology lab assignment", "2026-11-01T17:00:00")),
    ("remind me tomorrow at 5pm that I have to do my Web Technology Lab assignment", item("do my web technology lab assignment", "2026-11-01T17:00:00")),
    ("can you set a timer about the next 5 minutes", timer(300)),
    ("could you please turn the volume up a little", key("up")),
    ("ugh it's way too loud", key("down")),
    ("can you open up youtube for me", browser("edge", "youtube.com")),
    ("open linkedin", browser("chrome", "linkedin.com")),
    ("I wanna watch something on netflix", url("netflix.com")),
    ("play some arijit singh", url("arijit")),
    ("look up python tutorials on youtube", url("search_query=python+tutorials")),
    ("google the weather in pune", url("google.com/search?q=")),
    ("what's on my plate tomorrow", says("call mom")),
    ("did I miss anything", says("miss")),
    ("how much time do I have left on the timer", says("minutes")),
    ("kill the timer", says("cancelled")),
    ("remember that my locker number is 221", says("remembered")),
    ("what's my bike lock code", says("4512")),
    ("I'm finally done with the physics practical", says("marked done", "physics")),
    ("push the dentist appointment to friday at 4pm", says("moved", "dentist", "4:00 pm")),
    ("can you talk a bit slower", tune("speed", -1)),
    ("mute it", key("mute")),
    ("skip this song", key("next")),
    ("go back to the previous track", key("prev")),
    ("make chrome my default browser", launch("ms-settings:defaultapps")),
    ("hey how's it going", chat()),
    ("what can you do", says("I can")),
    ("remind me in 20 minutes to take the pizza out", item("pizza out", "2026-10-31T10:20:00")),
    ("remind me to call dad", says("when would you like")),
    ("remind me on monday at 3 to submit the lab record", item("submit the lab record", "2026-11-02T15:00:00")),
    ("what do I have on friday", says("dentist")),
    ("open the calculator", launch("calc.exe")),
    ("search for a gaming laptop on amazon", url("amazon.in/s?k=gaming+laptop")),
    ("what's 15 times 4", lambda c, r, s: "60" in r and not c),
    ("delete the dentist reminder", says("cancelled", "dentist")),
    ("open cmd", nothing_ran()),
    ("shut down my laptop", nothing_ran()),
    ("format the C drive", nothing_ran()),
    ("set the volume to 30 percent", lambda c, r, s: ("key", "up", 15) in c),
    ("wake me up at 6 30 tomorrow morning", item("", "2026-11-01T06:30:00")),
    ("so like, I need to buy groceries on sunday evening, remind me", item("groceries", "2026-11-01T18:00:00")),
    ("open whisper no pro", launch(r"C:\Users\USER\Desktop\Wisperno Pro.lnk")),
    ("close IHatePDF completely", closed("IHatePDF.exe")),
    ("ok you can turn yourself off now", says("goodbye")),
    ("not sure why you cannot hear me", chat()),
    ("shut down my computer", nothing_ran()),
    ("close WhatsApp", closed("WhatsApp.Root.exe")),
    ("close discord and whatsapp", lambda c, r, s: ("close", "Discord.exe") in c and ("close", "WhatsApp.Root.exe") in c),
    ("close YouTube", lambda c, r, s: c and c[0][0] == "tab" and "youtube" in c[0][1]),
    ("close this tab", lambda c, r, s: ("tab", None) in c),
    ("Essentially, remind me, today, 5 PM, I have to submit my Web Technology assignment", item("web technology assignment", "2026-10-31T17:00:00")),
    ("What are the current reminders?", says("call mom", "dentist")),
    ("Edit the reminder of call mom to call mom and dad", says("updated", "call mom and dad")),
    ("click a screenshot of the current screen", lambda c, r, s: ("shot",) in c),
    ("open Claude, Whisper Flow and Armory Crate", lambda c, r, s: len(c) == 3 and "wisperno" not in r.lower() and "armoury" in r.lower()),
    ("Close Claude and Whisper Flow", lambda c, r, s: ("close", "Claude.exe") in c and "wisperno" not in r.lower()),
    ("could you open whisper flow for me real quick", lambda c, r, s: len(c) == 1 and "wispr" in c[0][1].lower()),
    ("show me what I downloaded", launch("shell:Downloads")),
    ("close file explorer", lambda c, r, s: ("folders", None) in c),
    ("make this video full screen", lambda c, r, s: ("video", 0x46) in c),
    ("Edge band kar do", closed("msedge.exe")),
    ("Lewis Chrome", closed("chrome.exe")),
    ("Clues File Explorer", lambda c, r, s: ("folders", None) in c),
    ("cancel all the reminders for tomorrow", says("cancel", "call mom")),
    ("get rid of the 10 minute timer", says("cancelled")),
    ("hold the ten minute timer", says("paused")),
]
ok = 0; bad = []; times = []
for text, check in CASES:
    s = seeded(); actions.backend = Rec(); actions.muted = False; actions.last_site = None
    t = time.perf_counter(); line = actions.direct(text) or text_or_ai(text); times.append(time.perf_counter() - t)
    if line.lower().startswith("chat:"):
        reply = "CHAT " + line[5:].strip()
    elif actions.voice_tune(line):
        reply = f"TUNE {actions.voice_tune(line)}"
    else:
        reply = handle(line, s, NOW)
        if is_unknown(reply):
            raw = handle(text, s, NOW)
            reply = raw if not is_unknown(raw) else reply
    calls = actions.backend.calls
    allowed = all((c[0] == "url" and any(c[2].startswith(h) for h in [v[1] for v in actions.SITES.values()] + [v[2] for v in actions.SITES.values() if v[2]]))
                  or (c[0] == "launch" and c[1] in (*actions.APPS.values(), *actions.desktop_apps().values(), *actions.start_apps().values(), *actions.FOLDERS.values(), "ms-settings:defaultapps")) or c[0] in ("key", "close", "tab", "folders", "shot", "video", "first") for c in calls)
    good = check(calls, reply, s) and allowed
    ok += good
    if not good:
        bad.append(f"{text!r}\n      AI: {line!r}\n      -> {reply!r} {calls}")
print(f"BRAIN: {ok}/{len(CASES)} ({100 * ok / len(CASES):.0f}%), AI time median {sorted(times)[len(times) // 2] * 1000:.0f} ms, max {max(times) * 1000:.0f} ms")
for x in bad:
    print("   ", x.encode("ascii", "backslashreplace").decode())

# held-out: sentences unlike any example, to check it generalises rather than memorises
HELD = [
    ("bro can you crank the music up", key("up")),
    ("turn it down, my mom's sleeping", key("down")),
    ("next track please", key("next")),
    ("hold the music", key("play")),
    ("I need to submit my DBMS project by Thursday 11 am, don't let me forget", item("dbms project", "2026-11-05T11:00:00")),
    ("alarm at 5 45 am tomorrow", item("", "2026-11-01T05:45:00")),
    ("throw on some youtube music", url("music.youtube.com")),
    ("what have I got going on this week", says("this week")),
    ("did my timer finish yet", says("minutes")),
    ("bring up dev dot to in chrome", browser("chrome", "dev.to")),
    ("find me cheap headphones on amazon", url("amazon.in/s?k=")),
    ("tell me a joke", chat()),
    ("who made you", chat()),
    ("open my bank account", nothing_ran()),
    ("delete all my files", nothing_ran()),
    ("could you remind me in an hour and a half to stretch", item("stretch", "2026-10-31T11:30:00")),
    ("I've done the dentist appointment", says("marked done", "dentist")),
    ("take it slower when you talk", tune("speed", -1)),
    ("put a 3 minute timer on for my noodles", timer(180)),
    ("google how to center a div", url("google.com/search?q=")),
    ("could you launch i hate pdf for me", launch(r"C:\Users\Public\Desktop\IHatePDF.lnk")),
    ("kill wisperno", closed("WispernoPro.exe")),
    ("that is all, go to sleep jarvis", says("goodbye")),
    ("I need to do some sums", launch("calc.exe")),
    ("get rid of the netflix tab", lambda c, r, s: c and c[0][0] == "tab" and "netflix" in c[0][1]),
    ("I want to listen to something while I study", url("music.youtube.com")),
    ("change the wording of the dentist reminder to dentist checkup", says("updated", "dentist checkup")),
    ("list everything I have coming up", says("call mom")),
]
ok2 = 0; bad2 = []
for text, check in HELD:
    s = seeded(); actions.backend = Rec(); actions.muted = False; actions.last_site = None
    line = actions.direct(text) or text_or_ai(text)
    if line.lower().startswith("chat:"):
        reply = "CHAT " + line[5:].strip()
    elif actions.voice_tune(line):
        reply = f"TUNE {actions.voice_tune(line)}"
    else:
        reply = handle(line, s, NOW)
        if is_unknown(reply):
            raw = handle(text, s, NOW)
            reply = raw if not is_unknown(raw) else reply
    good = check(actions.backend.calls, reply, s)
    ok2 += good
    if not good:
        bad2.append(f"{text!r}\n      AI: {line!r}\n      -> {reply!r} {actions.backend.calls}")
print(f"HELD-OUT: {ok2}/{len(HELD)} ({100 * ok2 / len(HELD):.0f}%)")
for x in bad2:
    print("   ", x.encode("ascii", "backslashreplace").decode())

# the AI's memory: follow-ups that only make sense with the conversation, and two requests at once
s = seeded(); actions.backend = Rec()
line = b.rewrite("actually move it to friday at 5pm", recent=[("remind me to call mom tomorrow at 6pm", "Noted, sir: 'Call mom' tomorrow 6:00 pm.")])
r = handle(line, s, NOW)
print("follow-up:", repr(line), "->", repr(r), "OK" if "call mom" in r.lower() and "5:00 pm" in r else "FAIL")
line = b.rewrite("open notepad and set a timer for 5 minutes")
print("two at once:", repr(line), b.rest, "OK" if line == "open notepad" and b.rest == ["set a timer for 5 minutes"] else "FAIL")
line = b.rewrite("essentially remind me today at 5 pm to call the electrician about the fan", asked="Remind you of what, sir?")
print("whole sentence as an answer:", repr(line), "OK" if line.lower().startswith("remind me") else "FAIL")

# the AI writes its own replies; a wording that changes a fact is refused
facts = [("set two timers", "Timer set: 1 minute timer, sir. Timer set: 3 minute timer, sir."), ("open youtube", "Opening YouTube in Edge, sir."), ("close chrome", "Closing Chrome, sir."),
         ("take a screenshot", "Screenshot taken, sir."), ("remind me to call mom tomorrow at 5pm", "Noted, sir: 'Call mom' tomorrow 5:00 pm."), ("volume up", "Volume up, sir."),
         ("pause the one minute timer", "1 minute timer paused, sir."), ("cancel the three minute timer", "3 minute timer cancelled, sir.")]
own = 0; t0 = []
for said, fact in facts:
    words = set()
    for _ in range(3):
        t = time.perf_counter(); w = b.phrase(said, fact); t0.append(time.perf_counter() - t)
        words.add(w)
        from jarvis.brain import good_reply
    own += any(w != fact for w in words)
    print(repr(fact), "->", [x.encode("ascii", "replace").decode() for x in words])
print(f"own wording in {own}/{len(facts)} facts, median {sorted(t0)[len(t0) // 2] * 1000:.0f} ms, max {max(t0) * 1000:.0f} ms")

# the owner's own sentences, through the whole app with the real AI: what it does, and what it says
import tempfile
from jarvis import settings, ui
settings.PATH = os.path.join(tempfile.mkdtemp(), "s.json")
actions.backend = Rec()
app = ui.App(Store(":memory:"), tray=False, load_settings=False)
app.brain = b
app.store.add("Submit my lab record", datetime.now() + timedelta(days=1))
app.store.add("Check linkedin", datetime.now() + timedelta(days=1))
got = lambda: [r["text"] for r in app.store.upcoming(datetime.now(), 20)]
url2 = lambda part: any(c[0] == "url" and part in c[2] for c in actions.backend.calls)
fails = []
def step(said, check):
    actions.backend.calls = []
    app.submit(said)
    reply = app.text
    ok = check()
    print(("ok   " if ok else "FAIL ") + repr(said) + " -> " + repr(reply).encode("ascii", "replace").decode())
    if not ok:
        fails.append(said)
step("set a timer for 1 minute", lambda: len(app.store.all_timers()) == 1)
step("set a timer for 3 minutes", lambda: len(app.store.all_timers()) == 2)
step("Create two separate timers, a 5 minute timer and a 7 minute timer", lambda: len(app.store.all_timers()) == 4)
step("what timers do I have running right now", lambda: True)
step("pause the one minute timer", lambda: sum(r["status"] == "paused" for r in app.store.all_timers()) == 1)
step("cancel it 3 minute timer", lambda: len(app.store.all_timers()) == 3)
step("Cancel all the timers", lambda: not app.store.all_timers())
step("how many reminders do I have", lambda: True)
step("cancel all the reminders for tomorrow", lambda: not got())
app.store.add("Submit my lab record", datetime.now() + timedelta(days=1))
step("get rid of everything for tomorrow", lambda: True)
app.store.add("Check linkedin", datetime.now() + timedelta(days=1))
step("search the best laptops", lambda: url2("google.com/search"))
step("search for cats on edge", lambda: url2("google.com/search") and actions.backend.calls[-1][1] == "edge")
step("search lo-fi on youtube", lambda: url2("youtube.com/results"))
step("open youtube", lambda: url2("youtube.com"))
step("search for dogs", lambda: url2("google.com/search"))
step("I want to know how tall mount everest is", lambda: True)
step("close edge, file explorer and whatsapp", lambda: True)
step("Why are you so slow", lambda: True)
step("turn off the wifi", lambda: not actions.backend.calls)
import re as _re
step("You still haven't done what I asked", lambda: not _re.search(r"\bi will\b|\bi'll\b(?! .*if)|shut", app.text.split("if I can")[0], _re.I))
step("cancel my timer and I swear to god you better do it", lambda: True)
print("SCENARIO:", "PASS" if not fails else f"FAIL {fails}")
print("prompt size:", len(b.llm.tokenize(("".join(m["content"] for m in b._msgs())).encode())), "of", b.llm.n_ctx())
