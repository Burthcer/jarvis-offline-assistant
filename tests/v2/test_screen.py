"""Operating other apps. Part 1: the abilities and their rails with a fake PC. Part 2: the REAL UI Automation code against a throw-away window made by this test
(a window called 'Test Window Alpha': never one of the owner's apps, no screen capture, no sound). Run: py -3.12 tests/v2/test_screen.py -> failures only, then a count."""
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(HERE)), HERE]
from harness import fresh  # noqa: E402

FAILS, N = [], 0


class Script:
    def __init__(self, **out):
        self.out = out
        self.asked = []

    def complete(self, msgs, temperature=0.0, max_tokens=90):
        self.asked.append(msgs[-1]["content"])
        key = msgs[-1]["content"].split("]\n", 1)[-1]
        if "SCREEN TEXT" in key:
            return "The price is 499 rupees, sir."
        return self.out[key]


def check(name, cond, info=""):
    global N
    N += 1
    if not cond:
        FAILS.append(f"{name} {info}")


# ----- part 1: abilities and rails, fake PC -----
ai = Script(**{"what is the price": 'screen_ask(question="what is the price")', "press save": 'ui_click(label="save")', "press send": 'ui_click(label="send message")',
               "type hello": 'ui_type(text="hello there")', "hit enter": 'ui_press(key="enter")', "hit tab": 'ui_press(key="tab")', "close it all": 'ui_press(key="alt f4")',
               "ask claude hi": 'send_to_app(app="claude", text="summarise my notes")'})
app, os_, store = fresh(ai)
app.natural = False
r = app.handle("read the screen")
check("read the screen: instant phrase, answered from the window's text", "499" in r.text and r.plan.source == "phrase", (r.text, r.plan.source))
check("the answer prompt carries the window's text and nothing else about the PC", any("Price: 499" in q for q in ai.asked), ai.asked)
r = app.handle("what is the price")
check("a question about the screen", "499" in r.text, r.text)
r = app.handle("press save")
check("an ordinary click just happens", ("ui_click", "save") in os_.log and r.ok and "Clicked" in r.text, (os_.log, r.text))
os_.log.clear()
r = app.handle("press send")
check("a risky click asks first and does nothing yet", r.plan.kind == "ask" and "Shall I click" in r.text and not os_.log, (r.text, os_.log))
r = app.handle("yes")
check("after a yes it clicks", ("ui_click", "send message") in os_.log, os_.log)
os_.log.clear()
r = app.handle("press send")
r = app.handle("no")
check("after a no it never clicks", not os_.log and "Very good" in r.text, (os_.log, r.text))
r = app.handle("type hello")
check("typing never presses enter", ("ui_type", "hello there") in os_.log and not any(x[0] == "ui_press" for x in os_.log), os_.log)
os_.log.clear()
r = app.handle("hit enter")
check("enter right after typing asks (it may send)", r.plan.kind == "ask" and "Enter" in r.text and not os_.log, (r.text, os_.log))
r = app.handle("yes")
check("then presses it", ("ui_press", "enter") in os_.log, os_.log)
app2, os2, st2 = fresh(ai); app2.natural = False
r = app2.handle("hit enter")
check("enter with nothing typed is an ordinary key", ("ui_press", "enter") in os2.log, os2.log)
r = app2.handle("hit tab")
check("tab", ("ui_press", "tab") in os2.log)
r = app2.handle("close it all")
check("Alt+F4 is not a key Jarvis has", r.plan.kind == "ask" and not [x for x in os2.log if x[0] == "ui_press" and "f4" in str(x)], (r.plan.kind, r.plan.error, os2.log))
app3, os3, st3 = fresh(ai); app3.natural = False; os3._running.add("claude")
r = app3.handle("ask claude hi")
check("send_to_app: brings the app up, types, then asks before sending", [x[0] for x in os3.log] == ["focus", "ui_focus_field", "ui_type"] and "Shall I send it" in r.text, (os3.log, r.text))
check("nothing was sent", ("ui_press", "enter") not in os3.log)
os3.log.clear()
r = app3.handle("yes")
check("yes sends it (one Enter, then only looking at the window)", [x for x in os3.log if x[0] != "ui_read"] == [("ui_press", "enter")] and "Sent" in r.text, (os3.log[:4], r.text))
app4, os4, st4 = fresh(ai); app4.natural = False
os4.fail.add("ui")
r = app4.handle("read the screen")
check("a bank or login window is refused in plain words", not r.ok and "bank" in r.text, r.text)
r = app4.handle("press save")
check("and nothing is clicked there", not r.ok and "bank" in r.text)

