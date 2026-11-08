"""Write text to the Windows clipboard. Never pastes into another app."""
import ctypes
from ctypes import wintypes as wt
import time


def write(text):
    if '\0' in str(text):
        return False
    u, k = ctypes.windll.user32, ctypes.windll.kernel32
    k.GlobalAlloc.restype = k.GlobalLock.restype = ctypes.c_void_p
    k.GlobalLock.argtypes = k.GlobalUnlock.argtypes = k.GlobalFree.argtypes = [ctypes.c_void_p]
    k.GlobalSize.argtypes = [ctypes.c_void_p]
    k.GlobalSize.restype = ctypes.c_size_t
    u.GetClipboardData.argtypes = [ctypes.c_uint]
    u.GetClipboardData.restype = ctypes.c_void_p
    u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    u.SetClipboardData.restype = ctypes.c_void_p
    u.CreateWindowExW.argtypes = [wt.DWORD,wt.LPCWSTR,wt.LPCWSTR,wt.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wt.HWND,wt.HMENU,wt.HINSTANCE,ctypes.c_void_p]
    u.CreateWindowExW.restype = wt.HWND
    u.DestroyWindow.argtypes = [wt.HWND]
    u.OpenClipboard.argtypes = [wt.HWND]
    # A private message-only window owns the clipboard operation. Opening with
    # NULL and then EmptyClipboard leaves no owner for SetClipboardData.
    owner = u.CreateWindowExW(0, 'STATIC', 'Jarvis clipboard', 0, 0, 0, 0, 0, wt.HWND(-3), None, None, None)
    if not owner:
        return False
    data = (str(text) + '\0').encode('utf-16-le')
    handle = k.GlobalAlloc(2, len(data))
    if not handle:
        u.DestroyWindow(owner)
        return False
    transferred = False
    try:
        ptr = k.GlobalLock(handle)
        if not ptr:
            return False
        ctypes.memmove(ptr, data, len(data))
        k.GlobalUnlock(handle)
        for _ in range(20):
            if u.OpenClipboard(owner):
                try:
                    if u.EmptyClipboard():
                        transferred = bool(u.SetClipboardData(13, handle))
                    if not transferred:
                        return False
                    # Read back only the data we just wrote while the clipboard
                    # is still locked. Success means the exact requested value.
                    copied = u.GetClipboardData(13)
                    if not copied or k.GlobalSize(copied) < len(data):
                        return False
                    read = k.GlobalLock(copied)
                    if not read:
                        return False
                    try:
                        return ctypes.string_at(read,len(data)) == data
                    finally:
                        k.GlobalUnlock(copied)
                finally:
                    u.CloseClipboard()
            time.sleep(.01)
        return False
    finally:
        if not transferred:
            k.GlobalFree(handle)
        u.DestroyWindow(owner)
