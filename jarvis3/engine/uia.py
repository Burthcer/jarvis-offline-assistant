"""Reading and operating the window in front through Windows' accessibility interface (UI Automation): the same names a screen reader uses, no pictures of the screen.
Hard rails live HERE, under every ability that uses it, so no sentence can get around them:
- windows that look like banking, payments, passwords, logins are never read, typed into or clicked;
- a password field is never read or typed into;
- Jarvis's own windows are never touched;
- keys come from a short allowlist (no Alt+F4, no Windows key, no Delete);
- clicking or sending something irreversible (send, pay, delete...) needs a spoken yes first (the ability asks; see `risky`)."""
import difflib
import re
import time
import threading
_CLIENT_LOCK=threading.Lock()

DENY_WINDOW = re.compile(r"password|passcode|bank|paypal|wallet|otp|credential|log ?in\b|sign ?in\b|upi|netbanking|credit card|cvv|authenticator|keepass|bitwarden|1password|payment|checkout", re.I)
OWN_WINDOW = re.compile(r"^jarvis\b", re.I)
RISKY = re.compile(r"\b(send|submit|post|publish|pay|buy|purchase|order|checkout|confirm|delete|remove|erase|transfer|sign out|log out|logout|uninstall|install|accept|agree|allow|grant|empty|format|reset|share|tweet|reply|forward)\b", re.I)
KEYS = {"enter": "{Enter}", "tab": "{Tab}", "escape": "{Esc}", "esc": "{Esc}", "up": "{Up}", "down": "{Down}", "left": "{Left}", "right": "{Right}", "page down": "{PageDown}", "page up": "{PageUp}",
        "space": "{Space}", "home": "{Home}", "end": "{End}", "copy": "{Ctrl}c", "paste": "{Ctrl}v", "select all": "{Ctrl}a", "find": "{Ctrl}f", "address bar": "{Ctrl}l", "new tab": "{Ctrl}t",
        "next tab": "{Ctrl}{Tab}", "refresh": "{F5}", "back": "{Alt}{Left}", "forward": "{Alt}{Right}", "zoom in": "{Ctrl}={Ctrl}=", "zoom out": "{Ctrl}-{Ctrl}-"}
CLICKABLE = {"ButtonControl", "HyperlinkControl", "MenuItemControl", "TabItemControl", "CheckBoxControl", "RadioButtonControl", "ListItemControl", "TreeItemControl", "SplitButtonControl", "ComboBoxControl"}
READABLE = {"TextControl", "EditControl", "DocumentControl", "ButtonControl", "HyperlinkControl", "ListItemControl", "MenuItemControl", "TabItemControl", "HeaderControl", "TitleBarControl"}
MAX_NODES = 1500


class Refused(Exception):
    """A rail said no. The message is a plain sentence Jarvis can say."""


def _auto():
    import uiautomation as auto
    auto.SetGlobalSearchTimeout(2)
    return auto

def bound_client():
    """Use the Windows 8+ client inside THIS V3 process; no installed files/settings.
    The package's old CUIAutomation instance lacks IUIAutomation2 timeouts.
    Must be called inside an initialised COM thread before creating controls.
    """
    from uiautomation import uiautomation as implementation
    import comtypes.client
    with _CLIENT_LOCK:
        client=implementation._AutomationClient.instance()
        if not getattr(client,'_jarvis_bounded',False):
            enhanced=comtypes.client.CreateObject(client.UIAutomationCore.CUIAutomation8,interface=client.UIAutomationCore.IUIAutomation2)
            enhanced.ConnectionTimeout=500;enhanced.TransactionTimeout=1000
            client.IUIAutomation=enhanced;client.ViewWalker=enhanced.RawViewWalker;client._jarvis_bounded=True


def front_window():
    auto = _auto()
    fg = auto.GetForegroundControl()
    top = fg.GetTopLevelControl() if fg is not None else None
    if top is None:
        raise Refused("I can't see a window in front, sir.")
    title = top.Name or ""
    if OWN_WINDOW.search(title):
        raise Refused("That is my own window, sir. I won't operate it.")
    if DENY_WINDOW.search(title):
        raise Refused("That window looks like a bank, payment or login page. I don't read or operate those, sir.")
    return top


def _walk(win, kinds=None, limit=MAX_NODES):
    """Breadth-first over the window's controls, at most `limit`: web pages and Electron apps have thousands."""
    out, queue, seen = [], [win], 0
    while queue and seen < limit:
        c = queue.pop(0)
        for ch in c.GetChildren():
            seen += 1
            if seen > limit:
                break
            if kinds is None or ch.ControlTypeName in kinds:
                out.append(ch)
            queue.append(ch)
    return out


