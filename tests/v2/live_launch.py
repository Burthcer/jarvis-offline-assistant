"""The real thing: starts Jarvis V2 the way the icon would (Jarvis2.pyw, real PC, real mic and speakers, nothing is typed or said), times the start, measures memory, graphics memory,
CPU and heat after a minute, then closes it the way the X does and checks that nothing is left. It plays 'Ready, sir.' once. Run: py -3.12 -u tests/v2/live_launch.py"""
import ctypes
import os
import subprocess
import sys
import time

import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG = os.path.join(ROOT, "logs", "jarvis2.log")


def gpu():
    return os.popen("nvidia-smi --query-gpu=memory.used,temperature.gpu,power.draw,utilization.gpu --format=csv,noheader").read().strip()


def window():
    u = ctypes.windll.user32
    u.FindWindowW.restype = ctypes.c_void_p
    return u.FindWindowW(None, "Jarvis V2")


before = os.path.getsize(LOG) if os.path.exists(LOG) else 0
t0 = time.time()
p = subprocess.Popen([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(ROOT, "Jarvis2.pyw")], cwd=ROOT, env={**os.environ, "JARVIS_SILENT": "1"})   # silent: nothing comes out of the speakers
proc = psutil.Process(p.pid)
while not window() and time.time() - t0 < 30:
    time.sleep(0.2)
print(f"window on screen after {time.time() - t0:.1f} s")
ready = None
while time.time() - t0 < 120:
    try:
        tail = open(LOG, encoding="utf-8", errors="replace").read()[before:]
    except OSError:
        tail = ""
    if "microphone opened" in tail and "speaker ready" in tail:
        ready = time.time() - t0
        break
    time.sleep(0.5)
print(f"ears and voice ready after {ready and round(ready, 1)} s")
time.sleep(60)
proc.cpu_percent()
time.sleep(15)
kids = proc.children(recursive=True)
ram = proc.memory_info().rss + sum(k.memory_info().rss for k in kids if k.is_running())
print(f"after 75 s idle: Jarvis process {proc.memory_info().rss / 2**30:.2f} GB, with its window helper {ram / 2**30:.2f} GB, CPU {proc.cpu_percent():.1f}% of one core, threads {proc.num_threads()}")
print("graphics, temperature, power, load:", gpu())
ours = {proc.pid} | {k.pid for k in kids}
u = ctypes.windll.user32
t1 = time.time()
u.PostMessageW(ctypes.c_void_p(window()), 0x10, 0, 0)          # WM_CLOSE: the X button
while proc.is_running() and time.time() - t1 < 20:
    time.sleep(0.1)
print(f"closed after {time.time() - t1:.1f} s")
time.sleep(2)
left = [pid for pid in ours if psutil.pid_exists(pid)]
print("leftover processes of ours:", left or "none")
time.sleep(3)
print("graphics after closing:", gpu())
print("LAUNCH OK" if ready and not left and not proc.is_running() else "LAUNCH PROBLEM")
