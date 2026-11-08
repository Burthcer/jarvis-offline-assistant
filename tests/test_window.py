"""The REAL window and island, on screen: opens them with test data (no voice), presses things through the page, takes screenshots.
Run: py -3.12 tests\\test_window.py <folder for screenshots>"""
import ctypes
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import webview  # noqa: F401  (must load before the folder changes below)
from PIL import Image, ImageGrab
from jarvis import actions, settings, ui
from jarvis.store import Store

out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else tempfile.mkdtemp()
os.makedirs(out, exist_ok=True)
settings.PATH = os.path.join(tempfile.mkdtemp(), "settings.json")
settings.set_autostart = lambda on: None
os.chdir(tempfile.mkdtemp())
ctypes.windll.shcore.SetProcessDpiAwareness(2)
app = ui.App(Store(":memory:"), tray=False, load_settings=False, gui=True)
fails = []


class Rec:  # nothing real gets opened by this test
    def open_url(self, b, u): return b
    def launch(self, t): pass
    def key(self, n, c=1): pass


actions.backend = Rec()


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


def grab_window(name):
    """Only ever captures our own window: if something else is in front, no picture (it might be anything private)."""
    app.open_main()
    time.sleep(0.5)
    u = ctypes.windll.user32
    u.GetForegroundWindow.restype = ctypes.c_void_p
    if u.GetForegroundWindow() != app._hwnd():
        print("note: window not in front, no picture for", name)
        return
    w = app.window.native
    ImageGrab.grab(bbox=(w.Left, w.Top, w.Right, w.Bottom), all_screens=True).save(os.path.join(out, name + ".png"))


def grab_island(name):
    """The island's own picture on a plain background: never a capture of the screen."""
    i = app.island
    w, h = i._target()
    time.sleep(0.3)
    a = i._draw(w, h, time.perf_counter())
    back = Image.new("RGBA", (a.shape[1], a.shape[0]), (60, 70, 82, 255))
    back.alpha_composite(Image.fromarray(a, "RGBA"))
    back.save(os.path.join(out, name + ".png"))


def js(code):
    return app.window.evaluate_js(code)


