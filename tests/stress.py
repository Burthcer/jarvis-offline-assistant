"""Big M1 stress test. Run: py -3.12 tests\\stress.py   Prints every failure and a pass rate per section."""
import os
import random
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis.core import announce_due, handle
from jarvis.store import Store
from jarvis.timeparse import MONTHS, parse_when

NOW = datetime(2026, 10, 31, 10, 0)  # Saturday
results = {}
fails = []


def check(section, ok, label, detail=""):
    r = results.setdefault(section, [0, 0])
    r[1] += 1
    if ok:
        r[0] += 1
    else:
        fails.append(f"[{section}] {label} {detail}")


# ---------- A. time parsing against an independent oracle ----------
def at(d, h, m=0):
    return datetime(d.year, d.month, d.day, h, m)


today, tom = NOW.date(), (NOW + timedelta(days=1)).date()
tasks = ["call mom", "buy milk", "maths exam", "submit the assignment", "pay fees", "email professor", "gym", "take medicine"]
lead = ["", "remind me to ", "remind me about ", "remind me that I have ", "hey jarvis remind me to ", "jarvis, remind me to ", "please remind me to ", "set a reminder to ", "add a reminder for "]
cases = []
for task in tasks:
    for h12 in range(1, 13):
        for ap in ("am", "pm"):
            h24 = h12 % 12 + (12 if ap == "pm" else 0)
            cases.append((f"{task} tomorrow at {h12}{ap}", task, at(tom, h24)))
            cases.append((f"{task} at {h12}:15 {ap} tomorrow", task, at(tom, h24, 15)))
            d = at(today, h24)
            cases.append((f"{task} at {h12} {ap}", task, d if d > NOW else d + timedelta(days=1)))
    for n in (1, 2, 5, 10, 15, 20, 30, 45, 59, 90):
        cases.append((f"{task} in {n} minutes", task, NOW + timedelta(minutes=n)))
        cases.append((f"{task} in {n} mins", task, NOW + timedelta(minutes=n)))
        cases.append((f"in {n} minutes {task}", task, NOW + timedelta(minutes=n)))
    for n in (1, 2, 3, 5, 12, 24):
        cases.append((f"{task} in {n} hours", task, NOW + timedelta(hours=n)))
        cases.append((f"{task} in {n} hrs", task, NOW + timedelta(hours=n)))
    for n in (1, 2, 3, 7, 14):
        cases.append((f"{task} in {n} days", task, NOW + timedelta(days=n)))
    cases.append((f"{task} in a week", task, NOW + timedelta(weeks=1)))
    cases.append((f"{task} in an hour", task, NOW + timedelta(hours=1)))
    cases.append((f"{task} in half an hour", task, NOW + timedelta(minutes=30)))
    for mi, mon in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1):
        for day in (1, 2, 3, 11, 15, 22, 28):
            dt = datetime(2026, mi, day)
            if dt.date() < today:
                dt = dt.replace(year=2027)
            suf = {1: "st", 2: "nd", 3: "rd", 11: "th", 15: "th", 22: "nd", 28: "th"}[day]
            for phrase in (f"on {day} {mon}", f"on {day}{suf} {mon}", f"on {mon} {day}", f"on {mon} {day}{suf}", f"{day} {mon[:3]}", f"on the {day}{suf} of {mon}"):
                cases.append((f"{task} {phrase}", task, at(dt, 9)))
    for k, name in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        ahead = (k - NOW.weekday()) % 7 or 7
        d = (NOW + timedelta(days=ahead)).date()
        cases.append((f"{task} on {name}", task, at(d, 9)))
        cases.append((f"{task} next {name}", task, at(d, 9)))
        cases.append((f"{task} {name} at 4pm", task, at(d, 16)))
        cases.append((f"{task} on {name.capitalize()} at 7:45 am", task, at(d, 7, 45)))
    cases.append((f"{task} tomorrow", task, at(tom, 9)))
    cases.append((f"{task} tomorrow morning", task, at(tom, 9)))
    cases.append((f"{task} tomorrow evening", task, at(tom, 18)))
    cases.append((f"{task} tomorrow night", task, at(tom, 21)))
    cases.append((f"{task} tonight", task, at(today, 21)))
    cases.append((f"{task} today at 11pm", task, at(today, 23)))
    cases.append((f"{task} day after tomorrow", task, at((NOW + timedelta(days=2)).date(), 9)))
    cases.append((f"{task} at 17:30", task, at(today, 17, 30)))
    cases.append((f"{task} at 06:05 tomorrow", task, at(tom, 6, 5)))
