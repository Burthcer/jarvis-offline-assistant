"""The speech-check wake route (for voices the wake model scores low): ONLY this route is allowed to wake, played in real time.
Positives must wake; similar-sounding phrases must be rejected. Also tests the 'keep talking' route ("Hey Jarvis, open YouTube" in one breath).
Run: py -3.12 tests\\test_wake_check.py   (~3 minutes)"""
import os
import sys

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_rig import make_voice, run, say16, silence
from jarvis import voice as V

v = make_voice(); v._load()
V.THRESH = 9.0  # the model alone can never wake: everything has to pass the speech check
vary = lambda x, f: resample_poly(x.astype(np.float32), 100, int(100 * f)).astype(np.int16)
fails = []; total = 0

for f in (0.85, 0.95, 1.0, 1.1, 1.2):
    total += 1
    ev = run(v, np.concatenate([silence(1), vary(say16(v, "Hey Jarvis."), f), silence(2.5)]), pace=0.08)
    w = [p for k, p, _ in ev if k == "wake"]
    print("positive pitch x%.2f ->" % f, w[:1] or [p for k, p, _ in ev if k == "near"])
    if not w: fails.append(f"check route missed 'Hey Jarvis' at pitch x{f}")
for ph in ("Hey Google.", "Hey Harvey.", "Hey service.", "Hey Siri.", "Okay.", "Open YouTube.", "Hey there.", "What do we have today?"):
    total += 1
    ev = run(v, np.concatenate([silence(1), say16(v, ph), silence(2.5)]), pace=0.08)
    w = [p for k, p, _ in ev if k == "wake"]
    print("negative %-24s ->" % ph, "WOKE (bad)" if w else "ignored")
    if w: fails.append(f"check route woke on {ph!r}")

# one breath: wake word and command together -> Jarvis must stay quiet and still get the command
V.THRESH = 0.5
for cmd in ("Open YouTube.", "Set a timer for ten minutes.", "What do we have today?"):
    total += 1
    ev = run(v, np.concatenate([silence(1), say16(v, "Hey Jarvis,"), say16(v, cmd), silence(3)]), pace=0.08)
    heard = [p for k, p, _ in ev if k == "heard"]; w = [p for k, p, _ in ev if k == "wake"]
    print("one breath", repr(cmd), "->", w[:1], heard)
    expect = {"Open YouTube.": "open youtube", "Set a timer for ten minutes.": "timer for 10 minutes", "What do we have today?": "what do we have today"}[cmd]
    if not heard or expect not in heard[0].lower():
        fails.append(f"one-breath command {cmd!r} -> {heard}")
# just the name wakes; "Jarvis" inside ordinary talk must NOT
for phrase, want in (("Jarvis.", True), ("My friend Jarvis lives in Pune.", False), ("I watched Iron Man and Jarvis was great.", False)):
    total += 1
    ev = run(v, np.concatenate([silence(1), say16(v, phrase), silence(3)]), pace=0.08)
    w = bool([p for k, p, _ in ev if k == "wake"])
    print("name test", repr(phrase), "->", "woke" if w else "ignored")
    if w != want:
        fails.append(f"{phrase!r} woke={w}, want {want}")

# Jarvis asked a question: the answer is heard with no wake word
for ans in ("up", "ten minutes"):
    total += 1
    v.followup = True
    ev = run(v, np.concatenate([silence(0.5), say16(v, ans + "."), silence(2.5)]), pace=0.08)
    heard = [p for k, p, _ in ev if k == "heard"]
    print("follow-up", repr(ans), "->", heard)
    if not heard or ans.split()[0] not in heard[0].lower().replace("10", "ten"):
        fails.append(f"follow-up {ans!r} -> {heard}")

print(f"WAKE CHECK: {total - len(fails)}/{total}  {'PASS' if not fails else 'FAIL'}")
for f in fails:
    print("  ", f)
