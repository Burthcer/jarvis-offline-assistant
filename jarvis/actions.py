"""PC actions (M2). Only what is on the allowlists below can ever happen; everything else is refused.
act(l, store, now) -> reply or None (None = not an action). Real clicks/keys go through `backend`, so tests swap in a recorder."""
import ctypes
import difflib
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta
from functools import lru_cache
from urllib.parse import quote_plus

from .timeparse import TENS, UNITS

# name: (browser, home page, search url or None). Edge is the default browser; Chrome only for the three the owner named.
SITES = {
    "youtube music": ("edge", "https://music.youtube.com", "https://music.youtube.com/search?q="),
    "youtube": ("edge", "https://www.youtube.com", "https://www.youtube.com/results?search_query="),
    "gemini": ("edge", "https://gemini.google.com", None),
    "netflix": ("edge", "https://www.netflix.com", "https://www.netflix.com/search?q="),
    "amazon": ("edge", "https://www.amazon.in", "https://www.amazon.in/s?k="),
    "claude console": ("edge", "https://console.anthropic.com", None),
    "google": ("edge", "https://www.google.com", "https://www.google.com/search?q="),
    "linkedin": ("chrome", "https://www.linkedin.com", "https://www.linkedin.com/search/results/all/?keywords="),
    "dev.to": ("chrome", "https://dev.to", "https://dev.to/search?q="),
    "luma": ("chrome", "https://lu.ma", None),
}
APPS = {"chrome": "chrome", "google chrome": "chrome", "edge": "edge", "microsoft edge": "edge", "notepad": "notepad.exe",
        "calculator": "calc.exe", "calc": "calc.exe", "file explorer": "explorer.exe", "explorer": "explorer.exe",
        "settings": "ms-settings:", "paint": "mspaint.exe", "files": "explorer.exe", "task manager": "taskmgr.exe",
        "claude": r"shell:AppsFolder\Claude_pzs8sxrjxfjjc!Claude", "chatgpt": r"shell:AppsFolder\OpenAI.Codex_2p2nqsd0c76g0!App"}  # Store apps have no plain exe path
BROWSERS = {"chrome": "chrome", "google chrome": "chrome", "edge": "edge", "microsoft edge": "edge"}
CLOSE = {"chrome": "chrome.exe", "edge": "msedge.exe", "notepad": "notepad.exe", "calculator": "CalculatorApp.exe",
         "paint": "mspaint.exe", "settings": "SystemSettings.exe", "task manager": "Taskmgr.exe", "claude": "Claude.exe", "chatgpt": "ChatGPT.exe"}
NEVER_CLOSE = {"python.exe", "pythonw.exe", "py.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "explorer.exe", "wscript.exe"}  # Jarvis itself, Windows itself
DESKTOPS = [os.path.expandvars(p) for p in (r"%USERPROFILE%\Desktop", r"%PUBLIC%\Desktop", r"%USERPROFILE%\OneDrive\Desktop")]
BYE = "Goodbye, sir."
TAB = {"youtube": r"\byoutube\b(?! music)", "dev.to": r"dev\.to|dev community", "claude console": r"claude console|anthropic", "google": r"\bgoogle\b(?! chrome)"}  # how a site shows in the tab's title
BROWSER_TITLE = re.compile(r"(?:microsoft\W*edge|google chrome)\W*$", re.I)
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
FOLDERS = {"desktop": "shell:Desktop", "downloads": "shell:Downloads", "download": "shell:Downloads", "documents": "shell:Personal", "pictures": "shell:My Pictures",
           "photos": "shell:My Pictures", "music": "shell:My Music", "videos": "shell:My Video", "this pc": "shell:MyComputerFolder", "my computer": "shell:MyComputerFolder",
           "c drive": "C:\\", "d drive": "D:\\"}
EXPLORER = {"file explorer", "explorer", "files", "windows explorer", "folder", "folders", "this folder", "all folders"}
# never by voice: anything that runs commands or changes the system
NEVER_OPEN = re.compile(r"command|powershell|terminal|registry|regedit|uninstall|\bcmd\b|\bbash\b|\bshell\b|\bconsole\b|recovery|defragment|disk cleanup|system configuration|"
                        r"component services|odbc|iscsi|security configuration|task scheduler|\bservices\b|event viewer|computer management|print management|local security|"
                        r"windows tools|administrative|\bsdk\b|\bsetup\b|repair|installer|\brun\b|"
                        r"narrator|magnifier|voice access|on-screen keyboard|screen reader|sticky keys", re.I)  # last line: accessibility tools that take over the PC (Narrator opened for "open yt")
START_CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "start_apps.json")
_start = None


def desktop_apps():
    """The shortcuts on the owner's desktops are the second allowlist: {name: path}. 'Wisperno Pro.lnk' -> 'wisperno pro'."""
    out = {}
    for d in DESKTOPS:
        try:
            for f in os.listdir(d):
                stem, ext = os.path.splitext(f)
                if ext.lower() in (".lnk", ".url") and not re.search(r"\b(?:copy|uninstall)\b|^jarvis$", stem, re.I):  # Jarvis's own shortcut is not an app to open
                    out.setdefault(re.sub(r"\s*-\s*shortcut$", "", stem, flags=re.I).lower(), os.path.join(d, f))
        except OSError:
            pass
    return out


def start_apps(refresh=False):
    """Everything in the Start menu (Armoury Crate, Spotify...) minus NEVER_OPEN: the third allowlist. {name: launch target}. Remembered in a file, refreshed at each launch."""
    global _start
    if _start is None and not refresh:
        try:
            with open(START_CACHE, encoding="utf-8") as f:
                _start = {k: v for k, v in json.load(f).items() if not NEVER_OPEN.search(k)}  # filtered again: the saved list may predate a rule
        except (OSError, ValueError):
            refresh = True
    if refresh:
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"],
                                 capture_output=True, encoding="utf-8", timeout=30, creationflags=NOWIN).stdout
            _start = {a["Name"].lower(): "shell:AppsFolder\\" + a["AppID"] for a in json.loads(out) if not NEVER_OPEN.search(a["Name"]) and not NEVER_OPEN.search(a["AppID"])}
            with open(START_CACHE, "w", encoding="utf-8") as f:
                json.dump(_start, f)
        except (OSError, ValueError, subprocess.SubprocessError):
            _start = _start or {}
    return _start


