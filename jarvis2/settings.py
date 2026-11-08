"""V2 keeps its settings in data/settings2.json (V1's stay in settings.json). The window's code is V1's, so this module re-points V1's settings module at the new file:
same keys, same page. The file also holds learning_paused (Memory writes that one key), so saving merges instead of replacing. Start with Windows starts V2, not V1."""
import json
import os
import sys

from jarvis import settings as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join("data", "settings2.json")
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
    cmd = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{os.path.join(ROOT, "Jarvis2.pyw")}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, S.RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "Jarvis2", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, "Jarvis2")
            except FileNotFoundError:
                pass


S.save, S.set_autostart = save, set_autostart
