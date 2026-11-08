"""Actual existing planner model, fake PC, no voice or screen."""
import os
from pathlib import Path
import sys
import time
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).parent)]
os.environ['JARVIS_SILENT'] = '1'
from harness import fresh
from jarvis2.ai import AI, CHAT_MODEL
from jarvis2.organizer import rows

class TraceAI(AI):
    def complete(self, *args, **kw):
        output = super().complete(*args, **kw)
        print('Planner raw:', repr(output), flush=True)
        return output

brain = TraceAI(CHAT_MODEL, n_ctx=2048)
try:
    for request in ('open notepad and set a timer for 10 minutes', 'open youtube and set the volume to 20'):
        app, pc, _ = fresh(None)
        app.chat_ai = brain
        t = time.perf_counter()
        r = app.handle('plan: ' + request)
        print(request, '=>', r.text, round((time.perf_counter()-t)*1000), 'ms', flush=True)
        assert r.plan.kind == 'ask' and app.pending and not pc.log
        r = app.handle('yes')
        assert r.ok and rows(app.memory, 'jobs')[0]['state'] == 'done', r.text
        print('Finished on fake PC:', pc.log, flush=True)
finally:
    brain.unload()