def find_installed(t):
    """Like find_app, but over the long Start menu list a close guess must also start with the same letter ('play' is not 'Uplay')."""
    menu = start_apps()
    d = find_app(t, menu)
    return d if d and (_squash(d)[:1] == _squash(t)[:1]) else None


def _label(path):
    return re.sub(r"\s*-\s*shortcut$", "", os.path.splitext(os.path.basename(path))[0], flags=re.I)


_THIS_TAB = r"close (?:the |this |my )?(?:current |open )?tab"
_OPEN = r"(?:open|launch|start|run|go to|navigate to|show me|take me to|bring up|pull up|visit)"
_SHUT = (r"(?:shut ?down|shut yourself down|power (?:down|off)|turn (?:yourself )?off|switch (?:yourself )?off|quit|exit|close|go offline|go to sleep)"
         r"(?: (?:yourself|jarvis|the assistant|completely|fully))*")


def direct(text):
    """An open / close / shut-down whose target is known exactly -> the clean command for handle(), else None.
    The rules do these without the AI: faster, and the AI can't swap 'Wisperno' for 'Wispr Flow'."""
    l = _canon(re.sub(r"^(?:(?:hey|ok|okay)[,.]?\s+)?jarvis[,.!?]?\s*", "", text.strip(), flags=re.I)).rstrip(" .!?")
    l = re.sub(r"^(?:(?:ok|okay|alright|right|so|and|now),?\s+)+", "", l)
    l = re.sub(r",?\s+jarvis$", "", l)
    if re.fullmatch(_SHUT, l) or re.fullmatch(_THIS_TAB, l):
        return l
    if re.match(r"(?:search|google|look up|look for)\b", l):  # a search is exact too: the rules use Google unless a site is named. The AI must not pick a site
        return l
    m = re.fullmatch(r"(?:%s|close|quit|exit|kill|end)\s+(?:the |my )?(.+?)(?:\s+(?:app|application|window|completely|fully|entirely))*" % _OPEN, l)
    if not m:
        return None
    known = [_known(p) for p in _several(m[1])]
    return l if all(known) or (len(known) > 1 and any(known)) else None  # several names: the rules sort them out, a name they don't know must not send the rest to the AI


def _known(t):
    t = re.sub(r"\s+(?:folder|directory)$", "", t)
    return t in SITES or t in APPS or t in FOLDERS or t in EXPLORER or re.search(r"\b(?:wispr|whisper|wisper)$", t) or find_app(t, desktop_apps()) is not None or find_installed(t) is not None


def mentioned(text):
    """Which apps/sites does this sentence name, spelled out? The AI may tidy a sentence but must not swap one app for another (it did: Whisper Flow -> Wisperno)."""
    sq = _squash(_canon(text))
    names = [*SITES, *APPS, *desktop_apps(), *start_apps()]
    hits = sorted({n for n in names if len(_squash(n)) >= 4 and _squash(n) in sq}, key=lambda n: sq.find(_squash(n)))
    return [n for n in hits if not any(n != o and _squash(n) in _squash(o) for o in hits)]


def _several(t):
    """'discord and whatsapp' -> ['discord', 'whatsapp']"""
    return list(dict.fromkeys(p.strip() for p in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", t) if p.strip()))


def _squash(s):
    return re.sub(r"[^a-z0-9]", "", s.lower()).replace("whisper", "wisper")


def find_app(t, apps):
    """'i hate pdf' -> 'ihatepdf', 'whisper no' / 'wisperno' -> 'wisperno pro'. None if nothing is close."""
    sq, names = _squash(t), {_squash(k): k for k in apps}
    if not sq:
        return None
    if sq in names:
        return names[sq]
    pre = [v for k, v in names.items() if k.startswith(sq) and len(sq) >= 4]
    if len(pre) == 1:
        return pre[0]
    near = difflib.get_close_matches(sq, names, n=1, cutoff=0.75)
    return names[near[0]] if near else None
MAX_TIMER = 24 * 3600
VK = {"mute": 0xAD, "down": 0xAE, "up": 0xAF, "next": 0xB0, "prev": 0xB1, "stop": 0xB2, "play": 0xB3}


def copy_image(img):
    """Put a picture on the clipboard, ready for Ctrl+V, like Windows' own screenshot keys."""
    import io
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "BMP")
    data = buf.getvalue()[14:]  # the clipboard wants a bitmap without the file header
    k, u = ctypes.windll.kernel32, ctypes.windll.user32
    k.GlobalAlloc.restype = k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    h = k.GlobalAlloc(2, len(data))
    ctypes.memmove(k.GlobalLock(h), data, len(data))
    k.GlobalUnlock(h)
    for _ in range(10):  # another program may be holding the clipboard for a moment
        if u.OpenClipboard(None):
            u.EmptyClipboard()
            u.SetClipboardData(8, h)  # 8 = bitmap
            u.CloseClipboard()
            return True
        time.sleep(0.05)
    return False


def screenshots_folder():
    b = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 39, None, 0, b)  # 39 = My Pictures, wherever OneDrive may have moved it
    return os.path.join(b.value or os.path.expandvars(r"%USERPROFILE%\Pictures"), "Screenshots")


