"""Replay the owner's saved wake and command through real STT, without playing sound
or opening the microphone. Exercises actual segmentation + follow-up timing.
"""
import os
from pathlib import Path
import re
import sys
import threading
import time
import wave
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
os.environ['JARVIS_SILENT'] = '1'
import numpy as np
from harness import fresh
from jarvis2.ears import Ears, Transcriber, ArraySource, SR, BLOCK_S


def read(path):
    with wave.open(str(path)) as f:
        assert f.getframerate() == SR
        return np.frombuffer(f.readframes(f.getnframes()),dtype=np.int16)


reg = ROOT/'data/feedback-audio'
reg.mkdir(exist_ok=True)
for stem, pattern in [('wake','20261104-180242-*.wav'),('command','20261104-180059-*.wav')]:
    target = reg/(stem+'.wav')
    if not target.exists():
        source = next((ROOT/'data/clips').glob(pattern), None)
        if not source:
            raise RuntimeError('Saved feedback recording missing: '+pattern)
        target.write_bytes(source.read_bytes())

stt, ears = Transcriber(), None
try:
    stt.load()
    wake, full = read(reg/'wake.wav'), read(reg/'command.wav')
    segments, _ = stt.model.transcribe(full.astype(np.float32)/32768, language='en', beam_size=1, word_timestamps=True)
    words = [word for segment in segments for word in (segment.words or [])]
    start = next(w.start for w in words if re.sub(r'\W','',w.word).lower() == 'open')
    command = full[max(0,int((start-.06)*SR)):]
    for gap in (1.1, 2.2):
        app, pc, _ = fresh(None)
        source = ArraySource(np.concatenate([np.zeros(SR//2,np.int16),wake,np.zeros(int(gap*SR),np.int16),command,np.zeros(2*SR,np.int16)]))
        original = source.read
        def slow():
            time.sleep(BLOCK_S)
            return original()
        source.read = slow
        got = []
        def heard(h):
            got.append(h)
            if not h.text:
                def reply_finished():
                    time.sleep(.6)  # simulate wake reply duration; no actual playback
                    if ears.wake_pending:
                        ears.arm(since=ears.armed_from)
                threading.Thread(target=reply_finished,daemon=True).start()
            else:
                reply = app.handle(h.text,trigger=h.trigger)
                print('gap',gap,'heard',repr(h.text),'trigger',h.trigger,'ok',reply.ok,'delivery_ms',h.wait_ms,flush=True)
        ears = Ears(source,None,stt,heard,hint=app.names.hint)
        ears.is_complete=app.is_complete
        ears.start(); ears.join(30); ears.shutdown()
        assert any(not h.text for h in got), 'wake was not heard'
        assert any(h.trigger == 'follow_up' and 'open' in h.text.lower() for h in got), 'no-name command was lost'
        assert any(x[:2] == ('open','youtube') for x in pc.log), pc.log
    print('RECORDED WAKE + FOLLOW-UP PASSED',flush=True)
finally:
    if ears:
        ears.shutdown()
    stt.unload()