for ld in lead[:3]:
    pass
for text, task, want in cases:
    try:
        got_task, got = parse_when(text, NOW)
        check("A time parsing", got == want and got_task.lower() == task.lower(), repr(text), f"-> {got_task!r} {got} want {task!r} {want}")
    except Exception as e:
        check("A time parsing", False, repr(text), f"CRASH {e!r}")

# ---------- B. edge dates / times ----------
edge = [
    ("exam on 29 february", None),          # 2027 not leap -> must not crash
    ("exam on 30 february", None),
    ("exam on 31 april", None),
    ("exam on 0 march", None),
    ("exam on 32 march", None),
    ("meet at 25", None), ("meet at 99:99", None), ("meet at 13pm", None), ("meet at 0pm", None),
    ("meet at 12am", datetime(2026, 11, 1, 0, 0)), ("meet at 12pm", datetime(2026, 10, 31, 12, 0)),
    ("meet at 9:75 am", None), ("meet at 7:60 pm", None),
    ("exam on 31 december", datetime(2026, 12, 31, 9, 0)),
    ("exam on 1 january", datetime(2027, 1, 1, 9, 0)),
    ("exam on 31 october", datetime(2026, 10, 31, 11, 0)),
    ("meet in 0 minutes", NOW), ("meet in 100000 days", None), ("meet in 99999999999 hours", None),
]
for text, want in edge:
    try:
        _, got = parse_when(text, NOW)
        ok = (got == want) if want is not None else True
        if "29 february" in text and got is not None:
            ok = got.month == 2 and got.day == 29  # only valid in a leap year
        if want is None and got is not None and ("30 feb" in text or "31 apr" in text or "0 march" in text or "32 march" in text or "99:99" in text or "at 25" in text or "13pm" in text or "9:75" in text or "7:60" in text or "0pm" in text):
            ok = False  # invalid input must not become a made-up valid time
        check("B edge dates/times", ok, repr(text), f"-> {got} want {want}")
    except Exception as e:
        check("B edge dates/times", False, repr(text), f"CRASH {e!r}")

# year-end rollover / leap day with different "now"
for now2, text, want in [
    (datetime(2026, 12, 31, 23, 30), "x in 1 hour", datetime(2027, 1, 1, 0, 30)),
    (datetime(2026, 12, 31, 23, 30), "x tomorrow", datetime(2027, 1, 1, 9, 0)),
    (datetime(2028, 2, 28, 10, 0), "x tomorrow", datetime(2028, 2, 29, 9, 0)),
    (datetime(2028, 2, 29, 10, 0), "x on 29 february", datetime(2028, 2, 29, 11, 0)),  # today, 9am passed -> in an hour
    (datetime(2028, 3, 1, 10, 0), "x on 29 february", datetime(2032, 2, 29, 9, 0)),
    (datetime(2027, 1, 31, 10, 0), "x in 30 days", datetime(2027, 3, 2, 10, 0)),
    (datetime(2026, 11, 22, 23, 59), "x at 1am", datetime(2026, 11, 23, 1, 0)),
    (datetime(2026, 11, 22, 0, 0), "x at 12am", datetime(2026, 11, 23, 0, 0)),
]:
    try:
        _, got = parse_when(text, now2)
        check("B edge dates/times", got == want, f"{text!r} @ {now2}", f"-> {got} want {want}")
    except Exception as e:
        check("B edge dates/times", False, f"{text!r} @ {now2}", f"CRASH {e!r}")

# ---------- C. phrasing tables through handle() ----------
def fresh():
    return Store(":memory:")


add_forms = ["remind me to {t} {w}", "Remind me to {t} {w}.", "hey jarvis remind me to {t} {w}", "Hey Jarvis, remind me to {t} {w}",
             "ok jarvis remind me to {t} {w}", "jarvis remind me to {t} {w}", "please remind me to {t} {w}", "set a reminder to {t} {w}",
             "add a reminder to {t} {w}", "add reminder to {t} {w}", "remind me about {t} {w}", "REMIND ME TO {t} {w}",
             "remind me to {t} {w}!", "remind me to {t} {w}?", "  remind me to {t} {w}   "]
