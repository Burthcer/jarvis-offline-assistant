"""Capture one Tk window to a PNG by asking Windows to paint it (PrintWindow), so it works even when the screen is locked."""
import ctypes
from ctypes import wintypes

from PIL import Image

u, g = ctypes.windll.user32, ctypes.windll.gdi32


def grab(tk_window, path, see_through=(1, 2, 3), fill=(120, 130, 150)):
    tk_window.update()
    hwnd = u.GetParent(tk_window.winfo_id()) or tk_window.winfo_id()
    w, h = tk_window.winfo_width(), tk_window.winfo_height()
    dc = g.CreateCompatibleDC(0)
    hdc = u.GetDC(0)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(dc, bmp)
    u.PrintWindow(hwnd, dc, 2)  # 2 = render full content
    class BIH(ctypes.Structure):
        _fields_ = [("s", wintypes.DWORD), ("w", wintypes.LONG), ("h", wintypes.LONG), ("p", wintypes.WORD), ("b", wintypes.WORD),
                    ("c", wintypes.DWORD), ("si", wintypes.DWORD), ("x", wintypes.LONG), ("y", wintypes.LONG), ("u", wintypes.DWORD), ("i", wintypes.DWORD)]
    bi = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(dc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    px = img.load()
    for y in range(h):  # show the see-through colour as a flat grey so the pill is visible
        for x in range(w):
            if px[x, y] == see_through:
                px[x, y] = fill
    img.save(path)
    g.DeleteObject(bmp); g.DeleteDC(dc); u.ReleaseDC(0, hdc)
