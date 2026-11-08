"""The app: runs the commands and shows what is going on. Two faces: the island at the top of the screen (island.py) and the main window,
a web page in a WebView2 window (web/app.html). Everything is decided here and sent to them; nothing leaves the laptop.
Voice calls the same submit() / state() / say() as typing."""
import ctypes
import json
import os
import queue
import re
import threading
import time
import traceback
from datetime import datetime, timedelta

from . import actions, settings
from .brain import PROMISE, UNSURE
from .core import NO, YES, announce_due, handle, is_unknown
from .store import Store
from .timeparse import fmt

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
ICON = os.path.join(os.path.dirname(WEB), "..", "jarvis.ico")


def _log(e):
    os.makedirs("logs", exist_ok=True)
    with open(os.path.join("logs", "jarvis.log"), "a", encoding="utf-8") as f:
        f.write(traceback.format_exc() + "\n")


def timer_total(label, left=0):
    return max(actions.label_secs(label), left, 1)


class Api:
    """What the page may ask for. Everything goes through the same queue as voice, one thing at a time."""

    def __init__(self, app):
        self._app = app

    def boot(self):
        self._app.page_ready = True
        return {"history": self._app.history, "snap": self._app.snapshot()}

    def submit(self, text):
        self._app.q.put(("typed", str(text)[:4000]))

    def toggle_mic(self):
        self._app.q.put("mic")

    def timer(self, what, id):
        self._app.q.put(("timer", (what, int(id))))

    def add_timer(self, secs):
        self._app.q.put(("add_timer", int(secs)))

    def alert(self, what):
        self._app.q.put(("alert", what))

    def reminder(self, what, id):
        self._app.q.put(("reminder", (what, int(id))))

    def add_reminder(self, text):
        self._app.q.put(("typed", "remind me to " + str(text)[:300]))

    def hear_voice(self):
        self._app.q.put("voice_test")

    def settings(self):
        from .voice import VOICES
        return {"cfg": self._app.cfg, "voices": VOICES, "sites": [{"key": k, "name": actions._name(k)} for k in actions.SITES]}

    def save_settings(self, cfg):
        return self._app.save_settings(cfg)


