"""Real-use regressions: first follow-up, media wording, and editable facts.
No models, microphone, sound, clipboard or real app actions.
"""
import os
import queue
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ['JARVIS_SILENT'] = '1'
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).parent)]
from harness import fresh
from jarvis2.ears import Ears, Heard
from jarvis2.ui import UiApp, Voice, Api

fails = []
def check(ok, title):
    print(('ok ' if ok else 'FAIL ') + title)
    if not ok:
        fails.append(title)

# Exercise the actual UI's question path, not just Ears.arm in isolation.
engine, pc, store = fresh(SimpleNamespace(complete=lambda *a, **k: 'ASK: Which app, sir?'))
u = UiApp.__new__(UiApp)
u.engine, u.store, u.q = engine, store, queue.Queue()
u.cfg = {'voice_on': True, 'speak_replies': True}
u.voice = Voice(u)
e = u.voice.ears = Ears(None, None, None, lambda h: None)
e.clock = 10
u._add = lambda *a: None
u.state = lambda *a: None
u.say = lambda text, *a: u.voice.speak(text)
u.expect_answer = False
u.voice.speaker = SimpleNamespace(speak=lambda text: None, stop=lambda: None)
UiApp._voice_msg(u, 'heard', Heard('unclear', 'name', '', 8, 9))
check(e.decide('Close WhatsApp.', started=10.1) == ('Close WhatsApp.', 'follow_up'), 'first answer accepted while clarification is still speaking')
check(e.decide('Which app sir?', started=10.1) is None, 'clarification echo never consumes listening window')
UiApp._reply_over(u)
check(e.decide('Close WhatsApp.', started=10.1) == ('Close WhatsApp.', 'follow_up'), 'reply completion does not move listening start forward')

for text, action, count in [
    ('next', 'next', 1), ('play the next song', 'next', 1),
    ('the next song', 'next', 1), ('next one', 'next', 1),
    ('next next', 'next', 2), ('next twice', 'next', 2),
    ('skip two songs', 'next', 2), ('play the second next song', 'next', 2),
    ('next second song', 'next', 2), ('go back two tracks', 'previous', 2),
    ('previous twice', 'previous', 2), ('play the previous song', 'previous', 1),
    ('next song twice', 'next', 2), ('previous track three times', 'previous', 3),
]:
    app, pc, _ = fresh(None)
    r = app.handle(text)
    check(r.ok and r.plan.source == 'phrase' and pc.log.count(('media', action)) == count, f'{text}: exactly {count} {action} commands, no AI wait')

for raw in ('media(action="next", count=2)', 'media(action="next", count=99)'):
    app, pc, _ = fresh(SimpleNamespace(complete=lambda *a, out=raw, **k:out))
    app.handle('move to another song')
    check(not pc.log, 'AI cannot invent a skip count: '+raw)
app, pc, _ = fresh(None)
attempts = []
def reject_second(action):
    attempts.append(action)
    return len(attempts) == 1, pc.playing
pc.media = reject_second
r = app.handle('next three songs')
check(not r.ok and len(attempts) == 2 and '1 of 3' in r.text, 'multi-skip stops at rejection and reports partial completion')

# A delayed on-idle callback cannot reopen a consumed question window.
e.armed_until = 0
u.expect_answer = True
UiApp._reply_over(u)
check(e.armed_until == 0, 'an old reply finishing cannot reopen a consumed window')
e.clock = 30; e.arm(since=29)
e.remember_reply('Which app, sir?')
check(e.decide('Which app sir? Close WhatsApp.', started=30.1) == ('Close WhatsApp.', 'follow_up'), 'question and answer in one transcript retain only the answer')
check(e.decide('Jarvis, uh...', started=30.1) == ('', 'name'), 'name plus hesitation keeps listening')
e.armed_until = 0
check(e.decide('next song', started=31) is None, 'ordinary no-name room speech is still ignored outside a listening window')

# OS calls are mocked below; never focus a real app or control a real player.
import asyncio
from jarvis2.osapi import Real
from jarvis import actions
backend = SimpleNamespace(running=lambda:['Antigravity.exe'], _process_windows=lambda pids:[123] if pids == {7} else [],
                          _windows=lambda predicate: [], _front=lambda h:h == 123)
