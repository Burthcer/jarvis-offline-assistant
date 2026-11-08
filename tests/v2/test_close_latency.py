"""Close only our own uniquely named throwaway Tk process. No real user app."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ['JARVIS_SILENT'] = '1'
import psutil
from jarvis.actions import Real
from jarvis2.osapi import Real as AppOS

exe = ROOT/'data/runtime'/f'JarvisCloseCheck{os.getpid()}.exe'
shutil.copy2(sys.executable, exe)
backend = Real()
try:
    for blocked in (False, True):
        source = "import tkinter as t; w=t.Tk(); w.title('Jarvis own close test'); t.Label(w,text='Throwaway test window').pack(); "
        if blocked:
            source += "w.protocol('WM_DELETE_WINDOW',lambda:None); "
        source += 'w.mainloop()'
        child = subprocess.Popen([str(exe), '-c', source], cwd=ROOT, env={**os.environ,'JARVIS_SILENT':'1'})
        try:
            end = time.monotonic()+10
            while not backend._process_windows({child.pid}) and time.monotonic()<end:
                assert child.poll() is None, 'test window exited before ready'
                time.sleep(.05)
            assert backend._process_windows({child.pid}), 'own test window not ready'
            assert Path(psutil.Process(child.pid).exe()).resolve() == exe.resolve()
            start = time.perf_counter()
            ok, was = AppOS().close(exe.stem.lower(), 'app')
            elapsed = round((time.perf_counter()-start)*1000)
            print('Close blocked dialog' if blocked else 'Close normal window', ok, was, elapsed, 'ms',flush=True)
            assert was and ok == (not blocked)
            if blocked:
                assert child.poll() is None, 'blocked window must never be forced closed'
            else:
                child.wait(timeout=3)
                assert elapsed < 750, 'normal close still has an artificial wait'
        finally:
            if child.poll() is None:
                child.terminate()  # exact Popen-owned child; never user apps
            child.wait(timeout=5)
finally:
    exe.unlink(missing_ok=True)
print('OWN-WINDOW CLOSE CHECK PASSED')
