"""LIVE test of the real app with voice: the laptop speaks "Hey Jarvis" + commands out loud and the real microphone must hear them.
Needs working speakers + microphone and makes sound (about 2 minutes). Run: py -3.12 tests\\test_voice_live.py"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sounddevice as sd
from jarvis import actions, settings, ui
from jarvis.store import Store

_tmp = tempfile.mkdtemp(); settings.PATH = os.path.join(_tmp, "settings.json"); os.chdir(_tmp)
settings.set_autostart = lambda on: None
calls = []
class Rec:
    def open_url(self, b, u): calls.append((b, u)); return b
    def launch(self, t): calls.append(t)
    def key(self, n, c=1): calls.append((n, c))
actions.backend = Rec()
fails = []; total = 0
def check(ok, what):
    global total
    total += 1
    if not ok: fails.append(what)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_rig import say16  # the test's own speech: the plain Piper voice, not Jarvis's
app = ui.App(Store(":memory:"), tray=False, load_settings=False, voice=True)
r, v = app.root, app.voice
def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        r.update(); time.sleep(0.02)
t = time.time()
while not v.ready and time.time() - t < 60: pump(0.2)
check(v.ready, "voice loads"); print("voice ready:", v.device, v.stats)
pump(1.5)

def say_out_loud(text):
    sd.play((say16(None, text) * 0.7).astype('int16'), 16000); sd.wait()  # quieter than full scale: laptop speakers distort when pushed

def settle():  # a polite human waits until Jarvis has finished talking
    while time.time() < v.quiet_until + 0.5: pump(0.1)

def ask(cmd, wait=7):
    n = len(app.history); settle()
    say_out_loud("Hey Jarvis."); pump(2.9)  # wait for the "Yes, sir" to finish, then speak
    say_out_loud(cmd); pump(wait)
    return app.history[n:]

def breath(cmd, wait=8):  # "Hey Jarvis, <command>" in one go, no pause for the Yes
    n = len(app.history); settle()
    say_out_loud("Hey Jarvis, " + cmd); pump(wait)
    return app.history[n:]

def show(tag, h):
    print(tag, (" | ".join(f"{w}: {t}" for _, w, t, _ in h)).encode("ascii", "backslashreplace").decode()[:300])

h = ask("set a timer for ten minutes"); show("1:", h)
check(any(w == "Wake word" for _, w, _, _ in h), "wake word logged")
check(any(w == "You (voice)" for _, w, _, _ in h), "voice command logged as You (voice)")
check(any("Timer set" in t for _, w, t, _ in h), "timer set by voice")

h = breath("open youtube"); show("2 one breath:", h)
check(("edge", "https://www.youtube.com") in calls, "one breath: 'Hey Jarvis, open YouTube' works")
check(any("stayed quiet" in t for _, w, t, _ in h), "one breath: Jarvis did not say Yes over the user")

h = breath("remind me to call mom tomorrow at five pm"); show("3 one breath:", h)
check(any("Noted" in t for _, w, t, _ in h), "one breath reminder")

# Jarvis asks "when?", and the time alone (no wake word) completes it
h = ask("remind me to buy milk"); show("4 asks:", h)
check(any("When would you like" in t for _, w, t, _ in h), "Jarvis asks when")
settle(); n = len(app.history); say_out_loud("tomorrow at six pm"); pump(7); h = app.history[n:]; show("4 answer:", h)
check(any("Noted" in t and "Buy milk" in t for _, w, t, _ in h), "answer to the question works without 'Hey Jarvis'")

h = ask("speak slower"); show("5:", h)
check(v.speed < 1.0 and abs(app.cfg["tts_speed"] - 0.85) < 0.01, f"voice speed lowered ({v.speed})")
h = ask("increase your volume"); show("6:", h); check(v.volume > 0.8, f"voice volume raised ({v.volume})")

# microphone off: the wake word is ignored; back on: works again
app.toggle_mic(); pump(0.5)
n = len(app.history); say_out_loud("Hey Jarvis."); pump(3)
check(not any(w == "Wake word" for _, w, _, _ in app.history[n:]), "mic off: wake word ignored")
app.toggle_mic(); pump(0.5)
h = ask("what do we have today", 6); show("7:", h); check(any(w == "You (voice)" for _, w, _, _ in h), "mic back on: works again")

# Jarvis must never answer his own voice
voice_cmds = [t for _, w, t, _ in app.history if w == "You (voice)"]
check(not any("I'm afraid" in t or "Noted" in t or "sir" in t.lower() for t in voice_cmds), f"never answers its own voice: {voice_cmds}")
check(len(voice_cmds) <= 9, f"no runaway repetition ({len(voice_cmds)} voice commands)")

# silence after the wake word: no crash, goes back to idle
n = len(app.history); say_out_loud("Hey Jarvis."); pump(10)
check(app.state_name in ("idle", "speaking"), f"back to idle after silence ({app.state_name})")
print("FULL LOG:"); [print("  ", ts, w, "|", str(t).encode("ascii", "backslashreplace").decode()[:150]) for ts, w, t, _ in app.history]
print("stats:", v.stats)
app.quit()
print(f"LIVE VOICE: {total - len(fails)}/{total}  {'PASS' if not fails else 'FAIL'}")
for f in fails: print("  ", f)