class App:
    def __init__(self, store=None, tray=True, load_settings=True, voice=False, brain=None, gui=False):
        self.store = store or Store()
        self.cfg = settings.load()
        if load_settings:
            settings.apply(self.cfg)
        self.q = queue.Queue()  # tray, page and voice only drop messages here; the app's one thread does the work
        self._chatted = False  # the AI already wrote this reply itself
        self._spoken = False  # was the command being handled spoken (so a question back can be answered by voice)
        self.history = []  # [time, who, text, tag]: everything said, shown in the main window and copied by "Copy log"
        self.recent = []
        self.state_name, self.text, self.hide_at, self.note = "idle", "", 0.0, "Voice is off in this mode."
        self.alerts = []
        self.booting = bool(voice)  # True until the voice is ready: both faces say so
        self.window, self.page_ready, self.visible, self.sent, self._last = None, False, False, [], None
        self.island = None
        if gui:
            from .island import Island
            self.island = Island(lambda m: self.q.put(m))
        self.voice = None
        if voice:
            from .voice import Voice
            self.voice = Voice(lambda k, p: self.q.put((k, p)), self.cfg["tts_volume"], self.cfg["tts_speed"], self.cfg["voice_on"], self.cfg["speak_replies"],
                               replies=self.cfg["wake_replies"], voice=self.cfg["tts_voice"])
            self.voice.start()
            self.note = "Voice: loading models (a few seconds)..."
        self.brain = None
        if brain if brain is not None else voice:  # the smart layer loads in the background; until it's ready, the rules alone answer
            from .brain import Brain
            self.brain = Brain()
            threading.Thread(target=self.brain.load, daemon=True).start()
            if self.voice:
                self.voice.prewarm = self.brain.warm  # the moment someone starts talking, wake the AI's GPU too
        self.icon = None
        if tray:
            self._tray()
        self._add("Jarvis", "Ready, sir. Type below, or talk to me: \"Jarvis, open YouTube\".", "jarvis")
        self._render()

    # ---- what the faces show ----
    def snapshot(self):
        now = datetime.now()
        timers = []
        for r in self.store.all_timers():
            on = r["status"] == "open"
            left = max(0, round((datetime.fromisoformat(r["due"]) - now).total_seconds())) if on else (r["left_s"] or 0)
            timers.append({"id": r["id"], "name": r["text"].replace("-", " ") + " timer", "left": left, "total": timer_total(r["text"], left), "on": on,
                           "ends": fmt(datetime.fromisoformat(r["due"]), now).split(" ", 1)[-1] if on else ""})
        return {"booting": self.booting, "state": self.state_name, "text": self.text, "note": self.note, "mic": not self.voice or self.voice.listening, "timers": timers,
                "reminders": [{"id": r["id"], "text": r["text"], "when": fmt(datetime.fromisoformat(r["due"]), now)} for r in self.store.upcoming(now, 15)],
                "alert": self.alerts[0] if self.alerts else None}

    def _push(self, js):
        if self.window and self.page_ready:
            try:
                self.window.evaluate_js(js)
            except Exception as ex:
                _log(ex)

    def _render(self):
        s = self.snapshot()
        if self.island:
            self.island.set_panel(s["timers"], s["reminders"])
            run = [t for t in s["timers"] if t["on"]]
            if s["alert"]:
                self.island.show("alert", s["alert"]["title"])
            elif self.booting:
                self.island.show("starting")
            elif s["state"] in ("listening", "thinking"):
                self.island.show(s["state"])
            elif self.text:
                self.island.show("speaking", self.text)
            elif run:
                self.island.show("timer", timer=("Timer", run[-1]["left"], run[-1]["total"]))
            else:
                self.island.show("idle", dim=not s["mic"])
        if s != self._last:
            self._last = s
            self.sent.append(s)
            del self.sent[:-5]
            self._push(f"jarvis.update({json.dumps(s)})")

    def state(self, name):
        self.state_name = name
        self._render()

    def set_note(self, text):
        self.note = text
        self._render()

    def say(self, text, kind="jarvis"):
        self._add("Jarvis", text, "err" if ("afraid" in text and '"' in text) or "wrong" in text else kind)
        if self.voice:
            self.voice.speak(text)
            if self._spoken and self.store.pending and self.voice.talk:  # the user spoke and Jarvis is asking back: listen for the answer
                self.voice.followup = True
        self._spoken = False
        self.text, self.hide_at = text, time.time() + min(20, 4 + 0.06 * len(text))
        self.state("speaking")

    def hide_text(self):
        self.text = ""
        if self.state_name == "speaking":
            self.state_name = "idle"
        self._render()

    # ---- commands ----
    def submit(self, text="", spoken=False):
        text = (text or "").strip()
        if not text:
            return
        self._spoken = spoken
        self._add("You", text, "you")
        self.state("thinking")
        try:
            tune = actions.voice_tune(text)
            reply = self._tune(*tune) if tune else self._think(text)
        except Exception as ex:
            _log(ex); reply = "Something went wrong, sir. It's in the log."
        if self.brain and self.brain.ready and self.cfg.get("natural_replies", True) and reply != actions.BYE and not self._chatted and not self.store.pending and "?" not in reply and "\n" not in reply:
            try:  # the rules did the work and know exactly what happened; the AI says it in its own words
                reply = self.brain.phrase(text, reply)
            except Exception as ex:
                _log(ex)
        self._chatted = False
        self.recent = (self.recent + [(text, reply)])[-2:]
        self.say(reply)
        if reply == actions.BYE:  # say goodbye, then close completely (no background process left)
            threading.Timer(1.3, self.q.put, ("quit",)).start()

    def _think(self, text):
        """The AI rewrites messy words into one clean command for the rules engine (or a chat reply). If it isn't ready,
        or a short answer to Jarvis's own question is expected, the rules handle the words directly."""
        pend = self.store.pending
        if not (self.brain and self.brain.ready):
            return handle(text, self.store)
        if pend and pend[0] in ("combine", "when") and not re.search(r"\b(?:remind|open|close|search|set|timer|volume|what|delete|cancel|move)\b", text, re.I):
            return handle(text, self.store)  # "up", "5 pm"
        if pend and pend[0] not in ("combine", "when"):
            if text.lower().strip(" .!?") in YES | NO:
                return handle(text, self.store)  # yes or no to its question
            self.store.pending = None  # anything else is the user moving on: understand it, don't reject it
        exact = actions.direct(text)  # "open Wisperno Pro", "close IHatePDF", "shut down": exact rules, no AI needed
        if exact:
            self.store.pending = None
            return handle(exact, self.store)
        try:  # a longer answer may be a whole new sentence ("Essentially, remind me, today, 5 PM..."): the AI puts it together
            line = self.brain.rewrite(text, self.recent[-1][1] if pend and self.recent else None, self.recent[-2:], self._situation())
            self.store.pending = None
        except Exception as ex:
            _log(ex)
            return handle(text, self.store)
        if line.lower().startswith("chat:"):
            if line[5:].strip() == UNSURE or PROMISE.search(line):  # the AI wasn't sure, or promised what a chat can't do: the rules may know these words; if not, it answers again
                raw = handle(text, self.store)
                if not is_unknown(raw):
                    return raw
                self._chatted = True
                return self.brain.converse(text, self.recent[-2:], self._situation())
            self._chatted = True
            return line[5:].strip() or "Of course, sir."
        self._add("Understood as", line, "sys")
        tune = actions.voice_tune(line)
        if tune:
            return self._tune(*tune)
        rest = list(self.brain.rest)
        reply = handle(line, self.store)
        if is_unknown(reply):  # the rewrite didn't help: give the original words a chance, then answer properly
            raw = handle(text, self.store)
            if not is_unknown(raw):
                return raw
            self._chatted = True
            return self.brain.converse(text, self.recent[-2:], self._situation())
        replies = [reply]
        for more in rest:  # "open notepad and set a timer for 5 minutes"
            self._add("Understood as", more, "sys")
            replies.append(handle(more, self.store))
        return actions.merge_replies(replies)

    def _situation(self):
        """What is on right now, so the AI can make sense of 'the short one' or 'tomorrow's reminders'."""
        now = datetime.now()
        timers = [f"{r['text'].replace('-', ' ')} ({'running' if r['status'] == 'open' else 'paused'})" for r in self.store.all_timers()]
        rem = [f"{r['text']} ({fmt(datetime.fromisoformat(r['due']), now)})" for r in self.store.upcoming(now, 8)]
        return f"Timers now: {', '.join(timers) or 'none'}. Reminders now: {', '.join(rem) or 'none'}."

    def _tune(self, what, direction):
        """'speak slower', 'increase your volume': change Jarvis's own voice, remember it, answer at the new setting."""
        if not self.voice:
            return "My voice isn't running in this mode, sir."
        key, step, lo, hi = ("tts_volume", 0.15, 0.2, 1.0) if what == "volume" else ("tts_speed", 0.15, 0.6, 1.6)
        old = self.cfg[key]
        self.cfg[key] = new = round(min(hi, max(lo, old + direction * step)), 2)
        (self.voice.set_volume if what == "volume" else self.voice.set_speed)(new)
        try:
            settings.save(self.cfg)
        except OSError as ex:
            _log(ex)
        word = {("volume", 1): "loud", ("volume", -1): "quiet", ("speed", 1): "fast", ("speed", -1): "slow"}[(what, direction)]
        return f"That's as {word} as I go, sir." if new == old else {"loud": "Louder", "quiet": "Quieter", "fast": "Faster", "slow": "Slower"}[word] + ", sir."

    def toggle_mic(self):
        if not self.voice:
            return
        on = not self.voice.listening
        self.voice.set_listening(on)
        self.cfg["voice_on"] = on
        try:
            settings.save(self.cfg)
        except OSError as ex:
            _log(ex)
        self._render()

    def save_settings(self, new):
        c = dict(self.cfg)
        c.update({"wake_replies": [x.strip() for x in new.get("wake_replies", []) if x.strip()] or settings.DEFAULTS["wake_replies"],
                  "browsers": {k: new.get("browsers", {}).get(k, v) if new.get("browsers", {}).get(k) in ("edge", "chrome") else v for k, v in c["browsers"].items()},
                  "start_with_windows": bool(new.get("start_with_windows")), "tts_volume": round(float(new.get("tts_volume", c["tts_volume"])), 2),
                  "tts_speed": round(float(new.get("tts_speed", c["tts_speed"])), 2), "voice_on": bool(new.get("voice_on")), "speak_replies": bool(new.get("speak_replies")), "natural_replies": bool(new.get("natural_replies", True)),
                  "tts_voice": new.get("tts_voice", c["tts_voice"])})
        self.cfg = c
        if self.voice:
            self.voice.set_volume(c["tts_volume"]); self.voice.set_speed(c["tts_speed"]); self.voice.talk = c["speak_replies"]
            self.voice.set_replies(c["wake_replies"])
            threading.Thread(target=self.voice.set_voice, args=(c["tts_voice"],), daemon=True).start()  # loading a voice takes a second
            if c["voice_on"] != self.voice.listening:
                self.toggle_mic()
        try:
            settings.save(c); settings.apply(c)
            return "Saved, sir."
        except OSError as ex:
            _log(ex)
            return "Couldn't save. See the log."

    def timer_action(self, what, id):
        now, r = datetime.now(), self.store.get(id)
        if not r or r["kind"] != "timer":
            return
        on = r["status"] == "open"
        left = max(0, round((datetime.fromisoformat(r["due"]) - now).total_seconds())) if on else (r["left_s"] or 0)
        if what == "toggle":
            (self.store.pause_timer if on else self.store.resume_timer)(id, now)
        elif what == "reset":
            self.store.set_timer_left(id, timer_total(r["text"]), now, True)
        elif what == "plus":
            self.store.set_timer_left(id, left + 60, now, not on)
        elif what == "delete":
            self.store.delete(id)

    def reminder_action(self, what, id):
        r = self.store.get(id)
        if not r or r["kind"] != "reminder":
            return
        if what == "delete":
            self.store.delete(id)
        elif what == "done":
            self.store.set_status(id, "done")

    def alert_action(self, what):
        if not self.alerts:
            return
        a = self.alerts.pop(0)
        if what == "snooze":
            self.store.set_due(a["id"], datetime.now() + timedelta(minutes=5))
        elif a["kind"] == "reminder":
            self.store.set_status(a["id"], "done")

    def _fire(self):
        rows = []
        said = announce_due(self.store, fired=rows)
        if not rows:
            return
        for r in rows:
            timer = r["kind"] == "timer"
            self.alerts.append({"id": r["id"], "kind": r["kind"], "title": f"Your {r['text'].replace('-', ' ')} timer is up" if timer else r["text"],
                                "sub": "Time's up, sir." if timer else "Reminder, sir.", "face": "00:00" if timer else datetime.now().strftime("%H:%M")})
        self.open_main()
        self.say("\n".join(said), "rem")

    def _voice_msg(self, kind, p):  # the voice thread only sends messages
        if kind == "ready":
            self.booting = False
            self.voice.speak("Ready, sir.")
            self._add("Jarvis", f"Voice ready ({p}). Say \"Jarvis\" (with or without \"Hey\") and your command, e.g. \"Jarvis, open YouTube\". Or just \"Jarvis\" and wait for me.", "sys")
        elif kind == "status":
            self.set_note(p)
        elif kind == "state":
            self.state(p)
        elif kind == "wake":
            how = ("confirmed by the speech check" if p.get("via", "").startswith("check") else "clear") + (", you kept talking so I stayed quiet" if "continuing" in p.get("via", "") else "") + (f", you'd already said the command; I heard \"{p.get('heard', '')}\"" if "said it all" in p.get("via", "") else "")
            self._add("Wake word", f"heard ({how}, model score {p['score']}); my 'Yes' reached the speaker in {p['yes_ms']} ms (+{p['device_ms']} ms sound device).", "sys")
        elif kind == "near":
            self._add("Wake word", f"something like it (model score {p['score']}) but the speech check heard: \"{p['heard']}\". Not \"Jarvis\", so I ignored it.", "sys")
        elif kind == "heard":
            self.submit(p, spoken=True)
        elif kind == "error":
            self.booting = False
            self._add("Voice", p, "err"); self.set_note(p)
        elif kind == "typed":
            self.submit(p)
        elif kind == "timer":
            self.timer_action(*p); self._render()
        elif kind == "add_timer":
            handle(f"set a timer for {p} seconds", self.store); self._render()
        elif kind == "alert":
            self.alert_action(p); self._render()
        elif kind == "reminder":
            self.reminder_action(*p); self._render()

    def toggle(self):
        if self.island:
            self.island.set_hidden(not self.island.hidden)

    def open_settings(self):
        self.open_main()
        self._push("document.querySelector('[data-page=settings]').click()")

    def _tick(self, n, wait=0.0):
        """One round of the app's loop. Every 100 ms: messages; every 2 s: due reminders and timers; every second: what the faces show."""
        try:
            m = self.q.get(timeout=wait) if wait else self.q.get_nowait()
            while True:
                if isinstance(m, tuple):
                    self._voice_msg(*m)
                else:
                    {"toggle": self.toggle, "settings": self.open_settings, "main": self.open_main, "mic": self.toggle_mic, "quit": self.quit,
                     "voice_test": lambda: self.voice and self.voice.speak("At your service, sir.")}[m]()
                m = self.q.get_nowait()
        except queue.Empty:
            pass
        except Exception as ex:
            _log(ex)
        if self.text and time.time() > self.hide_at:
            self.hide_text()
        if self.voice and self.visible and n % 2 == 0:
            self._push(f"jarvis.level({min(1.0, self.voice.level * 25):.2f})")
        if n % 20 == 0:
            try:
                self._fire()
            except Exception as ex:
                _log(ex)
        if n % 10 == 0:
            self._render()

    def run(self):
        n = 0
        while True:
            self._tick(n, 0.1)
            n += 1

    def quit(self):
        if self.island:  # both faces gone at once; freeing the models takes Windows a few seconds more
            ctypes.windll.user32.ShowWindow(self.island.hwnd, 0)
        if self.window:
            ctypes.windll.user32.ShowWindow(ctypes.c_void_p(self._hwnd()), 0)
        if self.voice:
            self.voice.shutdown()
        if self.icon:
            t = threading.Thread(target=self.icon.stop, daemon=True)  # takes the tray icon away; can be slow, so it gets a moment and no more
            t.start()
            t.join(0.4)
        if self.window:
            os._exit(0)  # quit means quit: no leftover background threads keep the process (and its GPU memory) alive

    # ---- tray ----
    def _tray(self):
        import pystray
        from PIL import Image
        put = lambda m: (lambda icon, item: self.q.put(m))
        self.icon = pystray.Icon("Jarvis", Image.open(ICON), "Jarvis", pystray.Menu(
            pystray.MenuItem("Open Jarvis", put("main"), default=True),
            pystray.MenuItem("Show / hide island", put("toggle")),
            pystray.MenuItem("Mute / unmute microphone", put("mic")),
            pystray.MenuItem("Settings", put("settings")),
            pystray.MenuItem("Quit", put("quit"))))
        self.icon.run_detached()

    # ---- log ----
    def _add(self, who, text, tag):
        ts = datetime.now().strftime("%H:%M:%S")
        h = [ts, who, text, tag]
        self.history.append(h)
        try:
            os.makedirs("logs", exist_ok=True)  # local only
            with open(os.path.join("logs", "conversation.log"), "a", encoding="utf-8") as f:
                f.write(f"{ts} {who}: {text}\n")
        except OSError:
            pass
        self._push(f"jarvis.add({json.dumps(h)})")

    # ---- main window ----
    def _hwnd(self):
        if not getattr(self, 'hwnd', None):  # asking a closing window for this would stall, so it is kept from the start
            self.hwnd = int(self.window.native.Handle.ToInt64())
        return self.hwnd

    def open_main(self):
        self.visible = True
        if not self.window:
            return
        self.window.show()
        self.window.restore()
        try:
            actions.Real()._front(self._hwnd())
        except Exception as ex:
            _log(ex)
        self._render()

    def _on_closing(self):
        """Closing the window closes all of Jarvis: the island, the microphone, the models. Minimise to keep it listening."""
        self.quit()

    def _on_shown(self):
        hwnd = ctypes.c_void_p(self._hwnd())
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
        for attr, value in ((20, 1), (35, 0x000D0907)):  # dark title bar, in the page's own colour
            v = ctypes.c_int(value)
            dwm(hwnd, attr, ctypes.byref(v), 4)
        u = ctypes.windll.user32
        u.LoadImageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        for which, size in ((1, 32), (0, 16)):
            u.SendMessageW(hwnd, 0x80, which, u.LoadImageW(None, os.path.abspath(ICON), 1, size, size, 0x10))
        self.visible = True


def launch(app, debug=False):
    """Open the main window and hand this thread to it, until Jarvis quits."""
    import webview
    url = "file:///" + os.path.join(WEB, "app.html").replace("\\", "/")
    w = app.window = webview.create_window("Jarvis", url, js_api=Api(app), width=1180, height=760, min_size=(720, 520), background_color="#07090D")
    w.events.closing += app._on_closing
    w.events.shown += app._on_shown
    threading.Thread(target=app.run, daemon=True).start()
    webview.start(debug=debug, private_mode=True)
    os._exit(0)


def main():
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jarvis.Assistant")  # its own taskbar button and icon
    threading.Thread(target=actions.start_apps, args=(True,), daemon=True).start()  # newly installed apps become openable
    os.makedirs("data", exist_ok=True)
    launch(App(voice=True, gui=True))