def _exe(browser):
    pf, pf86, local = (os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"))
    paths = {"edge": [pf86 + r"\Microsoft\Edge\Application\msedge.exe", pf + r"\Microsoft\Edge\Application\msedge.exe"],
             "chrome": [pf + r"\Google\Chrome\Application\chrome.exe", pf86 + r"\Google\Chrome\Application\chrome.exe",
                        local + r"\Google\Chrome\Application\chrome.exe"]}[browser]
    return next((p for p in paths if os.path.isfile(p)), None)


class Real:
    def open_url(self, browser, url):
        """Returns the browser used, or None if it fell back to the Windows default browser."""
        exe = _exe(browser)
        if exe:
            subprocess.Popen([exe, url])
            self.focus(r"microsoft\W*edge\W*$" if browser == "edge" else r"google chrome\W*$")
            return browser
        os.startfile(url)

    def launch(self, target):
        exe = _exe(target) if target in ("chrome", "edge") else None
        if exe:
            subprocess.Popen([exe])
        else:
            os.startfile(target)

    def focus(self, pattern):
        """Windows won't let a background app put another program in front on its own, so a tab opened in a running browser stays hidden. Bring it forward."""
        def run():
            time.sleep(0.4)
            for _ in range(16):
                wins = self._windows(lambda h: re.search(pattern, self._title(h), re.I))
                if wins:
                    self._front(wins[0])
                    return
                time.sleep(0.25)
        threading.Thread(target=run, daemon=True).start()

    def key(self, name, n=1):
        u = ctypes.windll.user32
        for _ in range(n):
            u.keybd_event(VK[name], 0, 0, 0)
            u.keybd_event(VK[name], 0, 2, 0)
            time.sleep(0.004)

    def running(self):
        """The file names of every running program. Asks Windows directly: milliseconds, where tasklist took up to 8 s when the PC was busy."""
        k = ctypes.windll.kernel32
        k.CreateToolhelp32Snapshot.restype = ctypes.c_void_p

        class Entry(ctypes.Structure):
            _fields_ = [("size", ctypes.c_ulong), ("usage", ctypes.c_ulong), ("pid", ctypes.c_ulong), ("heap", ctypes.c_size_t), ("module", ctypes.c_ulong),
                        ("threads", ctypes.c_ulong), ("parent", ctypes.c_ulong), ("pri", ctypes.c_long), ("flags", ctypes.c_ulong), ("exe", ctypes.c_wchar * 260)]
        snap, e, out = ctypes.c_void_p(k.CreateToolhelp32Snapshot(2, 0)), Entry(), set()
        e.size = ctypes.sizeof(Entry)
        ok = k.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            out.add(e.exe)
            ok = k.Process32NextW(snap, ctypes.byref(e))
        k.CloseHandle(snap)
        return sorted(out)

    def _windows(self, test):
        u, found = ctypes.windll.user32, []
        proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(
            lambda h, _: (found.append(h) if u.IsWindowVisible(ctypes.c_void_p(h)) and test(ctypes.c_void_p(h)) else None, True)[1])
        u.EnumWindows(proc, None)
        return found

    def close_folders(self, pattern=None):
        """Close File Explorer WINDOWS (all, or those whose title matches). Never the explorer program: that is the taskbar and desktop too."""
        def is_folder(h):
            b = ctypes.create_unicode_buffer(64)
            ctypes.windll.user32.GetClassNameW(h, b, 64)
            return b.value == "CabinetWClass" and (pattern is None or re.search(pattern, self._title(h), re.I))
        wins = self._windows(is_folder)
        for h in wins:
            ctypes.windll.user32.PostMessageW(ctypes.c_void_p(h), 0x10, 0, 0)  # WM_CLOSE
        return len(wins)

    def screenshot(self):
        """The whole screen (every monitor) -> Pictures\\Screenshots. Returns the file path."""
        from PIL import ImageGrab
        d = screenshots_folder()
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, time.strftime("Jarvis %Y-%m-%d %H-%M-%S.png"))
        u = ctypes.windll.user32
        u.FindWindowW.restype = ctypes.c_void_p
        island = u.FindWindowW("JarvisIsland", None)  # the pill stays out of the picture
        if island:
            u.ShowWindow(ctypes.c_void_p(island), 0)
            time.sleep(0.05)
        img = ImageGrab.grab(all_screens=True)
        if island:
            u.ShowWindow(ctypes.c_void_p(island), 8)
        img.save(path)
        copy_image(img)
        return path

    def _front(self, raw):
        """Bring a window to the front. False if Windows refused."""
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        h = ctypes.c_void_p(raw)
        if u.IsIconic(h):
            u.ShowWindow(h, 9)
        if u.GetForegroundWindow() != raw:
            u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0)  # Windows only lets the app that last had a key press change the front window
            u.SetForegroundWindow(h)
            time.sleep(0.12)
        return u.GetForegroundWindow() == raw

    def _browsers(self):
        return self._windows(lambda h: BROWSER_TITLE.search(self._title(h)))

    def _find_tab(self, pattern):
        """Bring the tab whose title matches to the front (stepping through tabs). The window handle, or None."""
        for raw in self._browsers():
            if not self._front(raw):
                continue
            h, first = ctypes.c_void_p(raw), None
            for _ in range(60):
                title = self._title(h)
                page = BROWSER_TITLE.sub("", title)
                if re.search(pattern, page, re.I):
                    return raw
                if page == first or not self._chord(raw, 0x09):
                    break
                first = first or page
                self._settle(h, title, 0.25)
        return None

    def video_key(self, vk, shift=False):
        """A YouTube keyboard shortcut (K = pause, F = fullscreen...) sent to the YouTube tab. False if there is none."""
        raw = self._find_tab(TAB["youtube"])
        if raw is None:
            return False
        u = ctypes.windll.user32
        if shift:
            u.keybd_event(0x10, 0, 0, 0)
        u.keybd_event(vk, 0, 0, 0); u.keybd_event(vk, 0, 2, 0)
        if shift:
            u.keybd_event(0x10, 0, 2, 0)
        return True

    def first_video(self, wait=0):
        """Click the first video on the YouTube page in front, through Windows' accessibility interface. False if none was found."""
        time.sleep(wait)
        raw = self._find_tab(TAB["youtube"])
        if raw is None:
            return False
        ps = ("Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;"
              "$a=[Windows.Automation.AutomationElement];$r=$a::FromHandle([IntPtr]%d);"
              "$c=New-Object Windows.Automation.PropertyCondition($a::ControlTypeProperty,[Windows.Automation.ControlType]::Hyperlink);"
              "foreach($e in $r.FindAll([Windows.Automation.TreeScope]::Descendants,$c)){$v=$null;"
              "if($e.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$v) -and $v.Current.Value -match '/watch\\?v='){"
              "$e.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke();'clicked';break}}") % raw
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20, creationflags=NOWIN).stdout
        return "clicked" in out

    def _title(self, h):
        b = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(h, b, 512)
        return b.value

    def _chord(self, h, vk):
        """Ctrl+key, only if that window is still the one in front: never send it to something else."""
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        if u.GetForegroundWindow() != h:
            return False
        u.keybd_event(0x11, 0, 0, 0); u.keybd_event(vk, 0, 0, 0); u.keybd_event(vk, 0, 2, 0); u.keybd_event(0x11, 0, 2, 0)
        return True

    def _settle(self, h, old, wait):
        end = time.time() + wait
        while time.time() < end and self._title(h) == old:
            time.sleep(0.02)

    def close_tab(self, pattern=None):
        """Close the browser tabs whose title matches (None = the tab in front). Windows only show the title of their front tab,
        so step through the tabs with Ctrl+Tab. Returns how many closed. A window's last tab closes the window: fine by the owner."""
        n = 0
        for raw in self._browsers():
            h = ctypes.c_void_p(raw)
            if not self._front(raw):
                continue
            first = None
            for _ in range(60):  # ponytail: at most 60 steps per window; raise it if someone keeps more tabs
                title = self._title(h)
                if not BROWSER_TITLE.search(title):
                    break  # the window is gone
                page = BROWSER_TITLE.sub("", title)
                if pattern is None or re.search(pattern, page, re.I):
                    if not self._chord(raw, 0x57):
                        return n
                    n += 1
                    self._settle(h, title, 0.5)
                    first = None
                    if pattern is None:
                        return n
                elif page == first:
                    break  # been all the way round
                else:
                    first = first or page
                    if not self._chord(raw, 0x09):
                        return n
                    self._settle(h, title, 0.25)
            if pattern is None:
                return n
        return n

    def target(self, lnk):
        """The program a .lnk shortcut starts (its exe file name), or None."""
        if not lnk.lower().endswith(".lnk"):
            return None
        try:modified=os.stat(lnk).st_mtime_ns
        except OSError:return None
        return self._target_cached(lnk,modified)

    @lru_cache(maxsize=128)
    def _target_cached(self,lnk,modified):
        ps = "(New-Object -ComObject WScript.Shell).CreateShortcut('%s').TargetPath" % lnk.replace("'", "''")
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=10, creationflags=NOWIN).stdout.strip()
        return os.path.basename(out) or None

    def close_processes(self, exes, timeout=0.75):
        """Close visible windows directly; verify windows, not browser background
        workers. Never force-close an unsaved document or confirmation dialog.
        Only a tray-only process (no visible windows) is ended directly.
        """
        import psutil
        allowed = {x.lower() for x in exes if x.lower() not in NEVER_CLOSE}
        procs = []
        for p in psutil.process_iter(['pid', 'name']):
            if (p.info['name'] or '').lower() in allowed:
                procs.append(p)
        if not procs:
            return True, False
        pids = {p.pid for p in procs}
        windows = self._process_windows(pids)
        if windows:
            for hwnd in windows:
                ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), 0x10, 0, 0)
            end = time.monotonic() + timeout
            while self._process_windows(pids):
                if time.monotonic() >= end:
                    return False, True
                time.sleep(0.015)
            return True, True
        for p in procs:
            try:
                p.terminate()
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                return False, True
        _, alive = psutil.wait_procs(procs, timeout=timeout)
        return not alive, True

    def _process_windows(self, pids):
        def owned(hwnd):
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value in pids
        return self._windows(owned)

    def close(self, exe):
        """Close every window of `exe` politely; whatever is still running 2 s later (tray apps) is ended. False if it wasn't running."""
        running = lambda: exe.lower() in (x.lower() for x in self.running())
        if not running():
            return False
        kill = lambda *f: subprocess.run(["taskkill", "/IM", exe, "/T", *f], capture_output=True, creationflags=NOWIN)

        def finish():
            kill()
            for _ in range(10):
                time.sleep(0.2)
                if not running():
                    return
            kill("/F")
        threading.Thread(target=finish, daemon=True).start()
        return True