def read_window(win=None, limit_chars=3500):
    """The visible text of the window in front: titles, labels, buttons, page text. Password fields are skipped."""
    win = win or front_window()
    parts, size = [win.Name or ""], 0
    for c in _walk(win, READABLE):
        try:
            if c.ControlTypeName == "EditControl" and getattr(c, "IsPassword", False):
                continue
            t = (c.Name or "").strip()
            if c.ControlTypeName in ("EditControl", "DocumentControl"):
                try:
                    t = (c.GetValuePattern().Value or t).strip()
                except Exception:
                    pass
        except Exception:
            continue
        if t and t not in parts[-3:]:
            parts.append(t)
            size += len(t)
            if size > limit_chars:
                break
    return "\n".join(parts)[:limit_chars]


def find(name, win=None):
    """The clickable control whose name is closest to `name`. Returns (control, its name) or raises Refused."""
    win = win or front_window()
    want = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    best, score = None, 0.0
    for c in _walk(win, CLICKABLE):
        n = re.sub(r"[^a-z0-9 ]", "", (c.Name or "").lower()).strip()
        if not n:
            continue
        sc = 1.0 if n == want else 0.9 if want in n or n in want else difflib.SequenceMatcher(None, want, n).ratio()
        if sc > score:
            best, score = c, sc
    if best is None or score < 0.75:
        raise Refused(f"I can't find '{name}' in that window, sir.")
    return best, best.Name


def risky(label):
    return bool(RISKY.search(label or ""))


def click(name):
    ctrl, label = find(name)
    try:
        ctrl.GetInvokePattern().Invoke()
    except Exception:
        ctrl.Click(simulateMove=False)
    return label


def type_text(text):
    auto = _auto()
    front_window()                                                       # the rails again: not a bank, not Jarvis itself
    focus = auto.GetFocusedControl()
    if focus is not None and focus.ControlTypeName == "EditControl" and getattr(focus, "IsPassword", False):
        raise Refused("That is a password field. I never type into those, sir.")
    if len(text) > 600:
        raise Refused("That is too long to type for you, sir.")
    auto.SendKeys(text, interval=0.005, waitTime=0.2, charMode=True)


MODIFIERS = {"ctrl": "{Ctrl}", "control": "{Ctrl}", "alt": "{Alt}", "shift": "{Shift}", "win": "{Win}", "windows": "{Win}"}
NAMED = {**KEYS, "delete": "{Delete}", "del": "{Delete}", "backspace": "{Back}", "insert": "{Insert}", "spacebar": "{Space}",
         "capital": "{Shift}", "plus": "+", "minus": "-", "equals": "=", "slash": "/", "dot": ".", "period": ".", "comma": ","}
SPOKEN_LETTERS = {"bee": "b", "cee": "c", "see": "c", "dee": "d", "gee": "g", "jay": "j", "kay": "k", "el": "l", "em": "m", "en": "n", "pee": "p",
                  "queue": "q", "cue": "q", "are": "r", "ess": "s", "tee": "t", "you": "u", "vee": "v", "ex": "x", "why": "y", "zed": "z", "zee": "z", "eff": "f", "oh": "o"}


def parse_key(text):
    """'f', 'control s', 'ctrl+shift+t', 'f11', 'alt f4', 'page down' -> SendKeys string. None when a word is not a key."""
    t = re.sub(r"[+,]| plus ", " ", (text or "").lower()).replace(" key", "").strip()
    if t in NAMED:
        return NAMED[t]
    words = t.split(); out = ""
    while words and words[0] in MODIFIERS:
        out += MODIFIERS[words.pop(0)]
    rest = " ".join(words)
    if not rest:
        return None
    if rest in NAMED and not NAMED[rest].startswith("{Ctrl}") and not NAMED[rest].startswith("{Alt}"):
        return out + NAMED[rest]
    rest = SPOKEN_LETTERS.get(rest, rest)
    if re.fullmatch(r"[a-z0-9]", rest):
        return out + rest
    if re.fullmatch(r"f(?:[1-9]|1[0-2])", rest):
        return out + "{" + rest.upper() + "}"
    return None


def press(key):
    k = parse_key(key)
    if not k:
        raise Refused(f"I don't know a key called '{key}', sir. Try a letter, a number, enter, escape, the arrows, or control or alt with a key.")
    front_window()
    _auto().SendKeys(k, waitTime=0.2)


def focus_field():
    """Put the cursor in the main text box of the window in front (a chat box, a search box). True if there was one."""
    win = front_window()
    fields = [c for c in _walk(win, {"EditControl", "DocumentControl"}) if not getattr(c, "IsPassword", False)]
    for c in reversed(fields):                                           # chat boxes sit at the bottom
        try:
            c.SetFocus()
            return True
        except Exception:
            continue
    return False
