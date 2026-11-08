"""Jarvis V2, typing version (voice comes in Phase 4): type a sentence, read the reply. Real PC, real AI. Type 'quit' to leave.
Refuses to run beside V1 (same named mutex). Run: py -3.12 -m jarvis2"""
import ctypes
import logging
import os
import sys

from jarvis.store import Store

from .ai import AI
from .app import App
from .memory import Memory
from .osapi import Real

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stdin.reconfigure(encoding="utf-8", errors="replace")
os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
logging.basicConfig(filename=os.path.join(ROOT, "logs", "jarvis2.log"), level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")

k = ctypes.windll.kernel32
one = k.CreateMutexW(None, False, "JarvisOfflineAssistant")  # same name as V1: two copies would hear and talk over each other
if k.GetLastError() == 183:
    sys.exit("Jarvis (V1 or V2) is already running. Close it first.")

app = App(Real(), Store(os.path.join(ROOT, "data", "jarvis.db")), AI(), Memory(os.path.join(ROOT, "data", "jarvis2.db"), os.path.join(ROOT, "data", "settings2.json")))
if "--voice" in sys.argv:
    from .voice_app import VoiceApp
    v = VoiceApp(app, clips_dir=os.path.join(ROOT, "data", "clips"))
    v.start()
    try:
        while not app.exit_requested:
            import time
            time.sleep(1)
        while v.speaker.busy:
            time.sleep(0.2)                              # let 'Goodbye, sir' finish
    except KeyboardInterrupt:
        v.stop()
    app.ai.unload()
    sys.exit(0)
print("Jarvis V2 (typing). The AI loads on your first sentence. 'quit' leaves.")
while True:
    try:
        line = input("> ").strip()
    except EOFError:
        break
    if line.lower() in ("quit", "exit"):
        break
    if line:
        r = app.handle(line)
        print(("" if r.ok else "[!] ") + (r.text or "(silent)"), f"   [{r.plan.source or r.plan.kind}, {r.ms['understand']}+{r.ms['act']} ms]")
        if r.error:
            print(r.error)
        if app.exit_requested:
            break
app.ai.unload()
