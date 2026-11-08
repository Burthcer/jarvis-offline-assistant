"""the owner's recorded, name-free Close WhatsApp, once, during a clarification.
Real segmentation/STT and UI question handling; fake PC, no mic or sound.
"""
import os
import queue
import sys
import time
import wave
from pathlib import Path
from types import SimpleNamespace

os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
import numpy as np
import psutil
from harness import fresh
from jarvis2.ears import ArraySource, BLOCK_S, Ears, Heard, SR, Transcriber
from jarvis2.ui import UiApp, Voice

target = ROOT / 'data/feedback-audio/close-whatsapp-followup.wav'
target.parent.mkdir(exist_ok=True)
if not target.exists():
    source = next((ROOT / 'data/clips').glob('20261104-185201-*.wav'))
    target.write_bytes(source.read_bytes())
with wave.open(str(target)) as f:
    assert f.getframerate() == SR
    audio = np.frombuffer(f.readframes(f.getnframes()), np.int16)

stt, ears = Transcriber(), None
try:
    stt.load()
    for gap in (.2, .8):
        engine, pc, store = fresh(SimpleNamespace(complete=lambda *a, **k:'ASK: Which app, sir?'))
        u = UiApp.__new__(UiApp)
        u.engine, u.store, u.q = engine, store, queue.Queue()
        u.cfg = {'voice_on':True, 'speak_replies':True}
        u.voice = Voice(u)
        u._add = lambda *a:None
        u.state = lambda *a:None
        u.say = lambda text, *a:u.voice.speak(text)
        u.expect_answer = False
        u.voice.speaker = SimpleNamespace(speak=lambda text:None, stop=lambda:None)
        got = []
        def heard(h):
            got.append(h)
            UiApp._voice_msg(u, 'heard', h)
            print('gap', gap, 'heard', repr(h.text), 'trigger', h.trigger, 'delivery_ms', h.wait_ms, flush=True)
        source = ArraySource(np.concatenate([np.zeros(int(gap*SR),np.int16), audio, np.zeros(SR,np.int16)]))
        original = source.read
        def slow():
            time.sleep(BLOCK_S)
            return original()
        source.read = slow
        ears = u.voice.ears = Ears(source, None, stt, heard, hint=engine.names.hint)
        ears.is_complete = engine.is_complete
        # The question is still speaking until explicitly completed below.
        # Previous code never armed the ears at this point; first answer lost.
        UiApp._voice_msg(u, 'heard', Heard('unclear', 'name', '', 0, 0))
        assert u.expect_answer and ears.armed_until > 0
        ears.start(); ears.join(20); ears.shutdown()
        assert len(got) == 1 and got[0].trigger == 'follow_up', got
        assert pc.log.count(('close','whatsapp','app')) == 1, pc.log
        UiApp._reply_over(u)
        assert ears.armed_until == 0, 'old question must not reopen listening'
    print('QUESTION FOLLOW-UP REPLAY PASSED; RAM_MB', round(psutil.Process().memory_info().rss/1024**2), flush=True)
    import subprocess
    print(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu,utilization.gpu','--format=csv,noheader'], text=True).strip(), flush=True)
finally:
    if ears:
        ears.shutdown()
    stt.unload()
