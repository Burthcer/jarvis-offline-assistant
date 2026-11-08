"""The only way abilities touch Windows (ctx.os). Real wraps V1's actions.Real backend + pycaw + the Windows media session; Fake records and pretends, so tests open nothing.
Kinds: app, site, bookmark, folder, file."""
import asyncio
import json
import os
import re
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_TYPES = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf", ".odt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
              ".mp3", ".wav", ".m4a", ".mp4", ".mkv", ".mov", ".avi", ".zip"}          # opening only: nothing that runs code (.exe .bat .ps1 .py .js .msi ...), nothing is ever deleted
# More sites than V1 knew, with a search page where there is one: (browser, home page, search url or None)
EXTRA_SITES = {
    "patreon": ("edge", "https://www.patreon.com", "https://www.patreon.com/search?q="),
    "reddit": ("edge", "https://www.reddit.com", "https://www.reddit.com/search/?q="),
    "github": ("edge", "https://github.com", "https://github.com/search?q="),
    "wikipedia": ("edge", "https://en.wikipedia.org", "https://en.wikipedia.org/w/index.php?search="),
    "instagram": ("edge", "https://www.instagram.com", None),
    "facebook": ("edge", "https://www.facebook.com", "https://www.facebook.com/search/top?q="),
    "twitter": ("edge", "https://x.com", "https://x.com/search?q="),
    "pinterest": ("edge", "https://www.pinterest.com", "https://www.pinterest.com/search/pins/?q="),
    "flipkart": ("edge", "https://www.flipkart.com", "https://www.flipkart.com/search?q="),
    "google maps": ("edge", "https://www.google.com/maps", "https://www.google.com/maps/search/"),
    "google drive": ("edge", "https://drive.google.com", None),
    "spotify": ("edge", "https://open.spotify.com", "https://open.spotify.com/search/"),
    "stack overflow": ("edge", "https://stackoverflow.com", "https://stackoverflow.com/search?q="),
    "chatgpt site": ("edge", "https://chatgpt.com", None),
}
CATALOG_CACHE = os.path.join(ROOT, "data", "gold", "catalog.json")
APP_EXE = {"edge": "msedge", "chrome": "chrome"}  # browsers' audio and process names
STEP = 10  # "louder" = +10 percent


