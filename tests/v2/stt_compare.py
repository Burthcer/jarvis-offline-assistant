"""Which speech model hears the owner best? His own recorded sentences (data/gold/audio, 106 of them, quiet / music with the PC's sound cancelled / earphones), each cut out like a held-key clip
so only the MODEL is compared, with the same vocabulary hint. Silent: files only. Run: py -3.12 -u tests/v2/stt_compare.py large-v3 distil-large-v3.5 ...   (turbo is always included)
Prints exact sentences right (the app/name words must be exactly right), how many named Jarvis correctly, time per clip, graphics memory."""
import glob
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, HERE]
import ears_replay as R  # noqa: E402
from jarvis import voice as V  # noqa: E402

V._cuda()
from faster_whisper import WhisperModel  # noqa: E402

HINT = "Jarvis, Youtube, Edge, Whatsapp, Explorer, File Explorer, Claude, Linkedin, Obsidian, Chrome, Gemini, Discord, Quick Share, Task Manager, Wisperno, Wisperno Pro, Wispr Flow, Amazon, Antigravity, Luma, Youtube Music, Patreon."
SECTIONS = {"quiet": "quiet.wav", "music": "music_cancelled.wav", "earphones": "earphones.wav"}


def gpu():
    return int(os.popen("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits").read().strip())


def load(name):
    if name == "turbo":
        path = next(iter(sum((glob.glob(g) for g in V.WHISPER_GLOBS), [])))
        return WhisperModel(path, device="cuda", compute_type="int8_float16")
    return WhisperModel(name, device="cuda", compute_type=os.environ.get("CT", "int8_float16"))


names = ["turbo"] + sys.argv[1:]
audio = {s: R.load(f)[0] for s, f in SECTIONS.items()}
for name in names:
    base = gpu()
    t0 = time.time()
    m = load(name)
    m.transcribe(np.zeros(16000, np.float32), language="en")
    used = gpu() - base
    print(f"== {name}: loaded in {time.time() - t0:.0f} s, graphics memory +{used} MiB", flush=True)
    tot = ex = nm = 0
    times = []
    for sec, a in audio.items():
        e = n = c = 0
        for tk in R.SESSION[sec]["takes"]:
            if tk["id"][0] != "n":
                continue
            x = a[int(max(0, tk["start"] - 0.2) * 16000):int((tk["end"] + 0.3) * 16000)] / 32768
            t = time.perf_counter()
            segs, _ = m.transcribe(x, language="en", beam_size=int(os.environ.get("BEAM", "1")), best_of=1, temperature=0.0, condition_on_previous_text=False, initial_prompt=HINT, vad_filter=False)
            text = " ".join(s.text.strip() for s in segs).strip()
            times.append((time.perf_counter() - t) * 1000)
            c += 1
            e += R.same(text, R.PROMPTS[tk["id"]]["say"])
            n += "jarvis" in text.lower()[:25]
        print(f"   {sec:10} exact {e}/{c}   'Jarvis' heard {n}/{c}", flush=True)
        tot += c; ex += e; nm += n
    times.sort()
    print(f"   TOTAL exact {ex}/{tot} ({100 * ex / tot:.0f}%)  name {nm}/{tot}  median {times[len(times) // 2]:.0f} ms per clip, max {times[-1]:.0f} ms", flush=True)
    del m
os._exit(0)