# ----- part 2: the real UI Automation code against a window of our own (tests/v2/winform_target.ps1, a throw-away WinForms window) -----
import subprocess  # noqa: E402
import tempfile  # noqa: E402

from jarvis2 import uia  # noqa: E402

tmp = tempfile.mkdtemp()
STATE, TITLE = os.path.join(tmp, "state.txt"), os.path.join(tmp, "title.txt")
open(TITLE, "w").write("")
proc = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(HERE, "winform_target.ps1"), STATE, TITLE],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def fields():
    try:
        return open(STATE + ".fields", encoding="utf-16").read().strip()
    except Exception:
        return ""


def clicked():
    try:
        return open(STATE, encoding="utf-16").read().split()
    except Exception:
        return []


def settitle(t):
    open(TITLE, "w").write(t)
    time.sleep(0.8)


def real_part():
    title = ""
    for _ in range(40):                                                  # the window takes a few seconds to appear
        try:
            title = uia.front_window().Name
        except uia.Refused:
            title = ""
        if title == "Test Window Alpha":
            break
        time.sleep(0.5)
    if title != "Test Window Alpha":
        print("NOT VERIFIED: the front window is %r, not the test window; skipped (PC locked, or something took the focus)" % title)
        return
    check("UI Automation sees the window in front", True)
    try:
        uia.press("alt f4")
        check("Alt+F4 is refused", False)
    except uia.Refused:
        check("Alt+F4 is refused", True)
    text = uia.read_window()
    check("reads its text", "Price 499" in text and "Save" in text, text)
    check("a password field is never read", "*" not in text and "●" not in text)
    label = uia.click("save")
    time.sleep(0.5)
    check("clicks a button by its label", "saved" in clicked() and label == "Save", (clicked(), label))
    check("fuzzy label ('sav')", uia.find("sav")[1] == "Save")
    try:
        uia.find("launch the rockets")
        check("an unknown label is refused", False)
    except uia.Refused:
        check("an unknown label is refused", True)
    check("'Send message' is recognised as risky", uia.risky("Send message") and not uia.risky("Save"))
    check("focus_field finds the box", uia.focus_field())
    uia.type_text("hello there")
    time.sleep(0.8)
    check("types into the focused box", "box=hello there" in fields(), fields())
    check("typing never sent anything", "sent" not in clicked(), clicked())
    pwbox = [c for c in uia._walk(uia.front_window(), {"EditControl"}) if getattr(c, "IsPassword", False)]
    if pwbox:
        pwbox[0].SetFocus()
        time.sleep(0.4)
        try:
            uia.type_text("secret")
            check("a password field is never typed into", "pw=secret" not in fields(), fields())
        except uia.Refused:
            check("a password field is never typed into", "pw=secret" not in fields(), fields())
    else:
        print("NOT VERIFIED: UI Automation did not report the password box as a password field")
    settitle("My Bank Login")
    try:
        uia.read_window()
        check("a window called bank / login is refused", False)
    except uia.Refused:
        check("a window called bank / login is refused", True)
    settitle("Jarvis V2")
    try:
        uia.read_window()
        check("Jarvis's own window is refused", False)
    except uia.Refused:
        check("Jarvis's own window is refused", True)


try:
    real_part()
except Exception as ex:
    import traceback
    traceback.print_exc()
    FAILS.append("real part crashed: " + repr(ex))
finally:
    open(TITLE, "w").write("QUIT")
    try:
        proc.wait(5)
    except Exception:
        proc.kill()                                                      # our own child, started above
print("FAILED:" if FAILS else "all ok", *FAILS, sep="\n")
print(f"{N - len(FAILS)}/{N} checks")
os._exit(1 if FAILS else 0)
