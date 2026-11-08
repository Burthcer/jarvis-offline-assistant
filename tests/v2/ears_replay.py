"""Phase 4 replay: the owner's own recordings (data/gold/audio, git-ignored) through the NEW ears, faster than real time.
Run: py -3.12 tests/v2/ears_replay.py [quiet|music|earphones ...] [--nocancel] [--noearly]
Prints per recording: commands heard exactly / name heard / pieces, false names outside his sentences, speed. Baselines (stage 1 spike, same recordings):
quiet exact 35/40 name 40/40; music (cancelled) 29/30 name 30/30 (raw 20/30); earphones 18/20 name 20/20; sentences not for Jarvis ignored 7 of 8."""
import json
import os
import re
import sys
import time
import wave

import numpy as np
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT]
from jarvis2.ears import SR, ArraySource, Ears, Transcriber  # noqa: E402

AUD = os.path.join(ROOT, "data", "gold", "audio")
PROMPTS = {x["id"]: x for g in json.load(open(os.path.join(HERE, "prompts.json"), encoding="utf-8")).values() for x in g}
SESSION = json.load(open(os.path.join(AUD, "session.json"), encoding="utf-8"))["sections"]
NUM = {"forty": "40", "ten": "10", "three": "3", "two": "2", "five": "5", "twenty": "20"}
VOCAB = "Jarvis, YouTube, Gemini, Chrome, Edge, WhatsApp, Hostinger, Obsidian, Armoury Crate, Wisperno Pro, Wispr Flow, LinkedIn, Luma, Gmail, Claude, ChatGPT, File Explorer, Task Manager, timer, reminder, volume."


def load(fn):
    with wave.open(os.path.join(AUD, fn)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32), w.getframerate()


def norm(s):
    s = re.sub(r"(\d),(\d)", r"\1\2", s.lower()).replace("'", "").replace("-", " ").replace("pm", " pm")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"^(hey |hi |ok )?jarvis\b", " ", s.strip())
    return " ".join(NUM.get(w, w) for w in s.split())


def same(heard, say):
    return norm(heard).replace(" ", "") == norm(say).replace(" ", "")


class Ref:
    """The PC's sound from the recording of the loopback, on the mic's clock."""

    def __init__(self, ref):
        self.src = ArraySource(ref)

    def get(self, start, n):
        return self.src.get(start, n)


def replay(section, stt, cancel=True, early=True):
    mic, _ = load(f"{section}.wav")
    ref = None
    if cancel and os.path.exists(os.path.join(AUD, f"{section}_loop.wav")):
        lb, rate = load(f"{section}_loop.wav")
        ref = Ref(resample_poly(lb, SR, rate).astype(np.float32)[:len(mic)])
    got = []
    import jarvis2.ears as E
    if not early:
        E.EARLY_BLOCKS = 10 ** 6
    src = ArraySource(mic)
    if '--realtime' in sys.argv:
        _read = src.read
        def slow():
            time.sleep(E.BLOCK_S)
            return _read()
        src.read = slow
    ears = Ears(src, ref, stt, got.append, hint=lambda: VOCAB)
    if '--quick' in sys.argv:                  # act on a complete command without waiting out the pause, as the app now does
        sys.path.insert(0, HERE)
        from harness import fresh
        ears.is_complete = fresh(None)[0].is_complete
    t = time.time()
    ears.start()
    ears.join(1800)
    secs = time.time() - t
    takes = SESSION[section]["takes"]
    rows = []
    for tk in takes:
        hit = [h for h in got if h.started < tk["end"] + 0.5 and h.ended > tk["start"]]
        rows.append({"id": tk["id"], "say": PROMPTS[tk["id"]]["say"], "heard": " ".join(h.raw for h in hit), "name": bool(hit), "pieces": len(hit)})
        rows[-1]["exact"] = same(rows[-1]["heard"], rows[-1]["say"])
    n = [r for r in rows if r["id"][0] == "n"]
    x = [r for r in rows if r["id"][0] == "x"]
    extra = [h for h in got if not any(h.started < tk["end"] + 0.5 and h.ended > tk["start"] for tk in takes)]
    print(f"{section}{'' if cancel else ' (no cancel)'}{'' if early else ' (no early start)'}: exact {sum(r['exact'] for r in n)}/{len(n)}  name {sum(r['name'] for r in n)}/{len(n)}  "
          f"one piece {sum(r['pieces'] == 1 for r in n)}/{len(n)}  no-name speech acted on {sum(r['name'] for r in x)}/{len(x)}  extra names outside sentences {len(extra)}  "
          f"lag {None if ears.lag is None else round(ears.lag / SR * 1000)} ms  stats {dict(ears.stats)}  ({secs:.0f} s for {len(mic) / SR:.0f} s of audio)")
    w2 = sorted(h.wait_ms for h in got)
    print(f"   wait after the pause ends (wall clock, replay): median {w2[len(w2) // 2] if w2 else 0} ms")
    waits = sorted(h.stt_ms for h in got)
    if waits:
        print(f"   whisper per sentence: median {waits[len(waits) // 2]} ms, max {waits[-1]} ms")
    json.dump(rows, open(os.path.join(ROOT, "data", "gold", "results", f"ears2_{section}{'' if cancel else '_nc'}.json"), "w", encoding="utf-8"), indent=0)
    return rows


if __name__ == "__main__":
    secs = [a for a in sys.argv[1:] if not a.startswith("--")] or list(SESSION)
    stt = Transcriber()
    stt.load()
    for s in secs:
        replay(s, stt, "--nocancel" not in sys.argv, "--noearly" not in sys.argv)
    print("gpu", os.popen("nvidia-smi --query-gpu=memory.used,temperature.gpu --format=csv,noheader").read().strip())
