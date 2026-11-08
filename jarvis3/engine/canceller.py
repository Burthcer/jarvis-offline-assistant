"""The listening front end (plan 13.9, 1 and 2): subtract what the PC is playing from the mic, and say where there is speech.
Streaming version of the spike's cancel_echo(live=True): a frequency-domain adaptive filter (overlap-save) that learns how the speaker reaches the mic,
and learns ONLY while the voice detector hears no speech in its own output (0.8 s hold), so it never learns the owner's voice as echo."""
import numpy as np
from scipy.signal import fftconvolve

SR = 16000
BLOCK = 2048          # 128 ms
GAIN, THRESHOLD = 4, 0.35
HOLD = 6              # blocks (0.77 s) without learning after speech
QUIET_REF = 25        # rms of the PC sound below which there is nothing to cancel


def rms(x):
    return float(np.sqrt(np.mean(x.astype(np.float32) ** 2))) if len(x) else 0.0


def find_delay(mic, ref, max_s=1.0):
    """Samples by which the mic hears the speaker AFTER the reference (cross-correlation), or None if the two don't match.
    Only the stretches where the PC is playing (and up to max_s after them) count: a 2 second reply in a 10 second window is all there is to go on."""
    n = min(len(mic), len(ref))
    if n < SR * 3 or rms(ref[:n]) < QUIET_REF:
        return None
    a, b = mic[:n].astype(np.float32), ref[:n].astype(np.float32)
    env = fftconvolve(np.abs(b), np.ones(800) / 800, "same")
    on = env > max(0.15 * env.max(), QUIET_REF)
    if on.sum() < SR * 0.8:
        return None
    k = int(SR * max_s)
    near = fftconvolve(on.astype(np.float32), np.ones(2 * k + 1), "same") > 0.5       # where an echo can be
    a, b = a * near, b * on
    c = np.fft.irfft(np.fft.rfft(a, 2 * n) * np.conj(np.fft.rfft(b, 2 * n)))
    c = np.concatenate([c[-k:], c[:k + 1]])               # lags -k .. +k
    i = int(np.argmax(np.abs(c)))
    # music through the speakers matches the mic at 0.15 to 0.22 (measured on the owner's recordings); music in earphones, which the mic can't hear, at 0.01 to 0.02
    if abs(c[i]) < 0.05 * np.linalg.norm(a) * np.linalg.norm(b) + 1e-9:
        return None
    return i - k


class Canceller:
    def __init__(self):
        from openwakeword.vad import VAD
        self.vad = VAD()
        self.W, self.P = np.zeros(BLOCK + 1, complex), np.ones(BLOCK + 1) * 1e6
        self.hold = 0
        self.cancelling = False   # last block had PC sound to cancel (for reports)

    def reset(self):
        """A new output device: the old room response is wrong."""
        self.W[:] = 0
        self.P[:] = 1e6

    def feed(self, mic, ref2):
        """mic: one block (BLOCK samples). ref2: the reference for this block AND the one before (2*BLOCK samples), already time-aligned.
        -> (clean block float32, [voice probability per 640 samples])"""
        mic = mic.astype(np.float32)
        self.cancelling = rms(ref2) >= QUIET_REF
        if self.cancelling:
            X = np.fft.rfft(ref2.astype(np.float32))
            e = mic - np.fft.irfft(self.W * X)[BLOCK:]
        else:
            e = mic
        probs = [self.vad.predict(np.clip(e[j:j + 640] * GAIN, -32768, 32767).astype(np.int16), frame_size=640) for j in range(0, BLOCK - 639, 640)]
        speech = max(probs) > THRESHOLD
        self.hold = HOLD if speech else max(0, self.hold - 1)
        if self.cancelling and self.hold == 0:
            E = np.fft.rfft(np.concatenate([np.zeros(BLOCK), e]))
            self.P = 0.9 * self.P + 0.1 * np.abs(X) ** 2
            g = np.fft.irfft(np.conj(X) * E / (self.P + 1e6))
            g[BLOCK:] = 0
            self.W += 0.05 * np.fft.rfft(g)
        return np.clip(e, -32768, 32767), probs
