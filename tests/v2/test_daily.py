"""Daily commands stay fast even when Windows media properties stall. No sound or real apps."""
import os
import sys
sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), os.path.dirname(__file__)]
from harness import fresh

app, pc, store = fresh(None)
def blocked():
    raise AssertionError('unrelated command read Windows media')
pc.media_state = blocked
for command in ('Close, WhatsApp.', 'open youtube', 'shut up', 'fuck off'):
    reply = app.handle(command)
    assert reply.ok, (command, reply.text)
for command in ('Could you open up YouTube?', 'Hey Jarvis, can you open YouTube?'):
    assert app.handle(command).plan.source == 'shape', command
assert app.speech.stopped == 2
address = 'Student.Name+college@gmail.com'
assert app.handle('remember my Gmail is ' + address).ok
assert address in app.handle('what is my Gmail').text
assert not any(address in r['text'] for r in store.upcoming(app.clock()))
assert app.handle('I am a CS student').ok
assert 'CS student' in app.handle('what do you know about me').text
assert app.handle('shut down').ok and app.exit_requested
print('Daily commands: all passed; no AI, no Windows media reads, email preserved, facts separate.')
