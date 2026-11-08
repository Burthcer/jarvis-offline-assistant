"""Silent, bounded memory measurement of the SAME answer model. No PC actions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ['JARVIS_SILENT'] = '1'
import psutil
from jarvis.brain import _dlls
from jarvis2.ai import CHAT_MODEL

def gpu():
    return subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used,temperature.gpu', '--format=csv,noheader,nounits'], text=True).strip()

_dlls()
from llama_cpp import Llama
stats = []
try:
    for name, opts in [('current', {}), ('compact_buffers', {'n_batch':128, 'n_ubatch':128, 'flash_attn':True})]:
        model = None
        try:
            t = time.perf_counter()
            model = Llama(model_path=CHAT_MODEL, n_gpu_layers=-1, n_ctx=2048, use_mmap=False, verbose=False, **opts)
            load = round(time.perf_counter()-t,2)
            t = time.perf_counter()
            out = model.create_chat_completion([{'role':'user','content':'Explain how to prepare for a college exam in two short sentences.'}], temperature=0, max_tokens=90)
            item = {'mode':name, 'load_s':load, 'answer_s':round(time.perf_counter()-t,2), 'gpu_MiB_temp_C':gpu(), 'ram_GB':round(psutil.Process().memory_info().rss/2**30,2), 'answer':out['choices'][0]['message']['content']}
            stats.append(item)
            print(json.dumps(item), flush=True)
        finally:
            if model:
                model.close()
        if int(gpu().split(',')[-1].strip()) > 80:
            print('Stopped measurement to let the GPU cool.', flush=True)
            break
finally:
    print('After cleanup:', gpu(), flush=True)
    Path('data/model-memory-check.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