for f in add_forms:
    for t in ("call mom", "buy milk", "study physics"):
        s = fresh()
        out = handle(f.format(t=t, w="tomorrow at 5pm"), s, NOW)
        row = s.upcoming(NOW)
        check("C add phrasing", out.startswith("Noted") and len(row) == 1 and row[0]["due"] == "2026-11-01T17:00:00" and row[0]["text"].lower().rstrip("!?.") == t,
              repr(f.format(t=t, w="tomorrow at 5pm")), f"-> {out!r} {[dict(r) for r in row]}")

# remind me TIME to TASK order
for text, want_text in [("remind me tomorrow to buy a charger", "Buy a charger"), ("remind me in 10 minutes to check the oven", "Check the oven"),
                        ("remind me at 6pm to call dad", "Call dad"), ("remind me on friday to submit the form", "Submit the form"),
                        ("remind me in 2 hours and 30 minutes to leave", "Leave"), ("remind me tonight to study", "Study")]:
    s = fresh(); out = handle(text, s, NOW); r = s.upcoming(NOW)
    check("C add phrasing", out.startswith("Noted") and r and r[0]["text"] == want_text, repr(text), f"-> {out!r}")

# missing time asks; missing task asks
for text in ["remind me to call mom", "remind me about the exam", "remind me", "remind me to", "remind me tomorrow"]:
    s = fresh(); out = handle(text, s, NOW)
    check("C add phrasing", ("When" in out or "what" in out.lower() or "afraid" in out) and not s.upcoming(NOW), repr(text), f"-> {out!r}")

# query phrasing
def seeded():
    s = fresh()
    for t in ["remind me to call mom in 30 minutes", "remind me to buy milk today at 9pm", "remind me to pay fees tomorrow at 10am", "remind me maths exam on 23 november"]:
        handle(t, s, NOW)
    return s

today_q = ["what do we got to do today", "what do we have today", "what's on today", "what is on for today", "what's the schedule today", "my agenda for today",
           "what do I have to do today", "what the hell do we got to do today", "Hey Jarvis what do we have today?", "anything today", "what's happening today",
           "tell me my plan for today", "what's today", "today's reminders", "what do I have tonight", "show me today", "read my schedule"]
for q in today_q:
    out = handle(q, seeded(), NOW)
    check("C query today", "Call mom" in out and "Buy milk" in out and "Pay fees" not in out and "Maths" not in out, repr(q), f"-> {out!r}")
for q in ["what do I have tomorrow", "what's on tomorrow", "anything tomorrow", "tomorrow's reminders", "what's tomorrow looking like", "what do we got tomorrow?"]:
    out = handle(q, seeded(), NOW)
    check("C query tomorrow", "Pay fees" in out and "Call mom" not in out, repr(q), f"-> {out!r}")
later = NOW + timedelta(hours=2)
for q in ["what did I miss yesterday", "what did I miss", "what have I missed", "did I miss anything", "what did i miss today", "anything overdue", "what's overdue", "what was I supposed to do yesterday", "missed reminders", "what did I forget"]:
    out = handle(q, seeded(), later)
    check("C query missed", "Call mom" in out and "Pay fees" not in out, repr(q), f"-> {out!r}")
for q in ["what's coming up", "list", "list my reminders", "show my reminders", "show all reminders", "what are my reminders", "what's next", "what do I have coming up", "upcoming reminders", "my reminders", "list reminders"]:
    out = handle(q, seeded(), NOW)
    check("C query upcoming", "Maths exam" in out and "Pay fees" in out, repr(q), f"-> {out!r}")

# notes
notes = [("remember that my locker code is 4821", "locker", "4821"), ("remember my wifi password is abc123", "wifi", "abc123"),
         ("Remember: the library card number is 99-221", "library", "99-221"), ("remember that mom's birthday is 14 march", "birthday", "14 march"),
         ("hey jarvis remember I parked on level 3", "parked", "level 3")]
for add, key, val in notes:
    for q in (f"what do you remember about {key}", f"recall {key}", f"do you remember {key}", f"what is my {key}", f"what's my {key}"):
        s = fresh(); handle(add, s, NOW); out = handle(q, s, NOW)
        check("C notes", val in out, repr((add, q)), f"-> {out!r}")
