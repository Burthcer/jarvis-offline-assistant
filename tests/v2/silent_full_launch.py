"""Real window/mic/models, fake OS and disposable data. No audio or real actions.
Parent owns the exact child PID and always closes only its own process tree.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['JARVIS_SILENT'] = '1'
import psutil

def gpu():
    return subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip()

if '--child' in sys.argv:
    import webview
    from jarvis.store import Store
    from jarvis2.memory import Memory
    from jarvis2.osapi import Fake
    from jarvis2 import ui
    import numpy as np
    from jarvis2.ears import BLOCK,BLOCK_S
    class SilentMic:
        def read(self):
            time.sleep(BLOCK_S)
            return np.zeros(BLOCK,np.int16)
    ui.MicStream=lambda *a:SilentMic()
    ui.LoopRing=lambda:None
    temporary = tempfile.mkdtemp(prefix='jarvis-live-check-')
    real_store, real_memory = Store, Memory
    ui.Real = Fake
    ui.Store = lambda p: real_store(os.path.join(temporary,'store.db'))
    ui.Memory = lambda *a: real_memory(os.path.join(temporary,'memory.db'), os.path.join(temporary,'settings.json'))
    os.chdir(temporary)
    app = ui.UiApp(gui=True, tray=False)
    def check():
        try:
            limit = time.monotonic()+50
            while app.booting and time.monotonic()<limit:
                time.sleep(.2)
            assert not app.booting and app.voice.ears, 'voice failed to start'
            assert app.page_ready, 'voice loaded but actual UI page did not connect'
            assert app.window.evaluate_js("document.title === 'Jarvis' && !!document.getElementById('input')"), 'WebView loaded an error page'
            app.voice.ears.paused_until = float('inf') # device open, no private speech processed
            proc=psutil.Process()
            def measure(label):
                ram=proc.memory_info().rss+sum(p.memory_info().rss for p in proc.children(recursive=True) if p.is_running())
                print(label,'GPU MiB/C/%:',gpu(),'RAM incl window GB:',round(ram/2**30,2),flush=True)
            measure('Window + voice + action model')
            app.set_theme('dark')
            time.sleep(1)
            measure('Animated dark mode + voice')
            app.engine.chat_ai.load()
            measure('Window + voice + answer model')
            app.engine.chat_ai.complete([{'role':'user','content':'Say ready.'}],max_tokens=10)
            measure('After answer')
            Path(os.environ['JARVIS_LAUNCH_RESULT']).write_text('ok', encoding='utf-8')
            print('FULL LAUNCH OK',flush=True)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            app.q.put('quit')
    threading.Thread(target=check,daemon=True).start()
    ui.launch(app)
else:
    marker = Path(tempfile.mkdtemp(prefix='jarvis-launch-result-'))/'result.txt'
    p=subprocess.Popen([sys.executable,'-u',str(Path(__file__).resolve()),'--child'],cwd=ROOT,env={**os.environ,'JARVIS_SILENT':'1','JARVIS_LAUNCH_RESULT':str(marker)})
    proc=psutil.Process(p.pid)
    owned=[]
    try:
        for _ in range(150):
            if p.poll() is not None:
                break
            try:
                owned=proc.children(recursive=True)
            except psutil.NoSuchProcess:
                break
            time.sleep(.5)
    finally:
        if p.poll() is None:
            try:
                owned=proc.children(recursive=True)
            except psutil.NoSuchProcess:
                pass
            proc.terminate()
        p.wait(timeout=10)
        for child in owned:
            try:
                if child.is_running():
                    child.terminate()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(owned,timeout=5)
        print('Child closed. Graphics after cleanup:',gpu(),flush=True)
    assert marker.exists() and marker.read_text(encoding='utf-8') == 'ok', 'Actual UI/model startup verification failed; see child output above'
