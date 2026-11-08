"""The island at the top of the screen. Drawn with Pillow into a per-pixel see-through Windows window: smooth edges, the empty
parts let clicks through, no taskbar button, never takes focus. Only draws while something moves, so idle costs nothing."""
import ctypes
import math
import os
import threading
import time
from ctypes import wintypes as wt

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ACCENT, AMBER, GREY = (95, 212, 255), (255, 181, 71), (196, 205, 216)
BODY = (0, 0, 0)
LW, LH = 620, 480  # most the window can be, in screen points; it only takes the height the island needs
SHOWN = 5  # rows the opened pill shows at once; the mouse wheel moves through the rest
SIZES = {"idle": (118, 34), "starting": (170, 40), "listening": (250, 46), "thinking": (170, 40), "timer": (214, 44), "alert": (300, 52)}
FONTS = (r"C:\Windows\Fonts\SegUIVar.ttf", r"C:\Windows\Fonts\segoeui.ttf")

u32, gdi = ctypes.windll.user32, ctypes.windll.gdi32
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM)
u32.DefWindowProcW.argtypes = [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
u32.DefWindowProcW.restype = ctypes.c_ssize_t
u32.CreateWindowExW.restype = wt.HWND
u32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID]
u32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.c_void_p, ctypes.c_void_p, wt.HDC, ctypes.c_void_p, wt.COLORREF, ctypes.c_void_p, wt.DWORD]
u32.GetDC.restype = wt.HDC
u32.GetDC.argtypes = [wt.HWND]
u32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
u32.GetForegroundWindow.restype = wt.HWND
u32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
u32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
gdi.CreateCompatibleDC.restype = wt.HDC
gdi.CreateCompatibleDC.argtypes = [wt.HDC]
gdi.SelectObject.argtypes = [wt.HDC, ctypes.c_void_p]
gdi.SelectObject.restype = ctypes.c_void_p
gdi.CreateDIBSection.restype = ctypes.c_void_p
gdi.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]


class WNDCLASS(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("proc", WNDPROC), ("extra", ctypes.c_int), ("wnd", ctypes.c_int), ("inst", wt.HINSTANCE), ("icon", wt.HICON),
                ("cursor", wt.HANDLE), ("brush", wt.HBRUSH), ("menu", wt.LPCWSTR), ("name", wt.LPCWSTR)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("size", wt.DWORD), ("w", wt.LONG), ("h", wt.LONG), ("planes", wt.WORD), ("bits", wt.WORD), ("comp", wt.DWORD), ("img", wt.DWORD),
                ("xp", wt.LONG), ("yp", wt.LONG), ("used", wt.DWORD), ("imp", wt.DWORD)]


class BLEND(ctypes.Structure):
    _fields_ = [("op", ctypes.c_byte), ("flags", ctypes.c_byte), ("alpha", ctypes.c_ubyte), ("fmt", ctypes.c_byte)]


def is_fullscreen(cls, style, rect, screen):
    """A video or game really filling the screen. Not the desktop itself (also screen-sized), not a maximised window (it has a title bar)."""
    left, top, right, bottom = rect
    return cls not in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd") and not style & 0xC00000 and left <= 0 and top <= 0 and right >= screen[0] and bottom >= screen[1]