real = Real()
with patch.object(actions, 'backend', backend), patch('psutil.process_iter', return_value=[SimpleNamespace(info={'pid':7,'name':'Antigravity.exe'})]):
    check(real.focus('antigravity', 'app', wait=0), 'focus finds app by its program when its title contains only the project')

class Session:
    source_app_user_model_id = 'fake-player'
    playing = True
    calls = []
    def get_playback_info(self): return SimpleNamespace(playback_status=4 if self.playing else 5)
    async def try_skip_next_async(self): self.calls.append('next'); return True
    async def try_skip_previous_async(self): self.calls.append('previous'); return True
    async def try_play_async(self): self.playing=True; return True
    async def try_pause_async(self): self.playing=False; return True
session = Session()
real._session = lambda fn: asyncio.run(fn(session))
with patch('jarvis2.osapi.time.sleep', side_effect=AssertionError('unnecessary fixed wait')):
    t = time.perf_counter(); ok, state = real.media('next'); elapsed = time.perf_counter()-t
    check(ok and elapsed < .1 and session.calls == ['next'], 'acknowledged skip has no fixed 300ms wait or extra player lookup')
    check(real.media('pause')[1]['playing'] is False, 'pause still checks actual playback state')

app, pc, store = fresh(None)
calls = []
original_running = pc.running_names
pc.running_names = lambda catalog: (calls.append(1), original_running(catalog))[1]
pc.media_state = lambda: (_ for _ in ()).throw(AssertionError('unneeded media query'))
check(app.handle('open youtube').ok and len(calls) == 1, 'app command scans running programs once, not twice')

app, pc, store = fresh(None)
for note in store.notes(''):
    store.delete(note['id'])  # remove only this harness's seeded dummy facts
api = Api(SimpleNamespace(store=store, engine=app, q=queue.Queue(), snapshot=lambda:{}))
check(api.save_fact(None, 'college email', 'one@college.test')['ok'], 'add first fact')
check(api.save_fact(None, 'personal Gmail', 'two@gmail.test')['ok'] and len(store.notes('')) == 2, 'add Gmail without overwriting college email')
row = store.notes('personal Gmail')[0]
check(api.save_fact(row['id'], 'work email', 'work@example.test')['ok'], 'rename heading and replace value together')
check('work@example.test' in app.handle('what is my work email').text, 'voice recall uses the edited heading and value')
check(not api.save_fact(None, 'work email', 'oops@example.test')['ok'], 'duplicate heading is shown as an error, not silent overwrite')
check(api.copy_note(row['id']) and pc.log[-1] == ('clipboard','work@example.test'), 'renamed fact copies only its value')
before = len(store.notes(''))
check(api.save_fact(None, '', 'I enjoy reading science books')['ok'] and api.save_fact(None, '', 'I enjoy reading history books')['ok'] and len(store.notes('')) == before + 2, 'explicit Add keeps separate similar notes')
check(not api.save_fact(None, 'blank', ' ')['ok'] and not api.save_fact(None, 'x'*61, 'value')['ok'], 'empty and oversized fields are refused')
timer = store.add('timer', kind='timer')[0]
check(not api.save_fact(timer['id'], 'work email', 'bad')['ok'], 'fact editor cannot change a timer')

import tempfile
from jarvis.store import Store
with tempfile.TemporaryDirectory(prefix='jarvis-facts-check-') as folder:
    path = str(Path(folder)/'facts.db')
    saved = Store(path)
    api = Api(SimpleNamespace(store=saved, engine=app, q=queue.Queue(), snapshot=lambda:{}))
    api.save_fact(None, 'personal Gmail', 'first@example.test')
    saved_id = saved.notes('')[0]['id']
    api.save_fact(saved_id, 'work email', 'new@example.test')
    saved.db.close()
    reopened = Store(path)
    check([r['text'] for r in reopened.notes('')] == ['my work email is new@example.test'], 'new heading and value survive database close/reopen')
    reopened.db.close()
print(f'{len(fails)} failures')
sys.exit(bool(fails))
