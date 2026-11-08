"""Run: py -3.12 tests\\test_store.py   (prints OK if everything passes)"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jarvis.core import announce_due, handle
from jarvis.store import Store
from jarvis.timeparse import parse_when

NOW = datetime(2026, 10, 31, 10, 0)  # a Saturday


def p(s):
    return parse_when(s, NOW)


assert p("buy milk tomorrow at 5pm") == ("buy milk", datetime(2026, 11, 1, 17, 0))
assert p("call mom in 2 hours") == ("call mom", datetime(2026, 10, 31, 12, 0))
assert p("call mom in half an hour") == ("call mom", datetime(2026, 10, 31, 10, 30))
assert p("maths exam on 23 november") == ("maths exam", datetime(2026, 11, 23, 9, 0))
assert p("maths exam on November 23rd") == ("maths exam", datetime(2026, 11, 23, 9, 0))
assert p("submit report on monday") == ("submit report", datetime(2026, 11, 2, 9, 0))
assert p("pay fees on 5 oct") == ("pay fees", datetime(2027, 10, 5, 9, 0))
assert p("take medicine at 8am") == ("take medicine", datetime(2026, 11, 1, 8, 0))
assert p("gym at 6:30 pm") == ("gym", datetime(2026, 10, 31, 18, 30))
assert p("study tonight") == ("study", datetime(2026, 10, 31, 21, 0))
assert p("just a note") == ("just a note", None)
assert p("to check the oven in 10 minutes") == ("check the oven", datetime(2026, 10, 31, 10, 10))
assert p("leave in 2 hours and 30 minutes") == ("leave", datetime(2026, 10, 31, 12, 30))
assert p("pay rent on the 1st of december") == ("pay rent", datetime(2026, 12, 1, 9, 0))

s = Store(":memory:")
r = lambda x: handle(x, s, NOW)
assert r("Hey Jarvis, remind me about my maths exam on 23 november").startswith("Noted")
assert r("remind me maths exam on 25 november").startswith("Updated")      # no duplicate
assert r("remind me about the exam on 26 november").startswith("Updated")  # shorter wording merges too
assert len(s.upcoming(NOW)) == 1 and s.upcoming(NOW)[0]["due"].startswith("2026-11-26")
assert s.upcoming(NOW)[0]["text"] == "My maths exam"                            # detailed name kept
assert r("remind me to call mom").startswith("When")                        # no time -> asks
assert r("remind me to buy milk today at 5pm").startswith("Noted")
assert "buy milk" in r("what do we got to do today").lower()
assert "Nothing" in r("what did I miss yesterday")
assert r("remember that my locker code is 4821").startswith("Remembered")
assert "4821" in r("what do you remember about locker")
# Named reminder cancellation is immediate (the current, agreed behaviour).
assert "Cancelled" in r("delete buy milk") and not s.find("buy milk") and s.pending is None

later = datetime(2026, 11, 26, 9, 5)  # exam time has passed
assert announce_due(s, later) and not announce_due(s, later)               # spoken once only
assert "exam" in handle("what did I miss", s, later).lower()
assert "Marked done" in handle("done exam", s, later)
assert "Nothing missed" in handle("what did I miss", s, later)
s2 = Store(":memory:"); handle("remind me about physics exam on 24 nov", s2, NOW); handle("remember my wifi password is abc123", s2, NOW)
assert "abc123" in handle("what is my wifi password", s2, NOW)
assert "Marked done" in handle("mark physics exam as done", s2, NOW)
print("OK")
