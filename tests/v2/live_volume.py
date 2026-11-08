"""Real volume checks on this PC, every kind, then everything is put back exactly as it was. Touches no app and no screen.
Run: py -3.12 tests/v2/live_volume.py"""
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from jarvis.store import Store  # noqa: E402

from jarvis2 import awareness  # noqa: E402
from jarvis2.abilities.sound import volume  # noqa: E402
from jarvis2.app import App, Ctx  # noqa: E402
from jarvis2.osapi import Real  # noqa: E402

real = Real()
app = App(real, Store(":memory:"), None, natural=False)
v0, m0, e0 = real.volume(), real.muted(), real.app_volume("edge")
bad = []


def phrase(text):
    r = app.handle(text)
    return r


def expect(label, ok, info=""):
    print(("ok   " if ok else "FAIL ") + label, info)
    if not ok:
        bad.append(label)


try:
    real.set_muted(False)
    r = phrase("volume 30"); expect("volume 30", real.volume() == 30 and r.ok, (real.volume(), r.text))
    r = phrase("volume full"); expect("volume full", real.volume() == 100, real.volume())
    r = phrase("volume max"); expect("volume max", real.volume() == 100)
    r = phrase("set the volume to 70"); expect("set the volume to 70", real.volume() == 70, real.volume())
    r = phrase("volume zero"); expect("volume zero", real.volume() == 0, real.volume())
    r = phrase("volume 50"); expect("volume 50 after zero (not stuck)", real.volume() == 50 and not real.muted(), (real.volume(), real.muted()))
    r = phrase("volume up"); expect("volume up +10", real.volume() == 60, real.volume())
    r = phrase("volume down"); expect("volume down -10", real.volume() == 50, real.volume())
    r = phrase("mute"); expect("mute", real.muted() and r.ok, r.text)
    r = phrase("mute"); expect("mute again says already", r.text == "Already muted, sir." and real.muted(), r.text)
    r = phrase("unmute"); expect("unmute", not real.muted() and real.volume() == 50, (real.muted(), real.volume()))
    r = phrase("volume down"); r = phrase("undo that"); expect("undo restores the level", real.volume() == 50, real.volume())
    # one app: Edge's own audio, not the system volume
    if e0 is not None:
        snap = awareness.build(real, app.store, app.catalog, datetime.now(), [], {})
        ctx = Ctx(app, snap, datetime.now(), "set the volume of edge to 40")
        r = volume({"action": "set", "level": 40, "app": "edge"}, ctx)
        expect("one app: Edge to 40, system untouched", real.app_volume("edge") == 40 and real.volume() == 50 and r.ok, (real.app_volume("edge"), real.volume(), r.plain))
        r = volume({"action": "down", "app": "edge"}, ctx)
        expect("one app: quieter", real.app_volume("edge") == 30, real.app_volume("edge"))
    else:
        print("skip  Edge has no audio session right now")
    ctx = Ctx(app, awareness.build(real, app.store, app.catalog, datetime.now(), [], {}), datetime.now(), "turn it down")
    r = volume({"action": "down", "app": "chrome"}, ctx)
    expect("an app with no sound says so", not r.ok and "isn't playing" in r.plain, r.plain)
finally:
    real.set_volume(v0)
    real.set_muted(m0)
    if e0 is not None:
        real.set_app_volume("edge", e0)
    time.sleep(0.2)
    print(f"restored: system {real.volume()} (was {v0}), muted {real.muted()} (was {m0}), edge {real.app_volume('edge')} (was {e0})")
print("ALL OK" if not bad else f"FAILED: {bad}")
