"""Why the music test passed on recordings and failed live. On a recording the PC's sound lines up perfectly with the mic. Live, the PC-sound stream can run BEHIND the mic
(its chunks arrive late), so the sound that has to be subtracted is not there yet when the mic block that needs it is processed. This replays the owner's music recording with the
PC's sound shifted by different amounts and available only up to 'now' like the live stream; with the mic held back as needed (new) and without (old). Silent: nothing is played.
Run: py -3.12 -u tests/v2/ears_liveclock.py"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(HERE)), HERE]
import ears_replay as R  # noqa: E402
from jarvis2.ears import SR, ArraySource, Ears, Transcriber  # noqa: E402

mic, _ = R.load("music.wav")
loop, rate = R.load("music_loop.wav")
from scipy.signal import resample_poly  # noqa: E402
base = resample_poly(loop, SR, rate).astype(np.float32)[:len(mic)]      # lines up with the mic at +150 ms (2400 samples)


class Live:
    """The PC's sound, shifted so the mic hears it `lag` samples after it, and only available up to the moment the mic has reached (plus what the stream already delivered)."""

    def __init__(self, src, lag):
        self.src, self.shift = src, lag - 2400

    def get(self, start, n):
        idx = np.arange(start, start + n)
        out = np.zeros(n, np.float32)
        j = idx + self.shift                                       # sample of the recording that sits at this ring index
        ok = (j >= 0) & (j < len(base)) & (idx < self.src.i)        # nothing beyond what has been captured so far
        out[ok] = base[j[ok]]
        return out


stt = Transcriber()
stt.load()
takes = R.SESSION["music"]["takes"]
fails = 0
for lag, name in ((2400, "+150 ms (as recorded)"), (800, "+50 ms"), (-1856, "-116 ms (what the live device showed)"), (-7000, "-440 ms")):
    for held in (True, False):
        src = ArraySource(mic)
        got = []
        ears = Ears(src, Live(src, lag), stt, got.append, hint=lambda: R.VOCAB)
        if not held:
            ears.max_delay = 0
        ears.start()
        ears.join(900)
        ex = sum(R.same(" ".join(h.raw for h in got if h.started < tk["end"] + 0.5 and h.ended > tk["start"]), R.PROMPTS[tk["id"]]["say"]) for tk in takes)
        print(f"PC sound {name:40} mic held back {'as needed' if held else 'never    '}: exact {ex}/{len(takes)}  delay found {ears.lag and round(ears.lag / SR * 1000)} ms, held {ears.delay} blocks", flush=True)
        if held and ex < 26:
            fails += 1
print("LIVE CLOCK OK" if not fails else f"LIVE CLOCK PROBLEM in {fails} case(s)")
os._exit(0)