s = fresh(); out = handle("what do you remember about unicorns", s, NOW)
check("C notes", "don't have" in out, "recall of nothing", f"-> {out!r}")
s = fresh(); handle("remember my wifi password is abc123", s, NOW); handle("remember my wifi password is xyz789", s, NOW)
check("C notes", len(s.notes("wifi")) == 1 and "xyz789" in s.notes("wifi")[0]["text"], "note repeat updates", str([r["text"] for r in s.notes("wifi")]))

# done / delete
for f in ["done {x}", "done with {x}", "finished {x}", "completed {x}", "mark {x} done", "mark {x} as done", "mark {x} as completed", "Jarvis, mark {x} as done", "mark done {x}"]:
    s = fresh(); handle("remind me about physics exam on 24 nov", s, NOW); out = handle(f.format(x="physics exam"), s, NOW)
    check("C done", "Marked done" in out and not s.upcoming(NOW), repr(f.format(x="physics exam")), f"-> {out!r}")
s = fresh(); handle("remind me about physics exam on 24 nov", s, NOW); r = s.upcoming(NOW)[0]
out = handle(f"done {r['id']}", s, NOW); check("C done", "Marked done" in out, "done by number", out)
out = handle("done unicorn", s, NOW); check("C done", "couldn't find" in out, "done unknown", out)
for f in ["delete {x}", "cancel {x}", "remove {x}", "cancel the {x} reminder", "delete reminder {x}", "Jarvis delete {x}"]:  # the owner: when told to cancel, cancel
    s = fresh(); handle("remind me to buy milk tomorrow at 5pm", s, NOW)
    q = handle(f.format(x="buy milk"), s, NOW)
    check("C delete at once", "Cancelled" in q and not s.upcoming(NOW) and s.pending is None, repr(f), f"-> {q!r}")

# the "pending" answer must not eat a real command
s = fresh(); handle("clear everything", s, NOW)
out = handle("remind me to call dad tomorrow at 6pm", s, NOW)
check("C delete at once", out.startswith("Noted") and len(s.upcoming(NOW)) == 1, "new command while a question is open is not lost", f"-> {out!r}")

# dedupe behaviour
dups = [(["remind me about my maths exam on 23 november", "remind me maths exam on 25 november"], 1),
        (["remind me to call mom tomorrow at 5pm", "remind me to call mom tomorrow at 6pm"], 1),
        (["remind me about physics exam on 24 nov", "remind me about chemistry exam on 25 nov"], 2),
        (["remind me to buy milk tomorrow", "remind me to buy bread tomorrow"], 2),
        (["remind me to call mom tomorrow at 5pm", "remind me to call dad tomorrow at 5pm"], 2),
        (["remind me about the exam on 24 nov", "remind me about the Exam on 24 nov"], 1),
        (["remind me to pay fees on 5 dec", "remind me to pay the fees on 6 dec"], 1),
        (["remind me to study maths tomorrow", "remind me to study physics tomorrow"], 2),
        (["remind me to study tomorrow", "remind me to study maths tomorrow"], 1)]
for seq, want in dups:
    s = fresh()
    for x in seq:
        handle(x, s, NOW)
    n = s.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    check("C dedupe", n == want, repr(seq), f"-> {n} items want {want}")
# a done item must not swallow a new one
s = fresh(); handle("remind me about physics exam on 24 nov", s, NOW); handle("done physics exam", s, NOW); out = handle("remind me about physics exam on 28 nov", s, NOW)
check("C dedupe", out.startswith("Noted") and len(s.upcoming(NOW)) == 1, "new item after done is fresh", f"-> {out!r}")
# a reminder that has already fired and is repeated should fire again
s = fresh(); handle("remind me to call mom in 5 minutes", s, NOW); announce_due(s, NOW + timedelta(minutes=6)); handle("remind me to call mom in 10 minutes", s, NOW + timedelta(minutes=7))
check("C dedupe", len(announce_due(s, NOW + timedelta(minutes=20))) == 1, "repeated fired reminder fires again", "")

# ---------- D. announce_due ----------
s = fresh()
for i in range(5):
    handle(f"remind me to task{i} in {i + 1} minutes", s, NOW)
