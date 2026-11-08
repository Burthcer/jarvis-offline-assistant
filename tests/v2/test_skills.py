"""Skills taught by voice, the wish list, and reading an app's answer back. Fake PC, scripted AI, no sound, no real app. Run: JARVIS_SILENT=1 py -3.12 tests/v2/test_skills.py"""
import os
import sys
import tempfile

os.environ["JARVIS_SILENT"] = "1"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(HERE)), HERE]
from harness import fresh  # noqa: E402
from jarvis2.abilities import screen  # noqa: E402

FAILS, N = [], 0
screen.POLL_S = 0
REQ = os.path.join(tempfile.mkdtemp(), "requests.md")
os.environ["JARVIS_REQUESTS"] = REQ


def check(name, cond, info=""):
    global N
    N += 1
    if not cond:
        FAILS.append(f"{name} {info}")


class Script:
    def __init__(self, **out):
        self.out, self.asked = out, []

    def complete(self, msgs, temperature=0.0, max_tokens=90):
        self.asked.append(msgs[-1]["content"])
        if msgs[-1]["content"].startswith("TEXT:"):
            return "It says the notes are about maths, sir."
        return self.out[msgs[-1]["content"].split("]\n", 1)[-1]]


ai = Script(**{"keep a ten second timer": 'timer_set(duration="ten second")', "turn off the lights": "CHAT: I can't, sir.", "gibberish words": "ASK: What, sir?",
               "delete my files": "CHAT: no.", "ask claude hi": 'send_to_app(app="claude", text="summarise my notes")'})

# ----- teaching -----
app, os_, store = fresh(ai); app.natural = False
r = app.handle("when I say focus mode open notepad and keep a ten second timer")
check("taught", r.ok and app.memory.routines() == ["focus mode"] and "Learned" in r.text, (r.text, app.memory.routines()))
check("steps are his sentences", [s["args"]["text"] for s in app.memory.routine_get("focus mode")] == ["open notepad", "keep a ten second timer"], app.memory.routine_get("focus mode"))
check("teaching did nothing yet", not any(x[0] == "open" for x in os_.log) and not [t for t in store.all_timers() if "ten" in str(t)], os_.log)
n0 = len(store.all_timers())
r = app.handle("focus mode")
check("running it opens and times", ("open", "notepad", "app", 1, None) in os_.log and len(store.all_timers()) == n0 + 1 and r.ok, (os_.log, r.text))
check("running a skill is not 'the last thing'", [c.ability for c, _ in app.last_acts] == [] or all(c.ability != "routine_run" for c, _ in app.last_acts))
r = app.handle("learn a skill called morning that opens notepad and then opens calculator")
check("other phrasing", r.ok and "morning" in app.memory.routines(), (r.text, app.memory.routines()))
os_.log.clear()
app.handle("morning")
check("both steps ran", ("open", "notepad", "app", 1, None) in os_.log and any(x[:2] == ("open", "calculator") for x in os_.log), os_.log)

# ----- rails -----
for said, why in (("when I say bad one turn off the lights", "a chat answer"), ("when I say bad two open notepad then gibberish words", "an unclear step"),
                  ("when I say bad three open notepad and ask claude hi", "typing into another app needs a yes"), ("when I say bad four open notepad then turn off the lights", "not an action"),
                  ("when I say bad five open notepad and focus mode", "a skill inside a skill"), ("when I say open open notepad", "name already means something")):
    r = app.handle(said)
    check(f"refused: {why}", not r.ok and not any(n.startswith("bad") for n in app.memory.routines()) and "open" not in app.memory.routines(), (r.text, app.memory.routines()))
r = app.handle("when I say big one open notepad and open calculator and open edge and open chrome and open discord and open whatsapp and open youtube and open linkedin and open gmail")
check("too many steps", not r.ok and "big one" not in app.memory.routines(), r.text)
# a saved skill whose step later became unsafe never runs it
app.memory.routine_save("sneaky", [{"a": "say", "args": {"text": "shut down"}}, {"a": "say", "args": {"text": "open notepad"}}], app.clock())
os_.log.clear()
r = app.handle("sneaky")
check("an unsafe skill step stops the routine before later actions", not r.ok and not app.exit_requested and not os_.log and 'Stopped after 0 of 2' in r.text, (app.exit_requested, os_.log, r.text))
check("the knowledge page can show say steps", "open notepad" in str(app.memory.routine_steps("morning")))

# ----- wish list -----
app, os_, store = fresh(ai); app.natural = False
r = app.handle("I wish you could order me a pizza")
check("wish added", r.ok and "wish list" in r.text and open(REQ, encoding="utf-8").read().strip().endswith("order me a pizza"), (r.text, open(REQ).read()))
check("line format", open(REQ, encoding="utf-8").read().startswith("- [ ] 2026-10-31 "), open(REQ).read())
r = app.handle("add a feature to read my email aloud"); r = app.handle("I wish you could order me a pizza")
check("no duplicates", open(REQ, encoding="utf-8").read().count("pizza") == 1 and "already" in r.text, r.text)
r = app.handle("what is on your wish list")
check("wish list read back", "2 on my list" in r.text and "pizza" in r.text, r.text)
check("Jarvis never touched code", not os.path.exists(os.path.join(REQ, "..", "x.py")))

# ----- reading the answer back -----
app, os_, store = fresh(ai); app.natural = False; os_._running.add("claude")
os_.ui_script = ["Claude\nHistory\nsummarise my notes", "Claude\nHistory\nsummarise my notes", "Claude\nHistory\nsummarise my notes\nThinking", "Claude\nHistory\nsummarise my notes\nYour notes are about maths.",
                 "Claude\nHistory\nsummarise my notes\nYour notes are about maths."]
app.handle("ask claude hi")
os_.log.clear()
r = app.handle("yes")
check("sent, waited for the answer, read it back", "Sent" in r.text and "maths" in r.text and ("ui_press", "enter") in os_.log, (r.text, os_.log))
check("it only asked the AI about the NEW text", any(q.startswith("TEXT:\nThinking") or "Your notes" in q for q in ai.asked) and not any("History" in q for q in ai.asked if q.startswith("TEXT:")), ai.asked[-1:])
app5, os5, _ = fresh(ai); app5.natural = False; os5._running.add("claude")
os5.ui_script = ["Claude\nsummarise my notes"] 
app5.handle("ask claude hi"); r = app5.handle("yes")
check("nothing new: says it is still answering, never invents", "still answering" in r.text and "maths" not in r.text, r.text)
os5.ui_script = ["Claude\nsummarise my notes\nBack then: 42 is the answer."]
r = app5.handle("what did claude say")
check("what did claude say reads the window and answers", r.ok and "claude says" in r.text.lower(), r.text)
check("it focused Claude first", ("focus", "claude", "app") in os5.log, os5.log)
r = app5.handle("read claude s answer")
check("other phrasing", "claude says" in r.text.lower(), r.text)
app6, os6, _ = fresh(ai); app6.natural = False
r = app6.handle("what did claude say")
check("not open: plain words", not r.ok and "front" in r.text, r.text)
os6._running.add("claude"); os6.fail.add("ui")
r = app6.handle("what did claude say")
check("a bank or login window is still refused", not r.ok and "bank" in r.text, r.text)

print("\n".join(FAILS) or "no failures", f"\n{N - len(FAILS)}/{N}")
sys.exit(1 if FAILS else 0)