backend = Real()
muted = False  # ponytail: Windows has no cheap "read mute" call, so this is our best guess; an outside change can fool it

NUMW = "|".join(sorted([*UNITS, *TENS, "hundred"], key=len, reverse=True))
NUM = r"(?:\d+(?:\.\d+)?|(?:%s)(?:[\s-]+(?:%s))*)" % (NUMW, NUMW)


def num(s):
    s = s.strip().lower()
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)
    n = 0
    for w in re.split(r"[\s-]+", s):
        if w in UNITS or w in TENS:
            n += UNITS[w] if w in UNITS else TENS[w]
        elif w == "hundred":
            n = (n or 1) * 100
        else:
            return None
    return n


def _canon(s):
    s = s.lower()
    for a, b in [(r"\byou tube\b", "youtube"), (r"\b(?:yt|youtube)\s?music\b", "youtube music"), (r"\byt\b", "youtube"),
                 (r"\bdev(?: dot)? to\b|\bdevto\b", "dev.to"), (r"\blinked in\b", "linkedin"), (r"\blu\.ma\b", "luma"),
                 (r"\b(?:loom|looma|lumma|lu ma)\b", "luma"), (r"\bdefault brows\w*\b", "default browser"),
                 (r"\banthropic console\b", "claude console"), (r"\b(?:chat ?g ?[pb] ?[td]|g ?p ?t)\b", "chatgpt"), (r"\bwh?isp(?:e)?r[ ,.]*flo(?:w|ws)?\b", "wispr flow"), (r"\barmou?ry ?crates?\b", "armoury crate"), (r"\bscreen shot\b", "screenshot"),
                 (r"^((?:open|launch|start|run|close|quit|kill|exit|end) (?:up )?(?:the |my )?)(?:cloud|clawed|clod|claud|clode|clause)\b(?! console)", r"\1claude"), (r"\bgoogle chrome\b", "chrome"), (r"\bmicrosoft edge\b", "edge")]:
        s = re.sub(a, b, s)
    s = re.sub(r"^(?:(?:(?:can|could|would|will) you|i (?:want|need) you to|i'd like you to|go ahead and|let's|please)\s+)+", "", s)
    s = re.sub(r"^to (open|close)\b", r"\1", s)  # "to open YouTube": a stray first word
    s = re.sub(r"^(open|pull|bring|start) up\b", r"\1", s)  # "open up YouTube"
    s = re.sub(r"^(open|close|launch|start|quit|kill|exit)[,.]\s+", r"\1 ", s)  # "Close, Wisperno Pro"
    s = re.sub(r"\s+both$", "", s)
    return re.sub(r"(?:\s+(?:please|for me|now))+$", "", s).strip()


