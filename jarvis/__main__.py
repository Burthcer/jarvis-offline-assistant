"""Text-only Jarvis: type a sentence, read the reply. Type 'quit' to leave."""
import os
import sys
import threading
import time

from .core import announce_due, handle
from .store import Store

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows console would crash on emoji / Hindi text
sys.stdin.reconfigure(encoding="utf-8", errors="replace")
os.makedirs("data", exist_ok=True)
store = Store()


def watcher():
    while True:
        for line in announce_due(store):
            print(f"\n[REMINDER] {line}\n> ", end="", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    threading.Thread(target=watcher, daemon=True).start()
    print("Jarvis (text mode). Try: remind me to call mom in 1 minute. Type quit to exit.")
    while True:
        try:
            text = input("> ")
        except EOFError:
            break
        if text.strip().lower() in ("quit", "exit"):
            break
        if text.strip():
            print(handle(text, store))
