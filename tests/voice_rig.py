"""Shared rig for voice tests: feed generated speech to the real Voice pipeline through a fake microphone (no speakers, no human)."""
import os
import sys
import threading
import time

import numpy as np
from scipy.signal import resample_poly

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis import voice as V


class FakeMic:
    def __init__(self, audio, pace=0.0):
        self.a, self.i, self.done, self.pace = audio, 0, threading.Event(), pace

    def inject(self, x, rate, level=0.04):
        """Jarvis's own voice reaching the mic as a faint echo (measured: about 3-4% of full level on this laptop)."""
        e = resample_poly(x.astype(np.float32), 16000, rate) * level
        end = self.i + len(e)
        if end > len(self.a):
            self.a = np.concatenate([self.a, np.zeros(end - len(self.a), dtype=np.int16)])
        self.a[self.i:end] = np.clip(self.a[self.i:end].astype(np.float32) + e, -32768, 32767).astype(np.int16)

    def read(self, n):
        if self.pace:
            time.sleep(self.pace)  # real-time pacing (80 ms per chunk) for tests that depend on wall-clock waits
        if self.i >= len(self.a):
            self.done.set(); time.sleep(0.05)
            return np.zeros((n, 1), dtype=np.int16), False
        x = self.a[self.i:self.i + n]; self.i += n
        if len(x) < n:
            x = np.concatenate([x, np.zeros(n - len(x), dtype=np.int16)])
        return x[:, None], False


def make_voice():
    ev = []
    v = V.Voice(lambda k, p: ev.append((k, p, time.perf_counter())), watch=False)
    v.sink = lambda x: None
    v.events = ev
    return v


_PIPER = None


def say16(v, text, speed=1.0):
    """Generated TEST speech at the mic's 16 kHz: always the plain Piper voice (not Jarvis's own voice), so results stay comparable."""
    global _PIPER
    from piper import PiperVoice, SynthesisConfig
    _PIPER = _PIPER or PiperVoice.load(V.PIPER)
    cfg = SynthesisConfig(length_scale=1.0 / speed, noise_scale=0.667, noise_w_scale=0.8)
    a = np.frombuffer(b"".join(c.audio_int16_bytes for c in _PIPER.synthesize(text, syn_config=cfg)), dtype=np.int16).astype(np.float32)
    return resample_poly(a, 320, 441).astype(np.int16)  # 22050 -> 16000


def silence(sec):
    return np.zeros(int(V.SR * sec), dtype=np.int16)


def noisy(x, snr_db, rng):
    p = np.mean(x.astype(np.float32) ** 2) + 1e-9
    n = rng.normal(0, np.sqrt(p / 10 ** (snr_db / 10)), len(x))
    return (x + n).clip(-32768, 32767).astype(np.int16)


def run(v, audio, timeout=60, pace=0.0):
    """Run the pipeline over `audio`; returns the events that happened."""
    v.events.clear()
    v.quiet_until = 0.0
    m = FakeMic(audio, pace)
    v.mic, v.stop = m, False
    # real-time runs: Jarvis's own voice leaks into the mic and playing takes its real time, like a real speaker
    v.sink = (lambda x: (m.inject(x, v.sr), time.sleep(len(x) / v.sr))) if pace else (lambda x: None)
    th = threading.Thread(target=v._loop, args=(m,), daemon=True); th.start()
    m.done.wait(timeout); time.sleep(0.4)
    v.stop = True; th.join(5)
    return list(v.events)
