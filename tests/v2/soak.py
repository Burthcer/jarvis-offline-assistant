"""Soak: one long-lived Jarvis (real AI, replies reworded, pretend PC) takes hundreds of sentences in a row. Watches memory, graphics memory, heat, speed, errors,
and that the AI can be unloaded and loaded again. Run: py -3.12 -u tests/v2/soak.py [--turns 800]   Prints a line every 100 turns, then the verdict."""
import os
import random
import sys
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, HERE]
from gold_text import ALL  # noqa: E402
from harness import fresh  # noqa: E402

from jarvis2.ai import AI, DEFAULT_MODEL  # noqa: E402

turns = int(sys.argv[sys.argv.index("--turns") + 1]) if "--turns" in sys.argv else 800
random.seed(7)
texts = [t for t, e, o in ALL if not o.get("ctx")]
ai = AI(DEFAULT_MODEL)
app, os_, store = fresh(ai)
proc = psutil.Process()


def gpu():
    out = os.popen("nvidia-smi --query-gpu=memory.used,temperature.gpu,power.draw --format=csv,noheader,nounits").read().strip().split(",")
    return int(out[0]), int(out[1]), float(out[2])


times, errors, crashes, rows = [], 0, 0, []
t_start = time.time()
for i in range(1, turns + 1):
    t = random.choice(texts)
    if i % 200 == 0:
        ai.unload()                                   # the 15-minute idle unload, forced: the next turn must load it again
    t0 = time.perf_counter()
    try:
        r = app.handle(t)
        errors += bool(r.error)
    except Exception as ex:
        crashes += 1
        print("CRASH", repr(t), repr(ex)[:120], flush=True)
    times.append((time.perf_counter() - t0) * 1000)
    if i % 100 == 0:
        mem, temp, w = gpu()
        rows.append((i, proc.memory_info().rss / 2**30, mem, temp))
        recent = sorted(times[-100:])
        print(f"turn {i}: RAM {rows[-1][1]:.2f} GB, graphics {mem} MiB, GPU {temp} C {w:.0f} W, median {recent[50]:.0f} ms, p95 {recent[95]:.0f} ms, errors {errors}, crashes {crashes}, "
              f"history {len(app.history)}, events {app.memory.counts()['events']}", flush=True)
grow_ram = rows[-1][1] - rows[1][1] if len(rows) > 2 else 0
grow_gpu = rows[-1][2] - rows[1][2] if len(rows) > 2 else 0
print(f"{turns} turns in {(time.time() - t_start) / 60:.1f} min. RAM growth after turn 200: {grow_ram * 1024:+.0f} MB; graphics growth: {grow_gpu:+d} MiB; max GPU temp {max(r[3] for r in rows)} C; crashes {crashes}; errors {errors}")
ok = crashes == 0 and grow_ram < 0.15 and grow_gpu < 150
print("SOAK OK" if ok else "SOAK FAILED")
ai.unload()
sys.exit(0 if ok else 1)
