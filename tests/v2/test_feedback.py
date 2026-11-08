"""Regressions from the owner's actual November 4 feedback. Silent, fake PC."""
import os
from pathlib import Path
import queue
import sys
import time
from types import SimpleNamespace
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).parent)]
os.environ['JARVIS_SILENT'] = '1'
import numpy as np
from harness import fresh
from jarvis2.ears import Ears, Job, SR
from jarvis2.ui import UiApp, Voice


def check(ok, name):
    assert ok, name
    print('ok', name)


app, pc, store = fresh(None)
r = app.handle('Edit My College Email, It is student.id at the rate college.edu')
check(r.ok and r.plan.source == 'phrase' and 'student.id@college.edu' in r.text, 'actual edit sentence takes direct fact path')
r = app.handle('copy that to the clipboard')
check(r.ok and pc.log[-1] == ('clipboard', 'student.id@college.edu'), 'copy that copies only the email value')
r = app.handle('change my college email to new.id@newcollege.edu')
check(r.ok and 'student.id@college.edu' not in app.handle("what's my college email").text, 'editing replaces the previous email')
r = app.handle('copy my college email to the clipboard')
check(r.ok and pc.log[-1] == ('clipboard', 'new.id@newcollege.edu'), 'named fact can be copied without a prior question')
pc.fail.add('clipboard')
check(not app.handle('copy that').ok, 'clipboard failure reported honestly')

received = []
ear = Ears(None, None, None, received.append)
ear.clock = 10
ear.arm(since=10)
ear.wake_pending = True
job = Job(np.zeros(SR, np.int16), 9.8, 11)
job.voice_a = 10.3  # actual speech begins after the name; pre-roll began before it
job.text = 'Open YouTube'
job.final_at = time.monotonic()
ear._decide(job)
check(len(received) == 1 and received[0].text == 'Open YouTube', 'pre-roll does not reject the follow-up command')
check(ear.armed_until == 0 and not ear.wake_pending, 'one accepted command consumes wake window')
ear.arm(since=10)
check(ear.decide('Yes sir. Open Edge', started=10.4)[0] == 'Open Edge', 'wake echo with different punctuation is stripped')
check(ear.decide('Yes sir', started=10.4) is None, 'wake reply itself never becomes a command')
ear.wake_pending = True
ear.armed_until = time.monotonic() + .1
ui = SimpleNamespace(voice=SimpleNamespace(ears=ear), expect_answer=False, q=queue.Queue())
UiApp._reply_over(ui)
check(ear.armed_until > time.monotonic()+7 and ear.armed_from == 10, 'full eight seconds start after the wake reply finishes')
ear.is_complete = lambda text: text.lower() == 'open youtube'
check(ear._complete('open youtube'), 'follow-up commands get early transcription completion too')
ear.armed_until = time.monotonic()-1
ear.armed_to = 18
check(ear.decide('open youtube', started=12) == ('open youtube','follow_up'), 'a command begun in time survives delayed transcription')
check(ear.decide('open youtube', started=19) is None, 'speech begun after the deadline still needs the name')

voice = Voice(SimpleNamespace(cfg={'voice_on':True,'speak_replies':True}))
voice.speak('Reminder: submit the lab record.')
said = []
voice.speaker = SimpleNamespace(speak=said.append)
voice.flush_speech(); voice.flush_speech()
check(said == ['Reminder: submit the lab record.'], 'startup reminder waits for voice and speaks exactly once')
print('FEEDBACK REGRESSIONS ALL PASSED')

# Exercise native clipboard allocation/ownership without touching the actual
# Windows clipboard (all APIs replaced, memmove writes into our own buffer).
import ctypes
from unittest.mock import patch
from jarvis2 import clipboard
class Fn:
    def __init__(self, fn): self.fn = fn
    def __call__(self, *args): return self.fn(*args)
buffer = ctypes.create_string_buffer(2048)
opened, freed, destroyed = [], [], []
fake_kernel = SimpleNamespace(GlobalAlloc=Fn(lambda *a:888), GlobalLock=Fn(lambda h:ctypes.addressof(buffer)),
                              GlobalUnlock=Fn(lambda h:True), GlobalFree=Fn(freed.append), GlobalSize=Fn(lambda h:2048))
fake_user = SimpleNamespace(CreateWindowExW=Fn(lambda *a:77), DestroyWindow=Fn(destroyed.append),
                            OpenClipboard=Fn(lambda h:(opened.append(h), True)[1]), EmptyClipboard=Fn(lambda:True),
                            CloseClipboard=Fn(lambda:True), SetClipboardData=Fn(lambda fmt,h:h if fmt==13 else 0))
fake_user.GetClipboardData = Fn(lambda fmt:888)
with patch.object(ctypes, 'windll', SimpleNamespace(user32=fake_user,kernel32=fake_kernel)):
    check(clipboard.write('student@example.edu'), 'native clipboard path reports a successful transfer')
check(opened == [77] and destroyed == [77] and not freed, 'clipboard has a real owner and transferred memory is not freed')
check(buffer.raw.startswith('student@example.edu\0'.encode('utf-16-le')), 'clipboard uses correctly terminated Unicode text')
fake_user.GetClipboardData = Fn(lambda fmt:0)
with patch.object(ctypes, 'windll', SimpleNamespace(user32=fake_user,kernel32=fake_kernel)):
    check(not clipboard.write('another@example.test'), 'clipboard success requires readable exact-value verification')
print('NATIVE CLIPBOARD SHIM PASSED')