check("D announce", announce_due(s, NOW) == [], "nothing early", "")
got = announce_due(s, NOW + timedelta(minutes=3, seconds=30))
check("D announce", len(got) == 3 and all(x.startswith("Sir, reminder:") for x in got), "3 due", str(got))
check("D announce", announce_due(s, NOW + timedelta(minutes=3, seconds=30)) == [], "not repeated", "")
check("D announce", len(announce_due(s, NOW + timedelta(days=3))) == 2, "rest later", "")
s = fresh(); handle("remind me to call mom in 5 minutes", s, NOW)
check("D announce", len(announce_due(s, NOW + timedelta(days=30))) == 1, "very late still announces", "")
check("D announce", "Call mom" in handle("what did I miss", s, NOW + timedelta(days=30)), "announced-not-done shows as missed", "")

# ---------- E. robustness (must never crash) ----------
weird = ["", " ", "\n", "\t\t", ".", "?", "jarvis", "hey jarvis", "Hey Jarvis!", "yes", "no", "😀", "remind me to 😀 tomorrow at 5pm", "remind me to " + "a" * 100000,
         "remind me to " + "a b " * 20000 + " tomorrow", "'; DROP TABLE items; --", "remind me to '; DROP TABLE items; -- tomorrow", "remember \"quotes\" 'single' %s %d {x} {}",
         "remind me to {0} tomorrow", "remind me to %s tomorrow", "\x00\x01\x02", "remind me to call\x00mom tomorrow", "कल मुझे याद दिलाओ", "remind me to नमस्ते tomorrow at 5pm",
         "delete", "done", "mark", "mark done", "cancel", "remember", "remember that", "recall", "what", "what is", "what's", "what is my", "remind me to at", "remind me on on on",
         "remind me at 5pm at 6pm tomorrow yesterday", "remind me in in in 5 minutes", "remind me in 5 5 5 minutes", "remind me in -5 minutes", "remind me in 1e9 minutes",
         "remind me in 999999999999999999999 minutes", "remind me on 99999999 november", "remind me on 31 31 31", "remind me at 99999999999999999999 pm", "remind me on 00 jan",
         "remind me at 5pm" * 500, "tomorrow " * 5000, "yesterday", "missed " * 3000, "(?i)(a+)+$", "remind me to " + "(" * 5000, "remind me to \\", "list " * 2000]
s = fresh()
for w in weird:
    try:
        t0 = time.perf_counter(); out = handle(w, s, NOW); dt = time.perf_counter() - t0
        check("E robustness", isinstance(out, str) and dt < 1.0, repr(w[:60]), f"-> {type(out)} {dt:.2f}s")
    except Exception as e:
        check("E robustness", False, repr(w[:60]), f"CRASH {e!r}")
check("E robustness", s.db.execute("SELECT COUNT(*) FROM items").fetchone()[0] >= 0, "table still exists after injection strings", "")

# random fuzz
random.seed(1234)
vocab = (["remind", "me", "to", "about", "tomorrow", "today", "tonight", "yesterday", "at", "on", "in", "next", "the", "of", "and", "am", "pm", "morning", "evening", "hours", "minutes", "mins", "days", "week", "half", "an", "a",
          "done", "delete", "cancel", "remember", "recall", "what", "did", "I", "miss", "list", "jarvis", "hey", "yes", "no", "mark", "as", "is", "my", "exam", "mom", "milk", "5", "12", "0", "31", "99", "5:30", "17:45", "99:99", "1st", "2nd", "23rd", "00",
          "monday", "friday", "sunday", "november", "feb", "dec", "may", "oct", ",", ".", "?", "!", "-", "'", '"', ";", "#", "#3", "😀"] + [m for m in MONTHS])
crashes = 0
t0 = time.perf_counter()
N = 40000
fs = fresh()
for i in range(N):
    text = " ".join(random.choice(vocab) for _ in range(random.randint(1, 12)))
    try:
        out = handle(text, fs, NOW + timedelta(minutes=random.randint(0, 10000)))
        ok = isinstance(out, str)
        if not ok:
            raise TypeError(type(out))
    except Exception as e:
        crashes += 1
        check("F fuzz 40000 random sentences", False, repr(text), f"CRASH {e!r}")
        fs.pending = None
        if crashes > 30:
            break
else:
    pass
r = results.setdefault("F fuzz 40000 random sentences", [0, 0])
r[0] += N - crashes if crashes <= 30 else 0
r[1] += (N - crashes) if crashes <= 30 else 0
print(f"fuzz: {N} sentences in {time.perf_counter() - t0:.1f}s, crashes={crashes}")

