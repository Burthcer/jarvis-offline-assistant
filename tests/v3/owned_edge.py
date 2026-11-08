"""An OWNED Edge for real-site checks: fresh temporary profile (signed out, none of the owner's data), muted, no autoplay, closed and deleted afterwards.
Only this browser's own window is ever read or clicked (by handle), never the window the owner is using."""
import ctypes, os, shutil, subprocess, tempfile, time
from contextlib import contextmanager
from pathlib import Path
import psutil

EDGE = Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
ROOT = Path(__file__).resolve().parents[2]
u = ctypes.windll.user32


def _windows(pids):
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def each(h, _):
        pid = ctypes.c_ulong(); u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if pid.value in pids and u.IsWindowVisible(h):
            n = u.GetWindowTextLengthW(h); buf = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, buf, n + 1)
            cls = ctypes.create_unicode_buffer(64); u.GetClassNameW(h, cls, 64)
            if cls.value == 'Chrome_WidgetWin_1' and buf.value:
                found.append((h, buf.value))
        return True
    u.EnumWindows(each, 0)
    return found


def title(hwnd):
    n = u.GetWindowTextLengthW(hwnd); buf = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(hwnd, buf, n + 1); return buf.value


@contextmanager
def owned_edge(*urls, wait_for='', timeout=30):
    (ROOT / 'data/v3-dev-checks').mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='v4-edge-', dir=ROOT / 'data/v3-dev-checks')).resolve()
    marker = '--user-data-dir=' + str(folder)
    owned = lambda: [p for p in psutil.process_iter(['cmdline', 'exe']) if marker in (p.info['cmdline'] or [])]
    subprocess.Popen([str(EDGE), marker, '--no-first-run', '--no-default-browser-check', '--disable-sync', '--disable-extensions', '--mute-audio',
                      '--autoplay-policy=user-gesture-required', '--window-size=1400,1000', '--window-position=60,40', '--new-window', *urls],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        end, hwnd = time.monotonic() + timeout, None
        while time.monotonic() < end:
            wins = _windows({p.pid for p in owned()})
            if wins and (not wait_for or wait_for.lower() in wins[0][1].lower()):
                hwnd = wins[0][0]; break
            time.sleep(.5)
        if hwnd is None:
            raise RuntimeError('owned Edge window did not appear')
        time.sleep(3)                                   # let the page finish drawing
        yield hwnd
    finally:
        procs = owned()
        for p in procs:
            try: p.terminate()
            except psutil.NoSuchProcess: pass
        _, alive = psutil.wait_procs(procs, timeout=5)
        for p in alive:
            try: p.kill()
            except psutil.NoSuchProcess: pass
        time.sleep(1)
        shutil.rmtree(folder, ignore_errors=True)
