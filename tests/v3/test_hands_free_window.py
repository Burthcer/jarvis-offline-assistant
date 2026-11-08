"""Fake speech checks for the hands-free window and its short reply timer."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.ears import Ears

ear = Ears(None, None, None, lambda _: None)
ear.followup_filter = lambda text, **_: text.lower().strip('.') == 'open youtube'
ear.hands_free_s = 180
with patch('jarvis3.engine.ears.time.monotonic', return_value=100):
    ear.arm(180, since=0)
    ear.hands_free_until = ear.armed_until
with patch('jarvis3.engine.ears.time.monotonic', return_value=105):
    ear.arm(since=0)
assert ear.armed_until == 280
assert ear.decide('Open YouTube.', now=160, started=50)[1] == 'follow_up'
assert ear.decide('Room conversation.', now=160, started=50) is None
assert ear.decide('Open YouTube.', now=281, started=181) is None
ear.end_hands_free()
assert not ear.hands_free_active(now=161)
assert ear.decide('Open YouTube.', now=161, started=51) is None
assert ear.decide('Jarvis, open YouTube.', now=161, started=51)[1] == 'name'
ear.shutdown()
print('PASS hands-free survives short reply arming and ends on expiry or cancellation')
