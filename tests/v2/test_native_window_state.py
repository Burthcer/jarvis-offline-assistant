"""Only our exact subprocess window is minimized/maximized/restored."""
import os, sys, subprocess, time, ctypes
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from jarvis.actions import Real
from jarvis2.window_control import change
b=Real()
child=subprocess.Popen([sys.executable,'-c',"import tkinter as t; w=t.Tk(); w.title('Jarvis owned state fixture'); t.Label(w,text='Own disposable window').pack(); w.mainloop()"],cwd=ROOT)
try:
    end=time.monotonic()+8
    windows=[]
    while not windows and time.monotonic()<end:
        windows=b._process_windows({child.pid}); time.sleep(.05)
    assert windows,'own window missing'
    hwnd=windows[0]
    for action in ('minimize','restore','maximize','restore'):
        assert change(hwnd,action), action
        assert child.poll() is None,'window action terminated the process'
        print('Verified own window:',action,flush=True)
finally:
    child.terminate(); child.wait(timeout=5)
