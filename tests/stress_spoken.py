"""Spoken-style stress test (what speech-to-text really writes). Run: py -3.12 tests\\stress_spoken.py
Imported by stress.py's report as section I."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis.core import announce_due, handle
from jarvis.store import Store

NOW = datetime(2026, 10, 31, 10, 0)  # Saturday
total = ok_count = 0
fails = []


def check(ok, label, detail=""):
    global total, ok_count
    total += 1
    ok_count += bool(ok)
    if not ok:
        fails.append(f"{label} {detail}")


def fresh():
    return Store(":memory:")


def D(m, d, h, mi=0, y=2026):
    return datetime(y, m, d, h, mi)


spoken = [
    ("Remind me to call mom at 5 p.m.", "Call mom", D(10, 31, 17)),
    ("Remind me to call mom at 5 PM tomorrow.", "Call mom", D(11, 1, 17)),
    ("remind me to call mom at five pm", "Call mom", D(10, 31, 17)),
    ("remind me to call mom at five thirty pm tomorrow", "Call mom", D(11, 1, 17, 30)),
    ("remind me to call mom at five forty five pm", "Call mom", D(10, 31, 17, 45)),
    ("remind me to take medicine at 8:30 a.m.", "Take medicine", D(11, 1, 8, 30)),
    ("remind me to take medicine at eight thirty in the morning", "Take medicine", D(11, 1, 8, 30)),
    ("remind me in five minutes to check the rice", "Check the rice", D(10, 31, 10, 5)),
    ("remind me in two hours to leave", "Leave", D(10, 31, 12)),
    ("remind me in twenty five minutes to leave", "Leave", D(10, 31, 10, 25)),
    ("remind me in an hour to stretch", "Stretch", D(10, 31, 11)),
    ("Can you remind me to call dad tomorrow at 6", "Call dad", D(11, 1, 18)),
    ("could you please remind me to pay fees on the 5th of December", "Pay fees", D(12, 5, 9)),
    ("Would you remind me to buy a pen tomorrow at 4", "Buy a pen", D(11, 1, 16)),
    ("don't let me forget to submit the form on friday", "Submit the form", D(11, 6, 9)),
    ("don't let me forget my maths exam on 23rd November", "My maths exam", D(11, 23, 9)),
    ("I need you to remind me about the lab record on Monday at 2 p.m.", "The lab record", D(11, 2, 14)),
    ("remind me of the physics practical on twenty fourth november", "The physics practical", D(11, 24, 9)),
    ("remind me about chemistry on november twenty third", "Chemistry", D(11, 23, 9)),
    ("remind me about chemistry on the twenty third of november", "Chemistry", D(11, 23, 9)),
    ("remind me about the viva on second december at eleven a.m.", "The viva", D(12, 2, 11)),
    ("remind me that I have a viva on 2nd December at 11 a.m.", "Viva", D(12, 2, 11)),
    ("remind me to call mom at noon tomorrow", "Call mom", D(11, 1, 12)),
    ("remind me to call mom at midnight", "Call mom", D(11, 1, 0)),
    ("remind me tomorrow at 7 in the morning to wake up", "Wake up", D(11, 1, 7)),
    ("remind me tomorrow at 5 in the morning to wake up", "Wake up", D(11, 1, 5)),
    ("remind me to sleep at 9 at night", "Sleep", D(10, 31, 21)),
    ("remind me to study at 8 in the evening", "Study", D(10, 31, 20)),
    ("remind me at quarter past 4 to stand up", "Stand up", D(10, 31, 16, 15)),
    ("remind me at half past 6 to cook", "Cook", D(10, 31, 18, 30)),
    ("remind me to call mom at 5 o'clock tomorrow", "Call mom", D(11, 1, 17)),
    ("remind me to read on the 26th", "Read", D(11, 26, 9)),
    ("remind me to call mom tomorrow at 5pm please", "Call mom", D(11, 1, 17)),
    ("remind me to call mom tomorrow at 5pm sir", "Call mom", D(11, 1, 17)),
    ("Please remind me to call mom tomorrow at 5pm", "Call mom", D(11, 1, 17)),
    ("remind me to call mom this friday", "Call mom", D(11, 6, 9)),
    ("Hey Jarvis, can you remind me to call dad at 7 pm?", "Call dad", D(10, 31, 19)),
    ("remind me about the exam in three weeks", "The exam", D(11, 21, 10)),
    ("remind me to pay rent in 2 days", "Pay rent", D(11, 2, 10)),
]
for text, want_text, want_due in spoken:
    s = fresh(); out = handle(text, s, NOW); rows = s.db.execute("SELECT * FROM items").fetchall()
    check(len(rows) == 1 and rows[0]["text"] == want_text and rows[0]["due"] == want_due.isoformat() and out.startswith("Noted"),
          repr(text), f"-> {out!r} {[(r['text'], r['due']) for r in rows]} want {want_text!r} {want_due}")


def seeded():
    s = fresh()
    for t in ["remind me to call mom in 30 minutes", "remind me to buy milk today at 9pm", "remind me to pay fees tomorrow at 10am", "remind me maths exam on 23 november",
              "remind me about the viva on friday at 3pm", "remember the exam hall is room 204", "remember my roll number is 24CS042"]:
        handle(t, s, NOW)
    return s


for q, must, mustnot in [
    ("what do I have on friday", "viva", "Pay fees"), ("do I have anything on friday", "viva", "Call mom"), ("what's on friday", "viva", "Maths"),
    ("what do I have on 23rd November", "Maths", "viva"), ("what's on the twenty third of november", "Maths", "viva"), ("anything on november 23", "Maths", "viva"),
    ("what do I have this week", "viva", "Maths"), ("what's my schedule for tomorrow", "Pay fees", "Call mom"),
    ("which room is the exam hall", "room 204", "24CS"), ("where is the exam hall", "room 204", "24CS"), ("what's my roll number", "24CS042", "room"),
    ("tell me my roll number", "24CS042", "room"), ("what is the exam hall", "room 204", "24CS"),
]:
    out = handle(q, seeded(), NOW)
    check(must in out and mustnot not in out, repr(q), f"-> {out!r}")

for q, want in [("I'm done with the maths exam", "Marked done"), ("i am done with maths exam", "Marked done"), ("I completed the viva", "Marked done"), ("finished the viva", "Marked done"),
                ("I've finished my maths exam", "Marked done"), ("done with the viva", "Marked done"), ("mark the viva as done", "Marked done"), ("I'm done with unicorns", "couldn't find")]:
    out = handle(q, seeded(), NOW)
    check(want in out, repr(q), f"-> {out!r}")
for q, who in [("move the maths exam to the 26th", "26 Nov"), ("change the viva to saturday at 11 am", "Sat 07 Nov"), ("reschedule the maths exam to 3 december at 10 am", "Thu 03 Dec"),
               ("postpone the viva to monday", "Mon 02 Nov"), ("move the viva to twenty fourth november", "24 Nov")]:
    out = handle(q, seeded(), NOW)
    check(out.startswith("Moved") and who in out, repr(q), f"-> {out!r}")

s = seeded(); announce_due(s, NOW + timedelta(minutes=31))
out = handle("snooze for 10 minutes", s, NOW + timedelta(minutes=31)); check(out.startswith("Snoozed") and "10:41 am" in out, "snooze 10 min", out)
announce_due(s, NOW + timedelta(minutes=45)); out = handle("snooze", s, NOW + timedelta(minutes=45)); check(out.startswith("Snoozed"), "snooze default", out)
announce_due(s, NOW + timedelta(minutes=70)); out = handle("snooze it for twenty minutes", s, NOW + timedelta(minutes=70)); check(out.startswith("Snoozed"), "snooze words", out)
s = seeded(); out = handle("clear everything", s, NOW); check("Delete all" in out, "wiping everything still asks", out)
out = handle("no", s, NOW); check(out == "Cancelled, sir." and s.db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 7, "and no means no", out)
handle("clear everything", s, NOW); out = handle("yes", s, NOW); check("Cleared" in out and s.db.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0, "clear all confirmed", out)
out = handle("remind me to drink water every hour", fresh(), NOW); check("repeating" in out, "every -> honest refusal", out)
out = handle("add milk to my shopping list", fresh(), NOW); check("afraid" in out, "unsupported isn't mistaken for a list query", out)
out = handle("remind me to call mom at 9am today", fresh(), NOW); check("already passed" in out, "past time refused", out)

if __name__ == "__main__":
    print(f"I spoken-style: {ok_count}/{total}  {'PASS' if ok_count == total else 'FAIL'}")
    for f in fails:
        print("  ", f.encode("ascii", "backslashreplace").decode())
