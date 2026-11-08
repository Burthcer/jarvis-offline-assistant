"""Silent recorded-voice replay and resident-resource check. Never opens the mic.
This measures a recording at real speed, not a live human conversation.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
os.environ['JARVIS_SILENT'] = '1'
import numpy as np
import psutil
from harness import fresh
from jarvis2.ai import AI, CHAT_MODEL
from jarvis2.ears import ArraySource, Ears, Transcriber, BLOCK_S, SR
from jarvis2.speaker import Speaker


def resources(label):
    raw = subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu,utilization.gpu','--format=csv,noheader,nounits'], text=True).strip()
    item = {'stage':label, 'gpu_MiB_temp_C_load_percent':raw, 'ram_GB':round(psutil.Process().memory_info().rss/2**30,2)}
    print(json.dumps(item), flush=True)
    return item


app, pc, store = fresh(AI())
app.chat_ai = AI(CHAT_MODEL, n_ctx=2048)
stt, speaker, ears = Transcriber(), Speaker(), None
stats = []
try:
    stt.load()
    speaker.load()
    app.ai.load()
    stats.append(resources('speech, voice and action model ready'))
    clip = ROOT/'data/clips/20261104-132149-64672.wav'
    with wave.open(str(clip)) as w:
        assert w.getframerate() == SR
        audio = np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16)
    for i in range(2):
        src = ArraySource(np.concatenate([np.zeros(SR//2, np.int16), audio, np.zeros(2*SR, np.int16)]))
        original = src.read
        def realtime():
            time.sleep(BLOCK_S)
            return original()
        src.read = realtime
        got = []
        def heard(h):
            t = time.perf_counter()
            reply = app.handle(h.text, trigger=h.trigger)
            item = {'replay':i+1,'heard':h.raw,'stt_ms':h.stt_ms,'end_to_delivery_ms':h.wait_ms,
                    'action_ms':round((time.perf_counter()-t)*1000),'source':reply.plan.source,'ok':reply.ok}
            got.append(item)
            print(json.dumps(item), flush=True)
        ears = Ears(src, None, stt, heard, hint=app.names.hint)
        ears.is_complete = app.is_complete
        ears.start()
        ears.join(30)
        ears.shutdown()
        stats.extend(got)
        assert got and got[-1]['ok'], 'recorded command not understood'
    # Same answer model, exclusive residency. Speech remains loaded and ready.
    app.chat_ai.load()
    stats.append(resources('speech, voice and answer model ready'))
    output = app.chat_ai.complete([{'role':'user','content':'Explain one way to prepare for an exam in one sentence.'}], temperature=0, max_tokens=60)
    print('Answer:',output,flush=True)
    stats.append(resources('after answer'))
    app.ai.load()
    stats.append(resources('back to action model'))
finally:
    if ears:
        ears.shutdown()
    speaker.shutdown()
    stt.unload()
    app.ai.unload()
    app.chat_ai.unload()
    stats.append(resources('all models closed'))
    (ROOT/'data/voice-daily-check.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
