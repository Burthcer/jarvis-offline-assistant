"""Only changes window state. No close messages, keys or process termination."""
import ctypes
from ctypes import wintypes as wt
import time

def change(hwnd, action):
    u = ctypes.windll.user32
    for name in ('IsWindow','IsIconic','IsZoomed'):
        getattr(u,name).argtypes = [wt.HWND]
    u.ShowWindowAsync.argtypes = [wt.HWND, ctypes.c_int]
    if action not in ('minimize','maximize','restore') or not u.IsWindow(hwnd):
        return False
    # SW_RESTORE (9) can restore a minimised maximised window back to maximised.
    # The explicit "restore" action here means normal size, so use SHOWNORMAL.
    u.ShowWindowAsync(hwnd, {'minimize':6,'maximize':3,'restore':1}[action])
    end = time.monotonic() + .6
    while u.IsWindow(hwnd):
        iconic, zoomed = bool(u.IsIconic(hwnd)), bool(u.IsZoomed(hwnd))
        if {'minimize':iconic, 'maximize':zoomed and not iconic, 'restore':not iconic and not zoomed}[action]:
            return True
        if time.monotonic() >= end:
            break
        time.sleep(.015)
    return False