def run():
    try:
        for _ in range(100):
            if app.page_ready:
                break
            time.sleep(0.1)
        check(app.page_ready, "page opened and connected")
        time.sleep(1)
        app.q.put(("typed", "remind me to submit my lab record tomorrow at 5pm"))
        app.q.put(("typed", "remind me to check linkedin tomorrow at 5pm"))
        app.q.put(("typed", "set a timer for 25 minutes"))
        time.sleep(1)
        app.hide_at = 0
        time.sleep(0.6)
        check("Timer set" in js("document.getElementById('log').innerText"), "conversation shows")
        check(js("document.querySelectorAll('.tcard').length") == 1, "timer card exists")
        check(":" in js("document.querySelector('.miniRing div').textContent"), "side timer ticking")
        check(js("getComputedStyle(document.body).fontFamily").startswith("Geist"), "font in use")
        check(js("document.fonts.check('15px Geist')"), "font file loaded")
        check(js("document.documentElement.scrollWidth <= window.innerWidth"), "nothing overflows sideways")
        grab_window("1_home")
        grab_island("i1_timer")
        app.state("listening"); time.sleep(0.8)
        check(js("document.getElementById('orb').className").endswith("listening"), "orb follows state")
        grab_island("i2_listening")
        js("jarvis.level(0.7)"); grab_window("2_listening")
        app.state("thinking"); time.sleep(0.6); grab_island("i3_thinking")
        app.q.put(("typed", "open notepad")); time.sleep(0.8); grab_island("i4_speaking")
        app.hide_at = 0; time.sleep(0.5)
        js("document.getElementById('remText').value='water plants tomorrow at 9am';document.getElementById('addRem').requestSubmit()"); time.sleep(1)
        check(js("document.querySelectorAll('#sideRem .rem').length") == 3, "add a reminder in the window")
        js("document.querySelector('#sideRem .rem:last-child .tiny-btn:last-child').click()"); time.sleep(0.6)
        check(js("document.querySelectorAll('#sideRem .rem').length") == 2, "cancel a reminder in the window")
        app.hide_at = 0; time.sleep(0.5)
        js("document.querySelector('[data-page=timers]').click()"); time.sleep(0.5)
        js("document.getElementById('hrs').value='';document.getElementById('mins').value='2';document.getElementById('secs').value='30';document.getElementById('custom').requestSubmit()"); time.sleep(0.8)
        check(any(t["total"] == 150 for t in app.snapshot()["timers"]), "set any length on the Timers page")
        js("document.querySelector('.chip[data-secs=\"300\"]').click()"); time.sleep(0.8)
        check(js("document.querySelectorAll('.tcard').length") == 3, "preset button adds a timer")
        grab_window("3_timers")
        js("document.querySelector('.tcard .round.main').click()"); time.sleep(0.8)
        check("Paused" in js("document.querySelector('.tcard').innerText"), "pause button works")
        js("document.querySelector('[data-page=settings]').click()"); time.sleep(0.8)
        check(js("document.querySelectorAll('#browsers .seg').length") >= 9, "settings loaded")
        grab_window("4_settings")
        js("document.querySelector('#browsers .seg button:not(.on)').click()"); time.sleep(1)
        check("Saved" in js("document.getElementById('saved').textContent"), "a settings change saves itself")
        js("document.querySelector('#browsers .seg button:not(.on)').click()"); time.sleep(0.7)
        js("document.querySelector('[data-page=home]').click()")
        app.store.add("5-minute", datetime.now() - timedelta(seconds=1), kind="timer")
        app.window.hide(); app.visible = False; time.sleep(0.8)
        time.sleep(2.5)  # the 2 s check notices it
        check(ctypes.windll.user32.IsWindowVisible(ctypes.c_void_p(app._hwnd())), "window opens by itself when a timer ends")
        time.sleep(0.8)
        check(not js("document.getElementById('alert').hidden"), "alert showing")
        grab_window("5_alert"); grab_island("i5_alert")
        js("document.getElementById('alertStop').click()"); time.sleep(0.6)
        check(js("document.getElementById('alert').hidden"), "Stop closes the alert")
        i = app.island
        i._click(i.W // 2, int(20 * i.s)); time.sleep(0.8)
        check(i.expanded and i.hits, "clicking the pill opens it")
        grab_island("i6_open")
        n = sum(t["on"] for t in app.snapshot()["timers"])
        pause = next(h for h in i.hits if h[4] != "main" and h[4][1][0] == "toggle")
        i._click((pause[0] + pause[2]) / 2, (pause[1] + pause[3]) / 2); time.sleep(0.6)
        check(i.expanded and sum(t["on"] for t in app.snapshot()["timers"]) != n, "a timer's button in the open pill works")
        i._click(5, 5); time.sleep(0.6)
        check(not i.expanded, "clicking away closes it")
        for k in range(7):
            app.store.add(f"Extra thing {'abcdefg'[k]}", datetime.now() + timedelta(days=2 + k))
        time.sleep(1.2)
        i._click(i.W // 2, int(20 * i.s)); time.sleep(0.5)
        i._wheel(-120); time.sleep(0.4)
        check(i.expanded and i.scroll == 1, "the wheel scrolls the open pill")
        grab_island("i7_scrolled")
        i._click(5, 5); time.sleep(0.4)
        for m in (11, 12, 13, 14, 15, 16):
            app.q.put(("add_timer", m * 60))
        time.sleep(1.2)
        js("document.querySelector('[data-page=timers]').click()"); time.sleep(0.4)
        h = js("var p=document.getElementById('timers');p.scrollTop=9999;[p.scrollHeight,p.clientHeight,p.scrollTop]")
        check(h[0] > h[1] and h[2] > 0, f"the Timers page scrolls {h}")
        js("document.querySelector('[data-page=home]').click()"); time.sleep(0.4)
        h = js("var p=document.getElementById('sideTimers');p.scrollTop=9999;[p.scrollHeight,p.clientHeight,p.scrollTop,p.querySelectorAll('.mini').length]")
        check(h[0] > h[1] and h[2] > 0 and h[3] >= 6, f"every timer is in the Home list, and it scrolls {h}")
        quits = []
        app.quit = lambda: quits.append(1)
        app._on_closing()
        check(quits == [1], "X quits all of Jarvis")
        for t in app.store.all_timers():
            app.store.delete(t["id"])
        app.hide_at = 0
        app.state("idle"); time.sleep(2)
        f1 = app.island.frames; time.sleep(3)
        check(app.island.frames == f1, f"idle island draws nothing ({app.island.frames - f1} frames in 3 s)")
        grab_island("i0_idle")
    except Exception as e:
        check(False, f"crashed: {e!r}")
    print("WINDOW:", "PASS" if not fails else f"FAIL {fails}", "| screenshots in", out, flush=True)
    os._exit(1 if fails else 0)


threading.Thread(target=run, daemon=True).start()
ui.launch(app)
