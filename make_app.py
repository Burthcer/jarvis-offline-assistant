"""Makes Jarvis its own program: data/runtime/Jarvis.exe, a renamed copy of Python's windowless starter with Jarvis's name and icon,
so Task Manager says "Jarvis" instead of "Python". Then points the desktop shortcut at it. Run again after a Python upgrade: py -3.12 make_app.py"""
import ctypes
import os
import shutil
import struct
import subprocess
import sys
from ctypes import wintypes as wt

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPT = "Jarvis2.pyw" if "--v2" in sys.argv else "Jarvis.pyw"      # --v2: the desktop icon starts Jarvis V2 (only when the owner says switch)
OUT = os.path.join(ROOT, "data", "runtime")
EXE = os.path.join(OUT, "Jarvis.exe")
ICON_FILE = os.path.join(ROOT, 'jarvis-paper.ico')
if not os.path.exists(ICON_FILE):
    ICON_FILE = os.path.join(ROOT, 'jarvis.ico')
HOME = sys.base_prefix
k = ctypes.WinDLL("kernel32", use_last_error=True)
k.BeginUpdateResourceW.restype = wt.HANDLE
k.BeginUpdateResourceW.argtypes = [wt.LPCWSTR, wt.BOOL]
k.UpdateResourceW.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, wt.WORD, ctypes.c_void_p, wt.DWORD]
k.UpdateResourceW.restype = wt.BOOL
k.EndUpdateResourceW.argtypes = [wt.HANDLE, wt.BOOL]


def strip_signature(path):
    """Python's signature would no longer match the edited copy, and Windows refuses to edit a signed file."""
    with open(path, "r+b") as f:
        d = f.read()
        pe = struct.unpack("<I", d[0x3C:0x40])[0]
        magic = struct.unpack("<H", d[pe + 24:pe + 26])[0]
        entry = pe + 24 + (112 if magic == 0x20B else 96) + 4 * 8  # data directory 4: the certificate
        off, size = struct.unpack("<II", d[entry:entry + 8])
        if off:
            f.seek(entry)
            f.write(b"\0" * 8)
            f.truncate(off)


def set_name(path):
    """Task Manager shows the name stored inside the file. 'Python' and 'Jarvis' are the same length, so it can simply be overwritten."""
    with open(path, "rb") as f:
        d = f.read()
    n = 0
    for key in ("FileDescription", "ProductName"):
        at = d.find(key.encode("utf-16-le"))
        while at != -1:
            i = d.find("Python".encode("utf-16-le"), at, at + 200)
            if i != -1:
                d = d[:i] + "Jarvis".encode("utf-16-le") + d[i + 12:]
                n += 1
            at = d.find(key.encode("utf-16-le"), at + 2)
    if not n:
        raise OSError("name not found in the program file")
    with open(path, "wb") as f:
        f.write(d)


def set_icon(path, ico):
    """Windows' own resource editor. Not essential: if it refuses, Jarvis.exe just keeps Python's icon in Task Manager."""
    h = k.BeginUpdateResourceW(path, False)
    if not h:
        raise ctypes.WinError(ctypes.get_last_error())
    data = open(ico, "rb").read()
    n = struct.unpack("<H", data[4:6])[0]
    group = struct.pack("<HHH", 0, 1, n)
    for i in range(n):
        e = data[6 + i * 16:22 + i * 16]
        size, off = struct.unpack("<II", e[8:16])
        if not k.UpdateResourceW(h, 3, 200 + i, 1033, data[off:off + size], size):
            k.EndUpdateResourceW(h, True)
            raise ctypes.WinError(ctypes.get_last_error())
        group += e[:12] + struct.pack("<H", 200 + i)
    if not k.UpdateResourceW(h, 14, 1, 1033, group, len(group)):
        k.EndUpdateResourceW(h, True)
        raise ctypes.WinError(ctypes.get_last_error())
    if not k.EndUpdateResourceW(h, False):
        print("icon left as it was:", ctypes.WinError(ctypes.get_last_error()))


os.makedirs(OUT, exist_ok=True)
shutil.copy2(os.path.join(HOME, "pythonw.exe"), EXE)
for dll in ("python3.dll", f"python{sys.version_info.major}{sys.version_info.minor}.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
    shutil.copy2(os.path.join(HOME, dll), OUT)
with open(os.path.join(OUT, "pyvenv.cfg"), "w", encoding="utf-8") as f:
    f.write(f"home = {HOME}\ninclude-system-site-packages = true\nversion = {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n")
strip_signature(EXE)
set_name(EXE)
set_icon(EXE, ICON_FILE)
check = subprocess.run([EXE, "-c", "import sys,webview,numpy,faster_whisper;open(sys.argv[1],'w').write(sys.executable)", os.path.join(OUT, "ok.txt")], timeout=120, check=True)
print("runs:", open(os.path.join(OUT, "ok.txt")).read())
os.remove(os.path.join(OUT, "ok.txt"))
backup = os.path.join(ROOT, 'data', 'shortcut-backup')
os.makedirs(backup, exist_ok=True)
ps = ("$shortcut=[Environment]::GetFolderPath('Desktop')+'\\Jarvis.lnk';"
      f"if((Test-Path -LiteralPath $shortcut) -and -not (Test-Path -LiteralPath '{os.path.join(backup, 'Jarvis.lnk')}')){{Copy-Item -LiteralPath $shortcut -Destination '{os.path.join(backup, 'Jarvis.lnk')}'}};"
      "$l=(New-Object -ComObject WScript.Shell).CreateShortcut($shortcut);"
      f"$l.TargetPath='{EXE}';$l.Arguments='\"{os.path.join(ROOT, SCRIPT)}\"';$l.WorkingDirectory='{ROOT}';$l.IconLocation='{ICON_FILE},0';$l.Description='Jarvis offline assistant';$l.Save()")
subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
print("desktop shortcut now starts", EXE)
