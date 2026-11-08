"""Ears decisions without audio: who is the sentence for? Run: py -3.12 tests/v2/test_ears.py -> failures only, then a count."""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from jarvis2.ears import Ears, name_split  # noqa: E402

FAILS, N = [], 0


def check(name, got, want):
    global N
    N += 1
    if got != want:
        FAILS.append(f"{name}: got {got!r} want {want!r}")


for text, want in [("Jarvis, open YouTube", (True, "open YouTube")), ("Hey Jarvis, open YouTube.", (True, "open YouTube")), ("to... Hey Jarvis, open YouTube", (True, "open YouTube")),
                   ("Travis open chrome", (True, "open chrome")), ("Charles, volume up", (True, "volume up")), ("open YouTube", (False, "open YouTube")),
                   ("I told Jarvis to open it yesterday", (False, "I told Jarvis to open it yesterday")), ("Jarvis", (True, ""))]:
    check("name_split " + text, name_split(text), want)

e = Ears(None, None, None, lambda h: None, hint=lambda: "Jarvis, YouTube, Edge, Chrome, WhatsApp.")
now = time.monotonic()
check("name + command", e.decide("Jarvis, close Edge", now), ("close Edge", "name"))
check("no name, not armed: ignored", e.decide("close Edge", now), None)
check("junk", e.decide("Thank you.", now), None)
check("hint read back out of noise", e.decide("Jarvis, YouTube, WhatsApp.", now), None)
check("hint echo needs only hint words", e.decide("Jarvis, open YouTube", now), ("open YouTube", "name"))
e.clock = 10.0
e.arm()                                                      # a reply just ended at sample time 10 s
check("follow-up: sentence began after the reply ended", e.decide("close Edge", now, started=10.6), ("close Edge", "follow_up"))
check("the reply's own echo (began before it ended) is not a follow-up", e.decide("Closing Edge, sir.", now, started=9.0), None)
check("armed also takes a named sentence", e.decide("Jarvis, mute", now, started=9.0), ("mute", "name"))
e.armed_until = 0
check("armed window over", e.decide("close Edge", now, started=11), None)
check("bare name", e.decide("Jarvis.", now), ("", "name"))
check("no pause (music under his voice): the name may start a sentence in the middle", e.decide("la la la you know. Jarvis, next song. And more", now, continuous=True), ("next song And more", "name"))
check("without 'no pause' a name in the middle is not for Jarvis", e.decide("I told you. Jarvis, next song", now), None)
# "Jarvis" alone, then the command spoken right over the "Yes, sir" reply
e.armed_until, e.clock = 0, 20.0
e.arm(since=19.0)
check("command spoken over the wake reply is taken", e.decide("open YouTube", now, started=19.4), ("open YouTube", "follow_up"))
check("the wake reply heard back is not a command", e.decide("Yes, sir.", now, started=20.2), None)
check("wake reply followed by the command: only the command", e.decide("Yes, sir. Open YouTube", now, started=19.5), ("Open YouTube", "follow_up"))
e.arm()                                                       # arming again while armed only extends the time
check("re-arming keeps the earlier start", e.armed_from, 19.0)
e.armed_until = 0
check("not armed after an ordinary reply: a video's speech is ignored", e.decide("peace out", now, started=30), None)


# Obsolete early transcripts must not queue extra inference ahead of a command.
import numpy as np
from jarvis2.ears import Job, SR
calls = []
def transcribe(audio, hint):
    calls.append(1)
    return 'Jarvis, close Edge'
worker = Ears(None, None, transcribe, lambda h: None)
old = Job(np.zeros(SR, np.int16), 0, 1)
old.cancelled = True
current = Job(np.zeros(SR, np.int16), 2, 3)
worker.jobs.put(old); worker.jobs.put(current)
worker.stop = True
worker._worker()
check('cancelled early work does not delay the next job', len(calls), 1)
check('all queue entries released', worker.jobs.unfinished_tasks, 0)

print("FAILED:" if FAILS else "all ok", *FAILS, sep="\n")
print(f"{N - len(FAILS)}/{N} checks")
sys.exit(1 if FAILS else 0)
