"""Voice test with the REAL models and generated speech through a fake microphone (no speakers, no human). ~5 minutes.
Run: py -3.12 tests\\test_voice.py
A  wake word: hit rate across speed (=pitch), loudness and noise      B  false triggers on other phrases/noise
C  end to end: speech -> text -> handle() gives the same answer as typing the sentence
Limit: ONE synthetic voice, so real human speech can only do worse. Real-mic checks are separate."""
import os
import sys
import time
from datetime import datetime

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_rig import make_voice, noisy, run, say16, silence
from jarvis import actions
from jarvis.core import handle
from jarvis.store import Store

NOW = datetime(2026, 10, 31, 10, 0)
rng = np.random.default_rng(1)
v = make_voice(); v._load()
print(f"loaded in {v.stats['load_s']} s, speech model on {v.device}")


def vary(x, f):  # f<1 slower/lower voice, f>1 faster/higher: a cheap stand-in for different speakers
    return resample_poly(x.astype(np.float32), 100, int(100 * f)).astype(np.int16)


def woke(ev):
    return [e for e in ev if e[0] == "wake"]


# ---- A: wake word hit rate ----
hits = tot = 0; scores = []; miss = []
for phrase in ("Hey Jarvis.", "Hey Jarvis", "hey jarvis"):
    for f in (0.9, 1.0, 1.1):
        for snr in (None, 25, 15):
            for amp in (1.0, 0.3):
                x = vary(say16(v, phrase), f)
                x = (x * amp).astype(np.int16)
                if snr:
                    x = noisy(x, snr, rng)
                ev = run(v, np.concatenate([silence(1), x, silence(5.5)]))
                w = woke(ev); tot += 1; hits += bool(w)
                if w: scores.append(w[0][1]["score"])
                else: miss.append((phrase, f, snr, amp))
print(f"A wake word detected: {hits}/{tot} ({100 * hits / tot:.0f}%), median score {np.median(scores):.2f}; misses: {miss[:8]}")

# ---- B: false triggers ----
falses = []
for phrase in ("Hey Google.", "Hey service.",  # "Jarvis." alone is now meant to wake "Open YouTube.", "Remind me to call mom tomorrow at five pm.",
               "What do we have today?", "Hey there.", "Okay Google.", "Hey Siri.", "Dark service.", "Hey Harvey."):
    for f in (0.9, 1.1):
        ev = run(v, np.concatenate([silence(1), vary(say16(v, phrase), f), silence(5.5)]))
        if woke(ev): falses.append((phrase, f, woke(ev)[0][1]["score"]))
noise = noisy(np.zeros(16000 * 60, dtype=np.int16) + 1, 1, rng)  # 60 s of hiss
noise = (rng.normal(0, 800, 16000 * 60)).astype(np.int16)
n_ev = woke(run(v, noise, timeout=120))
conv = np.concatenate([np.concatenate([say16(v, s), silence(0.8)]) for s in
                       ("Please open the document and check the third paragraph.", "I think the meeting is at five thirty tomorrow.", "Can you tell me what the weather is like?",
                        "My friend Jarvis lives in Pune.", "Turn off the lights in the kitchen.", "The service was quite good yesterday.")] * 4)
c_ev = woke(run(v, conv, timeout=120))
print(f"B false triggers: phrases {len(falses)} {falses[:6]}; 60 s hiss {len(n_ev)}; 4 min of ordinary talk (incl. 'my friend Jarvis') {len(c_ev)}")

# ---- C: end to end vs typing ----
SEED = ["remind me to call mom tomorrow at 5pm", "remind me maths exam on 23 november", "remember my locker number is 42"]
CASES = [
    "remind me to call mom tomorrow at five pm", "remind me to take medicine at eight thirty in the morning", "remind me to submit the form on friday",
    "remind me in ten minutes to check the rice", "remind me to pay fees on the fifth of december", "set a timer for ten minutes", "set a timer for ninety seconds",
    "open youtube", "open linkedin", "open youtube music", "open gemini", "open netflix", "open amazon", "open claude console", "open luma", "open dev dot to",
    "open chrome", "open notepad", "open calculator", "search lo-fi beats on youtube", "search python jobs on linkedin", "google weather in pune", "play some music",
    "volume up", "volume down", "set volume to forty", "mute", "pause", "next song", "what do we have today", "what did I miss yesterday", "what's on tomorrow",
    "what do I have this week", "remember my wifi password is sunshine", "what is my locker number", "snooze for ten minutes", "move the maths exam to the twenty sixth",
    "I'm done with the maths exam", "make edge my default browser", "open the bank", "speak slower", "what can you do",
]
class Rec:
    def __init__(self): self.calls = []
    def open_url(self, b, u): self.calls.append(("url", b, u)); return b
    def launch(self, t): self.calls.append(("launch", t))
    def key(self, n, c=1): self.calls.append(("key", n, c))


def result(text):
    s = Store(":memory:")
    for x in SEED: handle(x, s, NOW)
    actions.backend = Rec(); actions.muted = False
    t = actions.voice_tune(text)
    out = f"TUNE {t}" if t else handle(text, s, NOW)
    return out, actions.backend.calls


ok = tot = 0; bad = []; stt_ms = []
for text in CASES:
    want = result(text)
    for tag, f, snr in (("clean", 1.0, None), ("slow", 0.92, None), ("fast", 1.1, 20)):
        x = vary(say16(v, text), f)
        if snr: x = noisy(x, snr, rng)
        audio = np.concatenate([silence(1), say16(v, "Hey Jarvis."), silence(1.2), x, silence(3)])
        ev = run(v, audio); heard = [e[1] for e in ev if e[0] == "heard"]
        tot += 1
        if heard and result(heard[0]) == want:
            ok += 1; stt_ms.append(v.stats["stt_ms"])
        else:
            bad.append((text, tag, heard[0] if heard else None))
print(f"C end to end same-as-typing: {ok}/{tot} ({100 * ok / tot:.0f}%), speech-to-text time median {np.median(stt_ms):.0f} ms (max {max(stt_ms)})")
for b in bad:
    print("   MISMATCH", str(b).encode("ascii", "backslashreplace").decode())

# simple pass bar for the synthetic voice (real speech can only do worse: see the real-mic checks)
print("RESULT", "PASS" if hits / 54 >= 0.9 and not falses and not n_ev and not c_ev and ok / tot >= 0.97 else "NEEDS WORK")