# fuzz parse_when alone with a wider vocabulary and random 'now' (also checks invariant: result is None or datetime >= now - 0)
bad_inv = 0
for i in range(30000):
    now2 = datetime(2026, 1, 1) + timedelta(minutes=random.randint(0, 60 * 24 * 900))
    text = " ".join(random.choice(vocab) for _ in range(random.randint(1, 8)))
    try:
        gs = fresh(); handle("remind me to " + text, gs, now2)
        bad = [r["due"] for r in gs.db.execute("SELECT due FROM items WHERE kind='reminder'") if datetime.fromisoformat(r["due"]) < now2 - timedelta(minutes=1)]
        check("G parse invariant: never crashes, never in the past", not bad, repr(text), f"now={now2} -> {bad}")
    except Exception as e:
        check("G parse invariant: never crashes, never in the past", False, repr(text), f"CRASH {e!r}")
        if len(fails) > 400:
            break

# ---------- H. persistence + concurrency + real files ----------
d = tempfile.mkdtemp()
path = os.path.join(d, "t.db")
s = Store(path); handle("remind me to call mom tomorrow at 5pm", s, NOW); handle("remember my locker code is 4821", s, NOW); s.db.close()
s2 = Store(path)
check("H persistence", "Call mom" in handle("list", s2, NOW) and "4821" in handle("recall locker", s2, NOW), "survives restart", "")
handle("remind me to call mom tomorrow at 6pm", s2, NOW)
check("H persistence", s2.db.execute("SELECT COUNT(*) FROM items WHERE kind='reminder'").fetchone()[0] == 1, "dedupe across restart", "")
# two processes' worth of connections at once
sA, sB = Store(path), Store(path)
errs = []
def worker(st, tag):
    try:
        for i in range(150):
            handle(f"remind me to {tag}task{i} tomorrow at 5pm", st, NOW)
    except Exception as e:
        errs.append(repr(e))
ts = [threading.Thread(target=worker, args=(sA, "alpha")), threading.Thread(target=worker, args=(sB, "beta"))]
[t.start() for t in ts]; [t.join() for t in ts]
check("H concurrency", not errs, "two connections writing at once", str(errs[:3]))
# same connection used by the main thread and the background watcher (as in the real app)
shared = Store(os.path.join(d, "shared.db")); stop = False; werrs = []
def watcher():
    while not stop:
        try:
            announce_due(shared, NOW + timedelta(days=400))
        except Exception as e:
            werrs.append(repr(e)); return
wt = threading.Thread(target=watcher, daemon=True); wt.start()
try:
    for i in range(400):
        handle(f"remind me to thing{i} in {i % 50 + 1} minutes", shared, NOW)
        handle("list", shared, NOW)
except Exception as e:
    werrs.append(repr(e))
stop = True; wt.join(2)
check("H concurrency", not werrs, "main thread + background watcher on one connection", str(werrs[:3]))
n = shared.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
check("H concurrency", n == 400, "no lost or duplicated rows", f"{n} rows, want 400")

# speed with a big database
big = Store(os.path.join(d, "big.db"))
for i in range(3000):
    big.db.execute("INSERT INTO items(kind,text,key,due,created,updated) VALUES('reminder',?,?,?,?,?)",
                   (f"item {i} word{i % 90}", f"item {i} word{i % 90}", (NOW + timedelta(minutes=i)).isoformat(), "x", "x"))
big.db.commit()
t0 = time.perf_counter(); handle("remind me to brand new thing tomorrow at 5pm", big, NOW); handle("what's coming up", big, NOW); handle("what do we have today", big, NOW)
ms = (time.perf_counter() - t0) * 1000
check("H speed", ms < 200, "3 commands on a 3000-item database", f"{ms:.1f} ms")

# ---------- report ----------
print()
tot_ok = tot = 0
for k in sorted(results):
    ok, n = results[k]
    tot_ok += ok; tot += n
    print(f"{k:60s} {ok:6d}/{n:<6d} {'PASS' if ok == n else 'FAIL'}")
print(f"{'TOTAL':60s} {tot_ok:6d}/{tot:<6d}  failure rate {100 * (tot - tot_ok) / tot:.3f}%")
print(f"\n{len(fails)} failures" + (":" if fails else ""))
for f in fails[:150]:
    print(" ", f.encode("ascii", "backslashreplace").decode())