def fit(text, font, width):
    if font.getlength(text) <= width:
        return text
    while text and font.getlength(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


class Island:
    def __init__(self, on_action=None, theme=None):
        self.paper = theme == "paper"
        self.body = (243, 240, 232) if self.paper else BODY
        self.accent = (40, 82, 150) if self.paper else ACCENT
        self.ink = (28, 35, 40, 255) if self.paper else (255, 255, 255, 255)
        self.grey = (88, 97, 106) if self.paper else GREY
        self.on_action = on_action  # gets "main", ("timer", (what, id)), ("reminder", (what, id))
        self.expanded, self._until, self.hits, self.panel, self.scroll = False, 0.0, [], {"timers": [], "reminders": []}, 0
        self.mode, self.text, self.timer, self.level, self.dim = "idle", "", None, 0.0, False
        self.hidden = False
        self.frames = 0  # how many frames were drawn: a check that idle really draws nothing
        self._dirty = threading.Event()
        self.hwnd = None
        threading.Thread(target=self._run, daemon=True).start()

    # ---- what the app calls, from any thread ----
    def set_theme(self, theme):
        self.paper = theme == 'paper'
        self.body = (243, 240, 232) if self.paper else (23, 25, 29)
        self.accent = (40, 82, 150) if self.paper else (169, 198, 255)
        self.ink = (28, 35, 40, 255) if self.paper else (243, 240, 232, 255)
        self.grey = (88, 97, 106) if self.paper else (179, 186, 196)
        self._dirty.set()

    def show(self, mode, text="", timer=None, dim=False):
        """mode: idle|listening|thinking|speaking|timer|alert. timer = (label, left, total)."""
        if (mode, text, timer, dim) != (self.mode, self.text, self.timer, self.dim):
            if mode != self.mode or text != self.text:
                self._born = time.perf_counter()
            if mode not in ("idle", "timer"):
                self.expanded = False  # something is happening: that comes first
            self.mode, self.text, self.timer, self.dim = mode, text, timer, dim
            self._dirty.set()

    def set_panel(self, timers, reminders):
        """What the opened island lists. timers: [{id, name, left, total, on}], reminders: [{id, text, when}]."""
        new = {"timers": timers, "reminders": reminders}
        if new != self.panel:
            self.panel = new
            if self.expanded:
                self._dirty.set()

    def _click(self, x, y):
        if self.expanded:
            for x0, y0, x1, y1, action in self.hits:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    self._until = time.perf_counter() + 12
                    if action == "main":
                        self.expanded = False
                    self.on_action and self.on_action(action)
                    self._dirty.set()
                    return
            self.expanded = False
        elif self.mode == "alert":
            self.on_action and self.on_action("main")
        else:
            self.expanded, self._until, self.scroll = True, time.perf_counter() + 12, 0
        self._born = time.perf_counter()
        self._dirty.set()

    def _rows(self):
        """Everything the opened pill lists: all the timers, then all the reminders."""
        return ([("t", t) for t in self.panel["timers"]] or [("n", "No timers running")]) + ([("r", r) for r in self.panel["reminders"]] or [("n", "No reminders coming up")])

    def _wheel(self, delta):
        if self.expanded:
            self.scroll = max(0, min(max(0, len(self._rows()) - SHOWN), self.scroll + (-1 if delta > 0 else 1)))
            self._until = time.perf_counter() + 12
            self._dirty.set()

    def set_hidden(self, hidden):
        self.hidden = hidden
        self._dirty.set()

    # ---- drawing ----
    def _font(self, pts):
        k = round(pts * self.s)
        if k not in self._fonts:
            for f in FONTS:
                if os.path.exists(f):
                    self._fonts[k] = ImageFont.truetype(f, k)
                    break
            else:
                self._fonts[k] = ImageFont.load_default(k)
        return self._fonts[k]

    def _wrap(self, text, font, width, lines=3):
        out, cur = [], ""
        for word in " ".join(text.split()).split(" "):
            t = (cur + " " + word).strip()
            if font.getlength(t) <= width:
                cur = t
            else:
                out.append(cur)
                cur = word
                if len(out) == lines:
                    break
        else:
            out.append(cur)
            return out
        out[-1] = out[-1].rstrip(" .,") + "…"
        return out

    def _target(self):
        if self.expanded:
            rows = self._rows()
            self.scroll = min(self.scroll, max(0, len(rows) - SHOWN))
            return (440, 58 + sum(52 for _ in rows[self.scroll:self.scroll + SHOWN]) + (26 if len(rows) > SHOWN else 8) + 8)
        if self.mode == "speaking":
            lines = self._wrap(self.text, self._font(15), 400 * self.s)
            self._lines = lines
            width = max(self._font(15).getlength(x) for x in lines) / self.s + 52
            return (max(200, min(460, width)), 50 + 22 * len(lines))
        if self.mode == "alert":
            width = self._font(14).getlength(self.text) / self.s + 76
            return (max(220, min(520, width)), 52)
        return SIZES[self.mode]

    def _draw(self, w, h, now):
        s, cw = self.s, self.W // 2
        W, H = round(w * s), round(h * s)
        rows = min(self.H, round((8 + h) * s) + 6)  # only as tall as needed: smaller, faster, and clicks below go to whatever is there
        if W < 4 or H < 4:
            return np.zeros((rows, self.W, 4), dtype=np.uint8)
        k = 3  # draw big, shrink: smooth corners
        mask = Image.new("L", (W * k, H * k), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, W * k - 1, H * k - 1), radius=min(H, round(self._radius(h) * s)) * k, fill=255)
        mask = mask.resize((W, H), Image.LANCZOS)
        img = Image.new("RGBA", (self.W, rows), (0, 0, 0, 0))
        x0, y0 = cw - W // 2, round(8 * s)
        self._origin = (x0, y0)
        self._box = (x0, y0, x0 + W, y0 + H)
        img.paste(Image.new("RGBA", (W, H), (*self.body, 255)), (x0, y0), mask)
        fade = min(1.0, (now - getattr(self, "_born", 0) - 0.08) / 0.2)
        if fade > 0:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            self._content(ImageDraw.Draw(layer), layer, W, H, now)
            a = np.array(layer, dtype=np.uint8)
            a[..., 3] = (a[..., 3] * fade * (np.array(mask) / 255)).astype(np.uint8)
            piece = Image.fromarray(a, "RGBA")
            img.alpha_composite(piece, (x0, y0))
        return np.array(img, dtype=np.uint8)

    def _radius(self, h):
        return min(h / 2, 28)

    def _button(self, d, x, y, kind, action):
        """A small round button, centred at (x, y), that really takes clicks."""
        s, c, r = self.s, (*self.grey, 255), 15 * self.s
        d.ellipse((x - r, y - r, x + r, y + r), fill=(232, 233, 226, 255) if self.paper else (38, 42, 48, 255))
        k, w = 5 * s, max(1, round(1.6 * s))
        if kind == "x":
            d.line((x - k, y - k, x + k, y + k), fill=c, width=w); d.line((x - k, y + k, x + k, y - k), fill=c, width=w)
        elif kind == "pause":
            d.rectangle((x - k, y - k, x - k * 0.3, y + k), fill=c); d.rectangle((x + k * 0.3, y - k, x + k, y + k), fill=c)
        elif kind == "play":
            d.polygon([(x - k * 0.7, y - k), (x + k, y), (x - k * 0.7, y + k)], fill=c)
        elif kind == "done":
            d.line((x - k, y, x - k * 0.2, y + k * 0.8, x + k, y - k * 0.8), fill=c, width=w, joint="curve")
        ox, oy = self._origin
        self.hits.append((ox + x - r - 3 * s, oy + y - r - 3 * s, ox + x + r + 3 * s, oy + y + r + 3 * s, action))

    def _panel(self, d, layer, W, H):
        s, white, grey = self.s, self.ink, (*self.grey, 255)
        self.hits, pad = [], 22 * s
        self._aa_dot(layer, pad + 4 * s, 28 * s, 4 * s, self.accent)
        d.text((pad + 16 * s, 28 * s), "Jarvis", font=self._font(14), fill=white, anchor="lm")
        bw = 118 * s
        d.rounded_rectangle((W - pad - bw, 14 * s, W - pad, 42 * s), radius=14 * s, fill=(232, 233, 226, 255) if self.paper else (38, 42, 48, 255))
        d.text((W - pad - bw / 2, 28 * s), "Open window", font=self._font(12), fill=white, anchor="mm")
        ox, oy = self._origin
        self.hits.append((ox + W - pad - bw, oy + 10 * s, ox + W - pad, oy + 46 * s, "main"))
        y = 58 * s
        rows = self._rows()
        for kind, x in rows[self.scroll:self.scroll + SHOWN]:
            cy = y + 26 * s
            if kind == "t":
                left = x["left"]
                self._ring(layer, pad + 12 * s, cy, 11 * s, left / max(1, x["total"]))
                clock = f"{left // 3600}:{left % 3600 // 60:02d}:{left % 60:02d}" if left >= 3600 else f"{left // 60:02d}:{left % 60:02d}"
                d.text((W - pad - 76 * s, cy), clock, font=self._font(16), fill=(*AMBER, 255) if x["on"] else (*self.grey, 255), anchor="rm")
                d.text((pad + 34 * s, cy), fit(x["name"], self._font(13), W - pad * 2 - 170 * s), font=self._font(13), fill=white, anchor="lm")
                self._button(d, W - pad - 52 * s, cy, "pause" if x["on"] else "play", ("timer", ("toggle", x["id"])))
                self._button(d, W - pad - 14 * s, cy, "x", ("timer", ("delete", x["id"])))
            elif kind == "r":
                d.line((pad, y, W - pad, y), fill=(38, 42, 48, 255), width=1)
                d.text((pad, cy - 9 * s), fit(x["text"], self._font(13), W - pad * 2 - 90 * s), font=self._font(13), fill=white, anchor="lm")
                d.text((pad, cy + 9 * s), x["when"], font=self._font(11), fill=grey, anchor="lm")
                self._button(d, W - pad - 52 * s, cy, "done", ("reminder", ("done", x["id"])))
                self._button(d, W - pad - 14 * s, cy, "x", ("reminder", ("delete", x["id"])))
            else:
                d.text((pad, cy), x, font=self._font(13), fill=grey, anchor="lm")
            y += 52 * s
        if len(rows) > SHOWN:
            more = len(rows) - SHOWN - self.scroll
            d.text((W / 2, y + 12 * s), f"Scroll for {more} more" if more else "Scroll up for the rest", font=self._font(11), fill=grey, anchor="mm")

    def _content(self, d, layer, W, H, now):
        s, m = self.s, self.mode
        white = self.ink
        cy = H / 2
        if self.expanded:
            self._panel(d, layer, W, H)
        elif m == "idle":
            dot = (100, 110, 122) if self.dim else self.accent
            label = "Mic off" if self.dim else "Jarvis"
            tw = self._font(13).getlength(label)
            x = (W - tw - 16 * s) / 2
            r = 4 * s
            self._aa_dot(layer, x + r, cy, r, dot)
            d.text((x + 16 * s, cy), label, font=self._font(13), fill=white, anchor="lm")
        elif m == "listening":
            d.text((22 * s, cy), "Listening", font=self._font(14), fill=white, anchor="lm")
            n = 9
            for i in range(n):
                wob = 0.5 + 0.5 * math.sin(now * 7 + i * 0.9)
                amp = max(0.16, min(1.0, 0.18 + self.level * 1.6)) * (0.45 + 0.55 * wob)
                bh = max(3 * s, 22 * s * amp)
                x = W - (22 + (n - 1 - i) * 7) * s
                d.rounded_rectangle((x - 1.5 * s, cy - bh / 2, x + 1.5 * s, cy + bh / 2), radius=1.5 * s, fill=(*self.accent, 255))
        elif m in ("thinking", "starting"):
            for i in range(3):
                v = 0.5 + 0.5 * math.sin(now * 6 - i * 0.8)
                self._aa_dot(layer, (24 + i * 13) * s, cy, (2.4 + 1.6 * v) * s, tuple(int(c * (0.45 + 0.55 * v)) for c in self.accent))
            d.text((70 * s, cy), m.title(), font=self._font(13), fill=(*self.grey, 255), anchor="lm")
        elif m == "speaking":
            d.text((26 * s, 14 * s), "Jarvis", font=self._font(12), fill=(*self.accent, 255), anchor="lt")
            for i, line in enumerate(getattr(self, "_lines", [])):
                d.text((26 * s, (34 + i * 22) * s), line, font=self._font(15), fill=white, anchor="lt")
        elif m == "timer" and self.timer:
            label, left, total = self.timer
            self._ring(layer, 26 * s, cy, 10.5 * s, left / max(1, total))
            d.text((46 * s, cy), label, font=self._font(13), fill=(*self.grey, 255), anchor="lm")
            d.text((W - 18 * s, cy), f"{left // 3600}:{left % 3600 // 60:02d}:{left % 60:02d}" if left >= 3600 else f"{left // 60:02d}:{left % 60:02d}",
                   font=self._font(16), fill=(*AMBER, 255), anchor="rm")
        elif m == "alert":
            v = 0.5 + 0.5 * math.sin(now * 5)
            self._aa_dot(layer, 28 * s, cy, (6 + 3 * v) * s, AMBER)
            d.text((48 * s, cy), self.text, font=self._font(14), fill=white, anchor="lm")

    def _aa_dot(self, layer, x, y, r, color):
        k, size = 4, int(r * 2 + 4)
        if size < 3:
            return
        m = Image.new("L", (size * k, size * k), 0)
        c = size * k / 2
        ImageDraw.Draw(m).ellipse((c - r * k, c - r * k, c + r * k, c + r * k), fill=255)
        m = m.resize((size, size), Image.LANCZOS)
        layer.paste(Image.new("RGBA", (size, size), (*color, 255)), (round(x - size / 2), round(y - size / 2)), m)

    def _ring(self, layer, x, y, r, frac):
        k, size = 4, int(r * 2 + 6)
        m1 = Image.new("L", (size * k, size * k), 0)
        m2 = Image.new("L", (size * k, size * k), 0)
        c, wd = size * k / 2, round(2.6 * self.s * k)
        box = (c - r * k, c - r * k, c + r * k, c + r * k)
        ImageDraw.Draw(m1).arc(box, 0, 360, fill=255, width=wd)
        ImageDraw.Draw(m2).arc(box, -90, -90 + 360 * frac, fill=255, width=wd)
        pos = (round(x - size / 2), round(y - size / 2))
        layer.paste(Image.new("RGBA", (size, size), (58, 58, 58, 255)), pos, m1.resize((size, size), Image.LANCZOS))
        layer.paste(Image.new("RGBA", (size, size), (*AMBER, 255)), pos, m2.resize((size, size), Image.LANCZOS))

    def _blit(self, arr):
        rgb = arr[..., :3].astype(np.uint16) * arr[..., 3:4] // 255  # Windows wants colours already multiplied by see-through-ness
        rows = arr.shape[0]
        out = np.dstack((rgb[..., 2], rgb[..., 1], rgb[..., 0], arr[..., 3])).astype(np.uint8)
        ctypes.memmove(self._bits, out.tobytes(), out.size)
        size, src, blend = wt.SIZE(self.W, rows), wt.POINT(0, 0), BLEND(0, 0, 255, 1)
        u32.UpdateLayeredWindow(self.hwnd, self._screen, None, ctypes.byref(size), self._dc, ctypes.byref(src), 0, ctypes.byref(blend), 2)
        self.frames += 1

    # ---- the window's own thread ----
    def _run(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except OSError:
            pass
        try:
            self.s = u32.GetDpiForSystem() / 96
        except AttributeError:
            self.s = 1.0
        self._fonts = {}
        self.W, self.H = round(LW * self.s), round(LH * self.s)
        sw = u32.GetSystemMetrics(0)

        def proc(h, msg, wp, lp):
            if msg == 0x0202:  # left button up
                self._click(lp & 0xFFFF, (lp >> 16) & 0xFFFF)
                return 0
            if msg == 0x020A:  # mouse wheel
                self._wheel(ctypes.c_short((wp >> 16) & 0xFFFF).value)
                return 0
            if msg == 0x10:  # asked to close: the island only ever closes along with the whole app
                return 0
            return u32.DefWindowProcW(h, msg, wp, lp)
        self._proc = WNDPROC(proc)  # keep it alive
        inst = ctypes.windll.kernel32.GetModuleHandleW(None)
        wc = WNDCLASS(0, self._proc, 0, 0, inst, None, u32.LoadCursorW(None, 32649), None, None, "JarvisIsland")
        u32.RegisterClassW(ctypes.byref(wc))
        # layered | always on top | no taskbar button | never takes the keyboard
        self.hwnd = u32.CreateWindowExW(0x80000 | 0x8 | 0x80 | 0x8000000, "JarvisIsland", "Jarvis island", 0x80000000, (sw - self.W) // 2, 0, self.W, self.H, None, None, inst, None)
        self._screen = u32.GetDC(None)
        self._dc = gdi.CreateCompatibleDC(self._screen)
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), self.W, -self.H, 1, 32, 0, 0, 0, 0, 0, 0)
        self._bits = ctypes.c_void_p()
        gdi.SelectObject(self._dc, gdi.CreateDIBSection(self._screen, ctypes.byref(bi), 0, ctypes.byref(self._bits), None, 0))
        u32.ShowWindow(self.hwnd, 8)  # show without taking focus
        w, h = 8.0, 8.0  # starts as a speck and springs open
        vw, vh = 0.0, 0.0
        msg, last, shown_hidden, check, was_down = wt.MSG(), time.perf_counter(), False, 0.0, False
        self._dirty.set()
        while True:
            while u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                u32.TranslateMessage(ctypes.byref(msg))
                u32.DispatchMessageW(ctypes.byref(msg))
            now = time.perf_counter()
            dt, last = min(0.05, now - last), now
            if self.expanded:
                down = bool(u32.GetAsyncKeyState(1) & 0x8000)  # a click anywhere else on the screen closes it, like clicking away from a menu
                if down and not was_down and not self._inside():
                    self._until = 0
                was_down = down
                if now > self._until:
                    self.expanded = False
                    self._born = now
            if now > check:  # a full-screen video or game: a small idle pill must not sit on top of it
                check = now + 1
                hide = self.hidden or (self.mode in ("idle", "timer") and not self.expanded and self._fullscreen(sw))
                if hide != shown_hidden:
                    shown_hidden = hide
                    u32.ShowWindow(self.hwnd, 0 if hide else 8)
                    self._dirty.set()
            if shown_hidden:
                self._dirty.wait(0.25)
                self._dirty.clear()
                continue
            tw, th = self._target()
            ax, ay = 230 * (tw - w) - 24 * vw, 260 * (th - h) - 26 * vh  # a spring, slightly under-damped: the bounce
            vw, vh = vw + ax * dt, vh + ay * dt
            w, h = max(4, w + vw * dt), max(4, h + vh * dt)
            settled = abs(tw - w) < 0.3 and abs(th - h) < 0.3 and abs(vw) < 2 and abs(vh) < 2
            live = self.mode in ("listening", "thinking", "starting", "alert")
            fading = now - getattr(self, "_born", 0) < 0.4
            if not settled or live or fading or self._dirty.is_set():
                self._dirty.clear()
                if settled:
                    w, h, vw, vh = tw, th, 0.0, 0.0
                self._blit(self._draw(w, h, now))
                time.sleep(0.016 if not settled or fading else 0.033)
            else:
                self._dirty.wait(0.03 if self.expanded else 0.25)  # nothing moves: nothing is drawn, the thread sleeps
                self._dirty.clear() if self.expanded and not self._dirty.is_set() else None

    def _inside(self):
        p, r = wt.POINT(), wt.RECT()
        u32.GetCursorPos(ctypes.byref(p))
        u32.GetWindowRect(self.hwnd, ctypes.byref(r))
        x0, y0, x1, y1 = getattr(self, "_box", (0, 0, 0, 0))
        return r.left + x0 <= p.x <= r.left + x1 and r.top + y0 <= p.y <= r.top + y1

    def _fullscreen(self, sw):
        fg = u32.GetForegroundWindow()
        if not fg or fg == self.hwnd:
            return False
        r, c = wt.RECT(), ctypes.create_unicode_buffer(64)
        u32.GetWindowRect(fg, ctypes.byref(r))
        u32.GetClassNameW(fg, c, 64)
        return is_fullscreen(c.value, u32.GetWindowLongW(fg, -16), (r.left, r.top, r.right, r.bottom), (sw, u32.GetSystemMetrics(1)))