class Real:
    def __init__(self):
        from jarvis import actions
        self.a = actions
        self.entries = {}
        self.sites = {**EXTRA_SITES, **actions.SITES}

    # ----- what exists -----
    def catalog(self):
        a, out = self.a, {}
        for n in a.APPS:
            out[n] = "app"
        for n, p in {**a.start_apps(), **a.desktop_apps()}.items():
            out.setdefault(n, "app")
            self.entries[n] = p
        for n in self.sites:
            out[n] = "site"
        for n in a.FOLDERS:
            out[n] = "folder"
        for d in (os.path.expandvars(r"%USERPROFILE%\Desktop"), os.path.expandvars(r"%USERPROFILE%\Documents"), os.path.expandvars(r"%USERPROFILE%\Downloads")):
            try:
                for f in os.scandir(d):                                  # top level only
                    stem, ext = os.path.splitext(f.name)
                    name = stem.lower().strip()
                    if f.is_file() and ext.lower() in FILE_TYPES and 3 <= len(name) <= 40 and name not in out:
                        out[name] = "file"
                        self.entries[name] = f.path
            except OSError:
                pass
        for b in ("Microsoft/Edge", "Google/Chrome"):
            p = os.path.expandvars(rf"%LOCALAPPDATA%\{b}\User Data\Default\Bookmarks")
            if os.path.exists(p):
                def walk(n):
                    name = re.sub(r"^\(\d+\)\s*", "", n.get("name", "")).lower()  # '(2) YouTube' is a notification count
                    if n.get("type") == "url" and 2 < len(name) < 26 and not re.search(r"[|?]| - ", name) and name not in out:
                        out[name] = "bookmark"
                        self.entries[name] = n["url"]
                    for c in n.get("children", []):
                        walk(c)
                for r in json.load(open(p, encoding="utf-8"))["roots"].values():
                    if isinstance(r, dict):
                        walk(r)
        return {n: k for n, k in out.items() if not self.a.NEVER_OPEN.search(n)}   # never Narrator, a terminal, regedit...

    def running_names(self, catalog):
        """Catalog app names that are running now (by program name)."""
        a = self.a
        progs = {a._squash(x[:-4]) for x in self.running_programs()}
        names = {n for n, k in catalog.items() if k == "app" and len(a._squash(n)) >= 4 and any(p.startswith(a._squash(n)) for p in progs)}
        for n, exe in a.CLOSE.items():
            if a._squash(exe[:-4]) in progs:
                names.add(n)
        return names

    def running_programs(self):
        return self.a.backend.running()

    def front(self):
        import ctypes
        import psutil
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        h = u.GetForegroundWindow()
        if not h:
            return "", ""
        pid = ctypes.c_ulong()
        u.GetWindowThreadProcessId(ctypes.c_void_p(h), ctypes.byref(pid))
        try:
            return psutil.Process(pid.value).name().lower().removesuffix(".exe"), self.a.backend._title(ctypes.c_void_p(h))
        except Exception:
            return "", ""

    def clipboard_write(self, text):
        from .clipboard import write
        return write(text)

    # ----- open, close, focus -----
    def window_state(self, action, target):
        from .window_control import change
        b = self.a.backend
        target = target.lower().strip()
        if target in ('this','it','this app','this window','app','window','current window'):
            import ctypes
            u = ctypes.windll.user32
            u.GetForegroundWindow.restype = ctypes.c_void_p
            hwnd = u.GetForegroundWindow()
            windows = [hwnd] if hwnd else []
        elif target in ('all tabs','all browser windows','the browser','browser'):
            windows = b._browsers()
        elif target in ('all','all apps','all windows','everything'):
            import psutil
            pids = {p.info['pid'] for p in psutil.process_iter(['pid','name'])
                    if p.info['pid'] != 0 and (p.info['name'] or '').lower() not in self.a.NEVER_CLOSE}
            windows = b._process_windows(pids)
        else:
            import psutil
            names = re.split(r'\s+and\s+|\s*,\s*', target)
            exes = set()
            for name in names:
                name = re.sub(r'\s+(?:app|window|browser)$','',name)
                found = self._app_exes(name)
                if not found:
                    return 0, 0  # resolve every target before changing any
                exes.update(x.lower() for x in found)
            pids = {p.info['pid'] for p in psutil.process_iter(['pid','name']) if (p.info['name'] or '').lower() in exes}
            windows = b._process_windows(pids)
        windows = list(dict.fromkeys(windows))
        return sum(change(hwnd, action) for hwnd in windows), len(windows)

    def open(self, name, kind, count=1, browser=None):
        a = self.a
        try:
            if kind == "site":
                b = browser or self.sites[name][0]
                if count==1:
                    try:
                        from .browser_tabs import WindowsTabs,operate
                        adapter=WindowsTabs(a.backend,browser=b)
                        pattern=a.TAB.get(name,r'\b'+re.escape(name)+r'\b')
                        tabs=adapter.list_tabs()
                        hits=[t for t in tabs if re.search(pattern,t['title'],re.I)]
                        current=[t for t in hits if t.get('selected')]
                        if current or len(hits)==1:
                            if operate(adapter,'focus','this' if current else hits[0]['title'],pattern)['ok']:return True
                    except Exception:pass
                return all(a.backend.open_url(b, self.sites[name][1]) is not False for _ in range(count))
            if kind == "bookmark":
                a.backend.open_url(browser or "edge", self.entries[name])
            elif kind == "folder":
                a.backend.launch(a.FOLDERS[name])
            elif kind == "file":
                os.startfile(self.entries[name])                          # opens it in its own program
            else:
                a.backend.launch(a.APPS.get(name) or self.entries[name])
                threading.Thread(target=self.focus, args=(name, kind), daemon=True).start()  # Windows hides new windows behind others: bring it forward
            return True
        except Exception:
            return False

    def focus(self, name, kind, wait=1.5):
        """True if the app's window really came to the front."""
        a = self.a
        pat = r"\b" + r"\W*".join(map(re.escape, {"calc": "calculator"}.get(name, name).split())) + r"\b"
        exes = {x.lower() for x in self._app_exes(name)} if kind == 'app' else set()
        end = time.monotonic() + wait
        while True:
            wins = []
            if exes:
                import psutil
                pids = {p.info['pid'] for p in psutil.process_iter(['pid', 'name']) if (p.info['name'] or '').lower() in exes}
                wins = a.backend._process_windows(pids) if pids else []
            # Editors often put only the project/document in their title.
            # Match the owning program first, then titles for websites/folders.
            if not wins:
                wins = a.backend._windows(lambda h: re.search(pat, a.backend._title(h), re.I))
            if wins and a.backend._front(wins[0]):
                return True
            if time.monotonic() >= end:
                break
            time.sleep(.05)
        return False

    def _app_exes(self, name):
        a, b = self.a, self.a.backend
        k = a.BROWSERS.get(name) or {'calc': 'calculator'}.get(name, name)
        if k in a.CLOSE:
            return [a.CLOSE[k]]
        sq = a._squash(name)
        exes = [x for x in b.running() if len(sq) >= 4 and a._squash(x[:-4]).startswith(sq)]
        path = self.entries.get(name)
        if not exes and path and '!' in path and path.startswith('shell:AppsFolder'):
            # Packaged desktop apps can have a display name unrelated to exe.
            identity = path.rsplit('!', 1)[-1]
            exes = [x for x in b.running() if a._squash(x.removesuffix('.exe')) == a._squash(identity)]
        if not exes and path:
            target = b.target(path)
            exes = [target] if target else []
        return [x for x in exes if x.lower() not in a.NEVER_CLOSE]

    def close(self, name, kind):
        """-> (ok, was_open). Checks the program really went away."""
        a, b = self.a, self.a.backend
        if kind == "site":
            n = self.close_tab(a.TAB.get(name, r"\b%s\b" % re.escape(name)), "front")
            return bool(n), bool(n)
        if kind == "folder":
            pat = None if name in a.EXPLORER else {"download": "downloads", "photos": "pictures", "my computer": "this pc"}.get(name, name)
            return True, bool(b.close_folders(pat))
        if name in a.EXPLORER:
            return True, bool(b.close_folders(None))
        exes = self._app_exes(name)
        if not exes:
            return False, False
        if hasattr(b, 'close_processes'):
            return b.close_processes(exes)
        was = [b.close(x) for x in exes]
        end = time.time() + 4
        while time.time() < end and any(x.lower() in (r.lower() for r in b.running()) for x in exes):
            time.sleep(0.2)
        gone = not any(x.lower() in (r.lower() for r in b.running()) for x in exes)
        return gone, any(was)

    # ----- other apps' windows, through UI Automation (rails in uia.py) -----
    def ui_read(self):
        from . import uia
        return uia.read_window()

    def ui_click(self, label):
        from . import uia
        return uia.click(label)

    def ui_type(self, text):
        from . import uia
        uia.type_text(text)

    def ui_press(self, key):
        from . import uia
        uia.press(key)

    def ui_focus_field(self):
        from . import uia
        return uia.focus_field()

    # ----- browser: pages, tabs, the video in front -----
    def url(self, browser, url):
        try:
            self.a.backend.open_url(browser, url)
            return True
        except Exception:
            return False

    def video_key(self, vk, shift=False):
        return bool(self.a.backend.video_key(vk, shift))

    def first_video(self, wait=0):
        return bool(self.a.backend.first_video(wait))

    def screenshot(self):
        return self.a.backend.screenshot()

    def close_tab(self, pattern=None, which="all"):
        """Compatibility count; verified tab operations use unique native identities."""
        result=self.tab_action(which,pattern)
        return len(result['done']) if result['ok'] else 0

    def tab_action(self,which,pattern=None):
        from .browser_tabs import WindowsTabs,operate
        try:return operate(WindowsTabs(self.a.backend),'close',which,pattern)
        except Exception as error:return {'ok':False,'done':[],'message':str(error)}

    def browser_tabs(self, action, selector):
        from .browser_tabs import WindowsTabs, operate
        try:
            return operate(WindowsTabs(self.a.backend),action,selector)
        except Exception as error:
            return {'ok':False,'done':[],'message':str(error)}

    def focus_tab(self, which):
        return self.browser_tabs('focus',which)['ok']

    # ----- sound -----
    def settings_page(self,uri):
        from .windows_settings import PAGES
        if uri not in {p[1] for p in PAGES.values()}:return False
        try:return self.a.backend.launch(uri) is not False
        except Exception:return False

    def audio_app(self, name, kind):
        """The program whose audio a name is: a site plays in its browser."""
        return self.sites[name][0] if kind == "site" else name

    def _ep(self):
        from pycaw.pycaw import AudioUtilities
        return AudioUtilities.GetSpeakers().EndpointVolume

    def volume(self):
        return round(self._ep().GetMasterVolumeLevelScalar() * 100)

    def set_volume(self, level):
        ep = self._ep()
        ep.SetMasterVolumeLevelScalar(max(0, min(100, level)) / 100, None)
        if level > 0 and ep.GetMute():
            ep.SetMute(0, None)
        return round(ep.GetMasterVolumeLevelScalar() * 100)

    def muted(self):
        return bool(self._ep().GetMute())

    def set_muted(self, on):
        ep = self._ep()
        ep.SetMute(1 if on else 0, None)
        return bool(ep.GetMute())

    def _sessions(self, app):
        from pycaw.pycaw import AudioUtilities
        prog = APP_EXE.get(app, app).replace(" ", "")
        return [s for s in AudioUtilities.GetAllSessions() if s.Process and s.Process.name().lower().replace(" ", "").startswith(prog)]

    def app_volume(self, app):
        ss = self._sessions(app)
        return round(ss[0].SimpleAudioVolume.GetMasterVolume() * 100) if ss else None

    def set_app_volume(self, app, level):
        ss = self._sessions(app)
        for s in ss:
            s.SimpleAudioVolume.SetMasterVolume(max(0, min(100, level)) / 100, None)
        return round(ss[0].SimpleAudioVolume.GetMasterVolume() * 100) if ss else None

    # ----- media: the Windows media session, no focus change -----
    def _session(self, fn):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M

        async def go():
            s = (await M.request_async()).get_current_session()
            return await fn(s) if s else None
        return asyncio.run(go())

    def media_state(self):
        async def f(s):
            p = await s.try_get_media_properties_async()
            return {"app": s.source_app_user_model_id, "title": p.title, "playing": s.get_playback_info().playback_status == 4}
        return self._session(f)

    def media(self, action):
        """-> (ok, state after). A session that says false, or none, is ok=False."""
        async def f(s):
            call = {"pause": s.try_pause_async, "play": s.try_play_async, "next": s.try_skip_next_async, "previous": s.try_skip_previous_async}[action]
            ok = bool(await call())
            # Skip is acknowledged by the player; no fixed delay or title
            # lookup is needed. Play/pause is checked on this SAME session.
            info = s.get_playback_info()
            if ok and action in ('play', 'pause'):
                end = time.monotonic() + .3
                while (info.playback_status == 4) != (action == 'play') and time.monotonic() < end:
                    await asyncio.sleep(.02)
                    info = s.get_playback_info()
            return ok, {'app': s.source_app_user_model_id, 'title': '', 'playing': info.playback_status == 4}
        return self._session(f) or (False, None)


