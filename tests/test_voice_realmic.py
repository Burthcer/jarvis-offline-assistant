"""Realistic microphone test: speech mixed into REAL room noise recorded from the owner's laptop mic (tests/data/room_noise.wav),
at weak levels like a quiet laptop mic, through the full voice pipeline in real time. No speakers involved.
Checks: wakes, hears the command, and handle(heard) gives the same result as typing it. Both styles:
  pause  : "Hey Jarvis." ... wait for the Yes ... command
  breath : "Hey Jarvis, <command>" in one go (must NOT say Yes over it)
Run: py -3.12 tests\\test_voice_realmic.py   (~6 minutes)"""
import os
import re
import sys
import wave
from datetime import datetime

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_rig import make_voice, run, say16
from jarvis import actions
from jarvis.core import handle
from jarvis.store import Store

with wave.open(os.path.join(os.path.dirname(__file__), "data", "room_noise.wav")) as w:
    NOISE = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
NOISE_GAIN = float(os.environ.get("NOISE_GAIN", "1"))  # 20 ~ the mic set to 100% (the owner's noise went from rms 63 to ~1500)
NOISE *= NOISE_GAIN
NOW = datetime(2026, 10, 31, 10, 0)
v = make_voice(); v._load()
rng = np.random.default_rng(5)


def at_level(x, rms):
    x = x.astype(np.float32)
    voiced = x[np.abs(x) > np.abs(x).max() * 0.1]
    return x * (rms * NOISE_GAIN / max(1.0, np.sqrt(np.mean(voiced ** 2))))


def scene(parts):
    """parts: list of (seconds of gap) or (speech array). Returns speech + looping real room noise."""
    s = np.concatenate([np.zeros(int(16000 * p), np.float32) if isinstance(p, (int, float)) else p for p in parts])
    start = rng.integers(0, len(NOISE) - 1)
    n = np.resize(np.roll(NOISE, -start), len(s))
    return np.clip(s + n, -32768, 32767).astype(np.int16)


class Rec:
    def __init__(self): self.calls = []
    def open_url(self, b, u): self.calls.append(("url", b, u)); return b
    def launch(self, t): self.calls.append(("launch", t))
    def key(self, n, c=1): self.calls.append(("key", n, c))


def result(text):
    s = Store(":memory:")
    actions.backend = Rec(); actions.muted = False
    t = actions.voice_tune(text)
    return (f"TUNE {t}" if t else handle(text, s, NOW)), actions.backend.calls


CMDS = ["set a timer for ten minutes", "open youtube", "remind me to call mom tomorrow at five pm", "what do we have today",
        "increase your volume", "search lo-fi beats on youtube", "volume down", "how much time is left on my timer"]
tot = ok = 0; bad = []; per = {}
for level in [int(x) for x in os.environ.get("LEVELS", "150,300,600").split(",")]:
    for mode in ("pause", "breath", "overlap", "name"):
        good = 0
        for cmd in CMDS:
            if mode == "pause":
                audio = scene([1.0, at_level(say16(v, "Hey Jarvis."), level), 2.6, at_level(say16(v, cmd + "."), level), 3.0])
            elif mode == "overlap":  # starts the command while Jarvis is still saying "Yes, sir" (its voice leaks into the mic as a faint echo)
                audio = scene([1.0, at_level(say16(v, "Hey Jarvis."), level), 1.0, at_level(say16(v, cmd + "."), level), 3.0])
            elif mode == "name":  # just "Jarvis, <command>" (no "Hey")
                audio = scene([1.0, at_level(say16(v, "Jarvis, " + cmd + "."), level), 3.0])
            else:
                audio = scene([1.0, at_level(say16(v, "Hey Jarvis, " + cmd + "."), level), 3.0])
            ev = run(v, audio, timeout=40, pace=0.08)
            heard = [p for k, p, _ in ev if k == "heard"]
            wake = [p for k, p, _ in ev if k == "wake"]
            spoke_over = mode in ("breath", "name") and wake and not any(w in wake[0]["via"] for w in ("continuing", "said it all"))
            fine = bool(heard) and result(re.sub(r"\b(mum|mam|mon)\b", "mom", heard[0], flags=re.I)) == result(cmd)  # British "mum" is fine
            tot += 1; ok += fine; good += fine
            if not fine:
                bad.append((level, mode, cmd, wake[0]["via"] if wake else "NO WAKE", heard[:1]))
            elif spoke_over:
                bad.append((level, mode, cmd, "worked, but said Yes over the user", heard[:1]))
        per[(level, mode)] = f"{good}/{len(CMDS)}"
        print(f"speech rms {level:4d} (room noise rms {np.sqrt(np.mean(NOISE ** 2)):.0f}) {mode:6s}: {good}/{len(CMDS)}", flush=True)
print(f"REAL-MIC SIM: {ok}/{tot} ({100 * ok / tot:.0f}%)")
for b in bad:
    print("   ", str(b).encode("ascii", "backslashreplace").decode())