_SITE = "|".join(re.escape(k) for k in sorted(SITES, key=len, reverse=True))
_BR = r"(?:\s+(?:in|on|using|with|via)\s+(chrome|edge))?$"
_DUR = re.compile(r"(%s|an?|half an?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b" % NUM)


def _name(site):
    return {"youtube": "YouTube", "youtube music": "YouTube Music", "linkedin": "LinkedIn", "dev.to": "dev.to", "chatgpt": "ChatGPT"}.get(site, site.title())


def _go(fn, *a):
    try:
        return True, fn(*a)
    except Exception:  # missing exe, blocked launch...: say so, never crash the assistant
        return False, None


def _open(site, browser=None):
    b, home, _ = SITES[site]
    ok, used = _go(backend.open_url, browser or b, home)
    return f"Opening {_name(site)} in {(browser or b).title()}, sir." if ok else f"I couldn't open {site}, sir."


def _search(site, query, browser=None):
    b, _, url = SITES[site]
    ok, _ = _go(backend.open_url, browser or b, url + quote_plus(query[:200]))
    return f"Searching {_name(site)} for {query}, sir." if ok else f"I couldn't search {site}, sir."


def label_secs(label):
    """A timer's length from its label: '1-hour and 5-minute' -> 3900."""
    return sum(int(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in re.findall(r"(\d+)-(h|m|s)", label))


def _length(l):
    secs = sum((num(n) if not n.startswith(("a", "half")) else (0.5 if n.startswith("half") else 1)) * {"s": 1, "m": 60, "h": 3600}[u[0]]
               for n, u in _DUR.findall(l) if num(n) is not None or n.startswith(("a", "half")))
    return round(secs)


def _spoken_timer(r):
    return r["text"].replace("-", " ") + " timer"


def _which_timers(l, rows, verb, store):
    """The timers a sentence means: a length names them, 'all' or 'both' means all, and with only one there is no doubt.
    Returns (rows, None), or (None, a reply) when it has to ask or there is no such timer."""
    secs = _length(l)
    if secs:
        hit = [r for r in rows if label_secs(r["text"]) == secs]
        if hit:
            return hit, None
        return None, f"You have no timer of that length to {verb}, sir."
    if len(rows) <= 1 or re.search(r"\b(?:all|both|every|everything)\b", l):
        return rows, None
    store.pending = ("combine", f"{verb} the timer ")
    return None, "Which timer, sir: " + " or ".join("the " + r["text"].replace("-", " ") for r in rows) + "?"


def _done(rows, what):
    return f"{_spoken_timer(rows[0]).capitalize()} {what}, sir." if len(rows) == 1 else ("Both timers " if len(rows) == 2 else f"All {len(rows)} timers ") + f"{what}, sir."


def _timer(l, store, now):
    if re.search(r"\b(?:cancel|stop|delete|clear|remove|kill|end)\b.*\btimers?\b", l):
        rows, ask = _which_timers(l, store.all_timers(), "cancel", store)
        if ask:
            return ask
        for r in rows:
            store.delete(r["id"])
        return _done(rows, "cancelled") if rows else "You have no timers running, sir."
    if re.search(r"\b(?:pause|hold|freeze)\b.*\btimers?\b", l):
        rows, ask = _which_timers(l, store.timers(), "pause", store)
        if ask:
            return ask
        for r in rows:
            store.pause_timer(r["id"], now)
        return _done(rows, "paused") if rows else "You have no timers running, sir."
    if re.search(r"\b(?:resume|continue|unpause|restart)\b.*\btimers?\b", l):
        rows, ask = _which_timers(l, [r for r in store.all_timers() if r["status"] == "paused"], "resume", store)
        if ask:
            return ask
        for r in rows:
            store.resume_timer(r["id"], now)
        return _done(rows, "running again") if rows else "No timer is paused, sir."

    def status():
        rows = store.timers()
        if _length(l):
            rows = [r for r in rows if label_secs(r["text"]) == _length(l)]
        return "\n".join(f"{r['text']} timer, {_left(r['due'], now)} left" for r in rows) if rows else "You have no timers running, sir."

    if re.search(r"\b(?:how (?:long|much)|what|which|any|show|list|check|status|remaining)\b.*\b(?:timers?|time left|left|remaining)\b", l) and not re.search(r"\b(?:set|start|make|create|put|add)\b", l):
        return status()
    if not re.search(r"\b(?:timer|countdown)\b", l):
        return None
    secs = _length(l)
    if secs < 1:  # "set a timer" asks how long; any other talk about a timer without a length shows the running ones
        return "How long should the timer run, sir?" if re.search(r"\b(?:set|start|make|create|begin|keep|put|run|add|new)\b", l) else status()
    if secs > MAX_TIMER:
        return "Timers go up to 24 hours, sir. For longer, set a reminder."
    h, m, s = secs // 3600, secs % 3600 // 60, secs % 60
    label = " and ".join(f"{v}-{u}" for v, u in ((h, "hour"), (m, "minute"), (s, "second")) if v)
    row, merged = store.add(label, now + timedelta(seconds=secs), kind="timer")
    return f"{'Restarted the' if merged else 'Timer set:'} {label.replace('-', ' ')} timer, sir."


def _left(due, now):
    s = max(0, int((datetime.fromisoformat(due) - now).total_seconds()))
    return f"{s // 3600} hours {s % 3600 // 60} minutes" if s >= 3600 else f"{s // 60} minutes {s % 60} seconds" if s >= 60 else f"{s} seconds"


_UP = r"(?:increase|raise|turn up|boost|up|speed up|louder|higher|faster)"
_DOWN = r"(?:decrease|lower|reduce|turn down|down|slow down|quieter|softer|lower|slower)"


def voice_tune(text):
    """Jarvis's OWN voice: 'speak slower', 'increase your volume' -> ('speed'|'volume', +1|-1), else None."""
    l = _canon(re.sub(r"^(?:(?:hey|ok|okay)[,.]?\s+)?jarvis[,.!?]?\s*", "", text.strip(), flags=re.I)).rstrip(" .?!")
    m = re.fullmatch(r"(?:speak|talk|say it|read)\s+(?:a bit |a little |much )?(slower|slow|more slowly|faster|fast|more quickly|quicker|louder|more loudly|quieter|more quietly|softer)", l)
    if m:
        w = m[1]
        return ("speed" if re.search(r"slow|fast|quick", w) else "volume", -1 if re.search(r"slow|quiet|soft", w) else 1)
    if re.fullmatch(r"(?:slow down|speed up)", l):
        return "speed", -1 if l == "slow down" else 1
    m = re.fullmatch(r"(%s|%s)\s+(?:your|jarvis'?s?)\s+(?:speech |voice |speaking )?(volume|speed)(?: a bit| a little)?" % (_UP, _DOWN), l) \
        or re.fullmatch(r"(?:your|jarvis'?s?)\s+(?:speech |voice |speaking )?(volume|speed)\s+(up|down|higher|lower)", l)
    if m:
        if m.re.pattern.startswith("(?:your"):
            return m[1], 1 if m[2] in ("up", "higher") else -1
        return m[2], 1 if re.fullmatch(_UP, m[1]) else -1
    return None


def _volume(l):
    global muted
    if voice_tune(l):
        return "I can only change my own voice inside the app, sir."
    if re.fullmatch(r"(?:un)?mute(?: (?:the )?(?:sound|volume|audio|music|laptop|pc|computer))?", l):
        want = not l.startswith("un")
        if want == muted:
            return "Already muted, sir." if muted else "Not muted, sir."
        if want:
            backend.key("mute")
        else:  # a volume key unmutes; up then down leaves the level where it was
            backend.key("up"); backend.key("down")
        muted = want
        return "Muted, sir." if want else "Unmuted, sir."
    if not re.search(r"\bvolume\b|\blouder\b|\bquieter\b|\bsofter\b|\bturn it (?:up|down)\b|\bturn (?:up|down) the sound\b", l):
        return None
    m = re.search(r"(?:to|at|volume|set)\s+(%s)\s*(?:%%|percent)?(?:\s+volume)?$" % NUM, l) or re.search(r"\b(%s)\s*(?:%%|percent)\s*(?:volume)?$" % NUM, l)
    level = num(m[1]) if m and "by" not in l.split(m[1])[0].split()[-1:] else None
    if level is None:
        level = 100 if re.search(r"\b(?:max|maximum|full)\b", l) else 50 if re.search(r"\bhalf\b", l) else None
    if level is not None:
        level = int(min(100, level))
        backend.key("down", 50); backend.key("up", round(level / 2))  # one key press = 2%
        muted = False
        return f"Volume set to about {level} percent, sir."
    up = re.search(r"\b(?:up|increase|raise|louder|higher|boost|more)\b", l)
    down = re.search(r"\b(?:down|decrease|lower|reduce|quieter|softer|less)\b", l)
    if bool(up) == bool(down):
        return "Up or down, sir?"
    by = re.search(r"\bby\s+(%s)" % NUM, l)
    n = max(1, min(50, round(num(by[1]) / 2))) if by and num(by[1]) else 5
    backend.key("up" if up else "down", n)
    muted = False
    return "Volume up, sir." if up else "Volume down, sir."


def _media(l):
    if re.fullmatch(r"(?:next|skip)(?: (?:the |this )?(?:song|track|one|video))?|play (?:the )?next(?: song| track)?", l):
        backend.key("next"); return "Next track, sir."
    if re.fullmatch(r"(?:previous|last|go back|back)(?: (?:song|track|one))?|play (?:the )?(?:previous|last)(?: song| track)?", l):
        backend.key("prev"); return "Previous track, sir."
    m = re.fullmatch(r"(pause|stop|resume|play|continue)(?: (?:the )?(?:music|song|video|playback|media|it))?", l)
    if m:  # ponytail: one play/pause key does all four; it toggles, so "pause" while paused would start it
        backend.key("play")
        return {"pause": "Paused, sir.", "stop": "Stopped, sir."}.get(m[1], "Playing, sir.")
    return None


def _close_tab(name):
    """name = a site or a word in the tab's title; None = the tab in front. Reply, or None if no such tab."""
    ok, n = _go(backend.close_tab, None if name is None else TAB.get(name, r"\b%s\b" % re.escape(name)))
    if not ok or not n:
        return None
    return "Closing the tab, sir." if name is None else f"Closing {_name(name)}, sir."


# YouTube's own keyboard shortcuts: (what you say, key, shift, reply)
VIDEO = [(r"(?:pause|stop) (?:the |this |my )?(?:video|youtube)", 0x4B, False, "Paused, sir."), (r"(?:play|resume|continue) (?:the |this |my )?(?:video|youtube)", 0x4B, False, "Playing, sir."),
         (r"(?:make (?:it|this|the video) |go |exit |leave )?full ?screen", 0x46, False, "Full screen, sir."), (r"next video", 0x4E, True, "Next video, sir."),
         (r"(?:skip (?:ahead|forward|10 seconds)|fast ?forward|go forward)(?: (?:the |this )?video)?", 0x4C, False, "Skipping ahead, sir."),
         (r"(?:rewind|go back 10 seconds|skip back(?:wards?)?)(?: (?:the |this )?video)?", 0x4A, False, "Going back, sir."),
         (r"(?:turn (?:on|off) |show |hide )?(?:captions|subtitles)", 0x43, False, "Captions switched, sir."), (r"(?:un)?mute (?:the |this )?video", 0x4D, False, "Done, sir.")]
FIRST = r"(?:play|click(?: on)?|open|watch|start) (?:the )?(?:first|top)(?: one| video| result)?"
SHOT = r"(?:(?:take|click|capture|grab|get|make|save)(?: me)? (?:a |an |the )?)?(?:screenshot|screen ?grab|snapshot|(?:picture|photo|image) of (?:the |my )screen)(?: of (?:the |this |my )?(?:current |whole |entire |full )?screen)?(?: please)?"


def _front_app(name):
    _go(lambda: backend.focus(r"\b" + r"\W*".join(map(re.escape, name.split())) + r"\b"))


def merge_replies(replies):
    """'Closing Edge, sir.' + 'Closing WhatsApp, sir.' -> 'Closing Edge and WhatsApp, sir.' One sentence, not the same one again and again."""
    parts = [r for r in replies if r]
    if len(parts) < 2:
        return parts[0] if parts else ""
    plain = [re.sub(r",? sir\.$", "", r) for r in parts]
    join = lambda xs: ", ".join(xs[:-1]) + " and " + xs[-1]
    for lead in ("Opening ", "Closing "):
        if all(p.startswith(lead) for p in plain):
            return lead + join([p[len(lead):] for p in plain]) + ", sir."
    if all(p.startswith("Timer set: ") for p in plain):
        return "Timers set: " + join([p[11:].replace(" timer", "") for p in plain]) + ", sir."
    return " ".join(parts)


def _close_folder(t):
    """'close file explorer', 'close downloads'. A reply, or None if t is no folder."""
    if t not in EXPLORER and t not in FOLDERS:
        return None
    pattern = None if t in EXPLORER else {"download": "downloads", "photos": "pictures", "my computer": "this pc", "c drive": r"\(c:\)", "d drive": r"\(d:\)"}.get(t, t)
    ok, n = _go(backend.close_folders, pattern)
    return ("Closing that folder, sir." if pattern else "Closing File Explorer, sir.") if ok and n else ("There's no such folder open, sir." if pattern else "File Explorer isn't open, sir.")


def act(l, store, now):
    l = _canon(l)
    m = re.fullmatch(r"((?:open|launch|start|run|close|quit|kill|exit|end)\s+)(?:the |my )?(.+)", l)
    if m and len(_several(m[2])) > 1:  # "close discord and whatsapp"
        return merge_replies([act(m[1] + p, store, now) for p in _several(m[2])])
    if re.fullmatch(SHOT, l):
        ok, _ = _go(backend.screenshot)
        return "Screenshot taken, sir." if ok else "I couldn't take the screenshot, sir."
    if re.fullmatch(FIRST, l):
        ok, done = _go(backend.first_video)
        return "Playing the first video, sir." if ok and done else "I can't see a YouTube results page, sir."
    for pat, vk, shift, say in VIDEO:
        if re.fullmatch(pat, l):
            ok, done = _go(backend.video_key, vk, shift)
            return say if ok and done else "I can't see YouTube open, sir."
    r = _timer(l, store, now) or _volume(l) or _media(l)
    if r:
        return r

    if re.search(r"\bdefault browser\b", l) and re.search(r"\b(?:make|set|change|switch|use)\b", l):
        ok, _ = _go(backend.launch, "ms-settings:defaultapps")
        want = "Chrome" if "chrome" in l else "Edge" if "edge" in l else "your browser"
        return ("Windows doesn't let me change that quietly, sir. I've opened the page: click the search box at the top, "
                f"type {want}, click it, then press 'Set default'.") if ok else "I couldn't open the settings page, sir."

    if re.fullmatch(r"(?:what can you (?:do|open)|help|what are your commands)", l):
        return ("I can: set reminders and notes, set timers, open " + ", ".join(SITES) + ", " + ", ".join(
            k for k in APPS if k not in ("calc", "explorer", "google chrome", "microsoft edge")) + ", and anything with a shortcut on your desktop "
            "(\"open Wisperno Pro\", \"close IHatePDF\"); search (\"search lo-fi on youtube\"); play, pause, next, volume up/down/mute; "
            "\"shut down\" closes me completely.")

    if re.fullmatch(r"(?:search|google|look up|look for|find)(?: for)?(?: (?:this|that|it|something))?(?:\s+(?:in|on|using|with|via)\s+(?:chrome|edge))?", l):
        return "Search for what, sir?"

    br = re.search(r"\s+(?:in|on|using|with|via)\s+(chrome|edge)$", l)
    browser, core = (br[1], l[:br.start()]) if br else (None, l)

    m = re.fullmatch(r"play\s+(.+?)(?:\s+(?:on|in|from)\s+(%s))?" % _SITE, core)
    if m and not re.fullmatch(r"(?:the )?(?:next|previous|last)(?: song| track)?", m[1]):
        if m[2] == "youtube" and m[1] not in ("music", "some music", "songs"):  # the results page, then its first video once the page has loaded
            threading.Thread(target=_go, args=(backend.first_video, 4), daemon=True).start()
        return _search(m[2] or "youtube music", m[1], browser) if m[1] not in ("music", "some music", "songs") else _open(m[2] or "youtube music", browser)

    m = (re.fullmatch(r"(?:search|find|look up|look for)\s+(?:on\s+|in\s+)?(%s)\s+for\s+(.+)" % _SITE, core)
         or re.fullmatch(r"(?:search|google|find|look up|look for)(?: for)?\s+(.+?)\s+(?:on|in|at)\s+(%s)" % _SITE, core))
    if m:
        site, q = (m[1], m[2]) if m[1] in SITES else (m[2], m[1])
    else:
        m = re.fullmatch(r"(?:search(?: for)?|google|look up|look for|find)\s+(.+)", core)
        site, q = "google", m and m[1]
    if m:
        q = re.sub(r"^(?:a|an|the)\s+", "", q.strip(" .,!?"))
        if not q:
            return "Search for what, sir?"
        if SITES[site][2] is None:
            return f"I can't search {_name(site)} yet, sir."
        return _search(site, q, browser)

    m = re.fullmatch(_OPEN + r"\s+(?:the |my )?(.+?)(?:\s+(?:website|site|app|application|page|tab|folder|directory))?", core)
    if m:
        t = m[1].strip(" .,!?")
        if core.startswith("show me") and not _known(t) and t != "screenshots":
            return None  # "show me today" is a question, not something to open
        if t in ("whisper", "wisper", "wispr"):
            return "Open Wispr Flow or Wisperno Pro, sir?"
        if t in FOLDERS or t == "screenshots":
            ok, _ = _go(backend.launch, FOLDERS.get(t) or (os.makedirs(screenshots_folder(), exist_ok=True) or screenshots_folder()))
            _front_app(t)
            return f"Opening {t.title()}, sir." if ok else f"I couldn't open {t}, sir."
        desk = desktop_apps() if t not in SITES and t not in APPS else {}
        d = find_app(t, desk)
        if d:  # a shortcut on the desktop: Wisperno Pro, IHatePDF, Discord...
            ok, _ = _go(backend.launch, desk[d])
            _front_app(_label(desk[d]))
            return f"Opening {_label(desk[d])}, sir." if ok else f"I couldn't open {d}, sir."
        near = difflib.get_close_matches(t, [*SITES, *APPS], n=1, cutoff=0.65)
        d = find_installed(t) if t not in SITES and t not in APPS and not (near and near[0][0] == t[0]) else None
        if d:  # anything else installed: Armoury Crate...
            ok, _ = _go(backend.launch, start_apps()[d])
            _front_app(d)
            return f"Opening {d.title()}, sir." if ok else f"I couldn't open {d}, sir."
        if t not in SITES and t not in APPS:  # speech-to-text mishears ("notal", "notetab"): accept a close match to an allowlisted name only
            near = difflib.get_close_matches(t, [*SITES, *APPS], n=1, cutoff=0.65)
            t = near[0] if near and near[0][0] == t[0] else t
        if t in SITES:
            return _open(t, browser)
        if t in APPS:
            ok, _ = _go(backend.launch, APPS[t])
            _front_app({"calc": "calculator", "files": "file explorer"}.get(t, t))
            return f"Opening {_name(t)}, sir." if ok else f"I couldn't open {t}, sir."
        return f"I'm afraid '{t}' isn't on my list, sir. I can open the websites I know, your folders, and any installed app."

    if re.fullmatch(_THIS_TAB, l):
        return _close_tab(None) or "I can't see a browser tab to close, sir."
    if re.fullmatch(_SHUT, l):
        return BYE  # the app sees this reply, says it, and closes itself completely
    m = re.fullmatch(r"(?:close|quit|exit|kill|shut|end)\s+(?:down\s+)?(?:the |my )?(.+?)(?:\s+(?:app|application|window|completely|fully|entirely))*", l)
    if m:
        t = re.sub(r"\s+(?:folder|directory)$", "", m[1].strip(" .,!?"))
        if t in ("whisper", "wisper", "wispr"):
            return "Close Wispr Flow or Wisperno Pro, sir?"
        r = _close_folder(t)
        if r:
            return r
        tab = re.fullmatch(r"(.+?) (?:tab|website|site|page)", t)
        if tab or t in SITES:  # "close YouTube" = its tab
            r = _close_tab(tab[1] if tab else t)
            if r:
                return r
            t = tab[1] if tab else t
        exes, name = [CLOSE[k]] if (k := BROWSERS.get(t) or {"calc": "calculator"}.get(t, t)) in CLOSE else [], t
        desk = {**start_apps(), **desktop_apps()}
        d = (find_app(t, desktop_apps()) or find_installed(t)) if not exes else None
        if d:
            name = _label(desk[d]) if desk[d].lower().endswith((".lnk", ".url")) else d.title()
            # by running program first: Store apps (WhatsApp) and some launchers have no useful target in their shortcut
            sq = _squash(name)
            exes = [x for x in (_go(backend.running)[1] or []) if len(sq) >= 4 and _squash(x[:-4]).startswith(sq)]
            if not exes:
                ok, exe = _go(backend.target, desk[d])
                exes = [exe] if ok and exe else []
        exes = [x for x in exes if x.lower() not in NEVER_CLOSE]
        if not exes:
            if t in SITES:
                return f"{_name(t)} isn't open, sir."
            return (not l.startswith("shut") and _close_tab(t)) or f"I'm afraid I can't close '{t}', sir."  # no such app: maybe a tab with that title ("shut down the laptop" never is)
        ok, was = True, False
        for exe in exes:
            ok1, w = _go(backend.close, exe)
            ok, was = ok and ok1, was or bool(w)
        name = _name(name) if name in CLOSE else name[0].upper() + name[1:]
        return (f"Closing {name}, sir." if was else f"{name} isn't running, sir.") if ok else f"I couldn't close {name}, sir."
    return None
