"""V3 settings redirect only the PRIVATE compatibility module.
Never imports or changes the live V1/V2 settings. Startup uses Jarvis4.
Learning shares this V3 file, so saving merges keys rather than replacing them.
"""
import json
import os
import sys

from jarvis3.legacy import settings as S

from jarvis3.paths import RUNTIME, PROJECT, ASSETS
ROOT = str(RUNTIME)
from jarvis3.paths import DATA, PROJECT
PATH = str(DATA / "settings3.json")
S.PATH = PATH


def save(cfg):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    try:
        cur = json.load(open(PATH, encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    cur.update(cfg)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(cur, f, indent=2)


def set_autostart(on):
    import winreg
    cmd = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{str(PROJECT / "Jarvis4.pyw")}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, S.RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "Jarvis4", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, "Jarvis4")
            except FileNotFoundError:
                pass


S.save, S.set_autostart = save, set_autostart
