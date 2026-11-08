"""Settings saved in data/settings.json (local only). load() -> dict, save(dict), apply(dict)."""
import json
import os
import sys

from . import actions

PATH = os.path.join("data", "settings.json")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULTS = {
    "wake_replies": ["At your service, sir", "Yes, sir", "I'm listening, sir"],
    "browsers": {k: v[0] for k, v in actions.SITES.items()},
    "start_with_windows": False,
    "tts_volume": 1.0,  # Jarvis's own speaking volume 0.2-1.0 (1.0 = loudest)
    "tts_speed": 1.0,  # 0.6-1.6
    "voice_on": True,  # microphone listening for the wake word
    "speak_replies": True,
    "natural_replies": True,  # the AI words each reply itself; off = fixed sentences, which start a little sooner
    "tts_voice": "jarvis",  # see voice.VOICES
    "theme": "light",
    "quiet_enabled":False,"quiet_start":"22:00","quiet_end":"07:00","cool_mode":False,"daily_briefing":False,"save_voice_clips":False,
}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load():
    cfg = json.loads(json.dumps(DEFAULTS))
    try:
        with open(PATH, encoding="utf-8") as f:
            saved = json.load(f)
        cfg["wake_replies"] = [x for x in saved.get("wake_replies", []) if isinstance(x, str) and x.strip()] or cfg["wake_replies"]
        cfg["browsers"].update({k: v for k, v in saved.get("browsers", {}).items() if k in cfg["browsers"] and v in ("edge", "chrome")})
        cfg["start_with_windows"] = bool(saved.get("start_with_windows", False))
        for k, lo, hi in (("tts_volume", 0.2, 1.0), ("tts_speed", 0.6, 1.6)):
            if isinstance(saved.get(k), (int, float)) and not isinstance(saved.get(k), bool):
                cfg[k] = min(hi, max(lo, float(saved[k])))
        from .voice import VOICES
        if saved.get("tts_voice") in VOICES:
            cfg["tts_voice"] = saved["tts_voice"]
        for k in ("voice_on", "speak_replies", "natural_replies"):
            if isinstance(saved.get(k), bool):
                cfg[k] = saved[k]
        if saved.get('theme') in ('light', 'dark'):
            cfg['theme'] = saved['theme']
        import re
        for key in ('quiet_enabled','cool_mode','daily_briefing','save_voice_clips'):
            if isinstance(saved.get(key),bool):cfg[key]=saved[key]
        for key in ('quiet_start','quiet_end'):
            if isinstance(saved.get(key),str) and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',saved[key]):cfg[key]=saved[key]
        if isinstance(saved.get('briefed_on'),str):cfg['briefed_on']=saved['briefed_on']
    except (OSError, ValueError, AttributeError):  # missing or damaged file: fall back to defaults
        pass
    return cfg


def save(cfg):
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def apply(cfg):
    for site, b in cfg["browsers"].items():
        _, home, search = actions.SITES[site]
        actions.SITES[site] = (b, home, search)
    set_autostart(cfg["start_with_windows"])


def set_autostart(on):
    import winreg
    cmd = f'"{sys.executable.replace("python.exe", "pythonw.exe")}" "{os.path.join(ROOT, "Jarvis.pyw")}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "Jarvis", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, "Jarvis")
            except FileNotFoundError:
                pass
