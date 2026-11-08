"""Back-to-back commands in real time, with Jarvis really "speaking" (its voice leaks into the fake mic like a real speaker).
Also times: end of speech -> command understood. py -3.12 tests\\test_backtoback.py"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from voice_rig import FakeMic, make_voice, say16, silence
from jarvis import actions, voice as V

REPLY = {"youtube": "Opening YouTube in Edge, sir.", "netflix": "Opening Netflix in Edge, sir.", "chrome": "Opening Chrome, sir.", "notepad": "Opening Notepad, sir."}


def session(v, lines, gap, level):
    """Say each line `gap` s after the previous one ended. Returns (what was heard, ms from end of speech to heard)."""
    audio, ends = [silence(0.6)], []
    for l in lines:
        audio.append(say16(v, l))
        ends.append(sum(map(len, audio)) / V.SR)
        audio.append(silence(gap))
    audio.append(silence(4))
    m = FakeMic(np.concatenate(audio), pace=0.08)
    heard, times = [], []

    def emit(kind, p):
        if kind == "heard":
            heard.append(p)
            pos = m.i / V.SR
            done = [e for e in ends if e <= pos]
            times.append(round((pos - done[-1]) * 1000) if done else None)
            key = next((k for k in REPLY if k in p.lower()), None)
            v.speak(REPLY[key] if key else "Very well, sir.")
    v.emit = emit
    v.mic, v.stop, v.quiet_until = m, False, 0.0
    v.sink = lambda x: (m.inject(x, v.sr, level), time.sleep(len(x) / v.sr))
    th = threading.Thread(target=v._loop, args=(m,), daemon=True)
    th.start()
    m.done.wait(120)
    time.sleep(0.5)
    v.stop = True
    th.join(5)
    return heard, times


def main():
    v = make_voice()
    v._load()
    threading.Thread(target=v._speaker, daemon=True).start()
    raw, orig = [], v._heard
    v._heard = lambda *a: (raw.append(orig(*a)), raw[-1])[1]
    lines = ["Jarvis, open YouTube.", "Jarvis, open Netflix.", "Jarvis, open Chrome.", "Jarvis, open Notepad."]
    fails, all_t = 0, []
    for gap in (0.3, 0.8, 1.5):
        for level in (0.04, 0.15):  # how loud Jarvis's voice is in the mic: measured weak level, and much louder
            heard, t = session(v, lines, gap, level)
            got = sum(any(l.split()[-1][:3].lower() in h.lower() for h in heard) for l in lines)  # "Notad" = Notepad: the open command forgives that
            if got < len(lines):
                print("   every sentence the speech model wrote:", raw[-12:])
            fails += got < len(lines)
            all_t += [x for x in t if x is not None]
            print(f"gap {gap} s, echo {level}: {got}/{len(lines)} commands, end of speech -> understood {t} ms; heard {heard}")
    print("median ms", int(np.median(all_t)) if all_t else None, "RESULT", "PASS" if not fails else "FAIL")
    os._exit(1 if fails else 0)


main()
