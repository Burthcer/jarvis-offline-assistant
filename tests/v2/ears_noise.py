"""Noisy room for the new ears: the owner's real quiet recording with this laptop's own room noise added at several levels, and 20 minutes of nothing but room noise
(it must not hear a thing). Run: py -3.12 -u tests/v2/ears_noise.py   (noise 1x = the room as recorded, rms about 63; his speech is about 600)"""
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, HERE]
import ears_replay as R  # noqa: E402
from jarvis2.ears import SR, ArraySource, Ears, Transcriber  # noqa: E402

import wave  # noqa: E402

with wave.open(os.path.join(ROOT, "tests", "data", "room_noise.wav")) as w:
    noise = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
mic, _ = R.load("quiet.wav")
stt = Transcriber()
stt.load()


def run(audio):
    got = []
    ears = Ears(ArraySource(np.clip(audio, -32768, 32767)), None, stt, got.append, hint=lambda: R.VOCAB)
    t = time.time()
    ears.start()
    ears.join(3000)
    return got, ears, time.time() - t


takes = R.SESSION["quiet"]["takes"]
bad = 0
for k in (0, 1, 3, 6, 10):
    rep = np.tile(noise, len(mic) // len(noise) + 1)[:len(mic)] * k
    got, ears, secs = run(mic + rep)
    n = [t for t in takes if t["id"][0] == "n"]
    ex = nm = 0
    for tk in n:
        hit = [h for h in got if h.started < tk["end"] + 0.5 and h.ended > tk["start"]]
        text = " ".join(h.raw for h in hit)
        ex += R.same(text, R.PROMPTS[tk["id"]]["say"])
        nm += bool(hit)
    extra = [h for h in got if not any(h.started < tk["end"] + 0.5 and h.ended > tk["start"] for tk in takes)]
    print(f"room noise x{k:<2} (rms {63 * k:>4}): exact {ex}/{len(n)}  name heard {nm}/{len(n)}  false names outside his sentences {len(extra)}  ({secs:.0f} s)", flush=True)
print("-- 20 minutes of room noise only, at 1x, 3x and 6x: names heard (must be 0), Whisper runs")
for k in (1, 3, 6):
    audio = np.tile(noise, 60) * k
    got, ears, secs = run(audio)
    print(f"noise x{k}: heard {len(got)}  ignored {ears.stats['ignored']}  noise guard {ears.stats['noise_guard']}  ({secs:.0f} s for 20 min)", flush=True)
    bad += len(got)
print("NOISE TEST OK" if bad == 0 else f"FALSE TRIGGERS: {bad}")
os._exit(0)