class Fake:
    """Pretends to be the owner's PC. Every action is appended to .log as (what, ...). Nothing real happens."""

    def __init__(self, running=("edge", "chrome", "whatsapp", "discord"), playing=("youtube", True)):
        self.log, self._running, self.vol, self.mute, self.app_vol = [], set(running), 50, False, {"edge": 100, "chrome": 100}
        self.playing = {"app": "msedge", "title": playing[0], "playing": playing[1]} if playing else None
        self.fail = set()  # names of things that "fail", for tests

    sites = {**EXTRA_SITES}

    def catalog(self):
        if not os.path.exists(CATALOG_CACHE):
            os.makedirs(os.path.dirname(CATALOG_CACHE), exist_ok=True)
            json.dump(Real().catalog(), open(CATALOG_CACHE, "w", encoding="utf-8"))
        return json.load(open(CATALOG_CACHE, encoding="utf-8"))

    def running_names(self, catalog):
        return set(self._running)

    def front(self):
        return "msedge", "YouTube - Microsoft Edge"

    def clipboard_write(self, text):
        self.log.append(('clipboard', text))
        return 'clipboard' not in self.fail

    def open(self, name, kind, count=1, browser=None):
        self.log.append(("open", name, kind, count, browser))
        if name not in self.fail:
            self._running.add(name)
        return name not in self.fail

    def focus(self, name, kind, wait=0):
        self.log.append(("focus", name, kind))
        return name in self._running

    def close(self, name, kind):
        self.log.append(("close", name, kind))
        was = name in self._running
        if kind != "site":
            self._running.discard(name)
        return name not in self.fail, was

    def focus_tab(self, which):
        self.log.append(('focus_tab', which))
        return 'focus_tab' not in self.fail

    def browser_tabs(self, action, selector):
        self.log.append(('browser_tabs',action,selector))
        return {'ok':'browser_tabs' not in self.fail,'done':[] if 'browser_tabs' in self.fail else [selector], 'message':'Test player refused.' if 'browser_tabs' in self.fail else ''}

    def tab_action(self,which,pattern=None):
        count=self.close_tab(pattern,which)
        return {'ok':bool(count),'done':['tab']*count,'message':'No matching tab.'}

    def window_state(self, action, target):
        self.log.append(('window_state', action, target))
        return (0,1) if target in self.fail else (1,1)

    ui_text = "Price: 499 rupees. Delivery in 3 days. Save for later. Send message."

    def _ui(self, what, *a):
        from . import uia
        self.log.append((what, *a))
        if "ui" in self.fail:
            raise uia.Refused("That window looks like a bank, payment or login page. I don't read or operate those, sir.")

    ui_script = None      # a list of texts: each ui_read gives the next one (the last repeats), like an app that is still writing its answer

    def ui_read(self):
        self._ui("ui_read")
        if self.ui_script:
            return self.ui_script.pop(0) if len(self.ui_script) > 1 else self.ui_script[0]
        return self.ui_text

    def ui_click(self, label):
        self._ui("ui_click", label)
        return label.title()

    def ui_type(self, text):
        self._ui("ui_type", text)

    def ui_press(self, key):
        self._ui("ui_press", key)

    def ui_focus_field(self):
        self._ui("ui_focus_field")
        return True

    def url(self, browser, url):
        self.log.append(("url", browser, url))
        return "url" not in self.fail

    def video_key(self, vk, shift=False):
        self.log.append(("video_key", vk))
        return "video" not in self.fail

    def first_video(self, wait=0):
        self.log.append(("first_video",))
        return "video" not in self.fail

    def screenshot(self):
        self.log.append(("screenshot",))
        return "shot.png"

    def close_tab(self, pattern=None, which="all"):
        self.log.append(("close_tab", pattern, which))
        return 0 if "tab" in self.fail else (3 if which == "all" else 1)

    def volume(self):
        return self.vol

    def settings_page(self,uri):
        self.log.append(('settings_page',uri))
        return 'settings_page' not in self.fail

    def set_volume(self, level):
        self.log.append(("volume", level))
        self.vol, self.mute = max(0, min(100, level)), False if level > 0 else self.mute
        return self.vol

    def muted(self):
        return self.mute

    def set_muted(self, on):
        self.log.append(("mute", on))
        self.mute = on
        return self.mute

    def audio_app(self, name, kind):
        return "edge" if kind == "site" else name

    def app_volume(self, app):
        return self.app_vol.get(app)

    def set_app_volume(self, app, level):
        self.log.append(("app_volume", app, level))
        if app in self.app_vol:
            self.app_vol[app] = max(0, min(100, level))
        return self.app_vol.get(app)

    def media_state(self):
        return dict(self.playing) if self.playing else None

    def media(self, action):
        self.log.append(("media", action))
        if not self.playing:
            return False, None
        if action in ("pause", "play"):
            self.playing["playing"] = action == "play"
        return True, self.media_state()
