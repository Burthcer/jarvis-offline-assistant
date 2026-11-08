"""Actual owned click-through overlay above an owned Tk fixture, no screenshots."""
import os,sys,tempfile,time,ctypes,tkinter as tk
from pathlib import Path
os.environ['JARVIS_SILENT']='1';sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.choices import Choices
from jarvis3.overlay import TargetOverlay,render
root=tk.Tk();root.title('V3 owned overlay fixture');root.geometry('700x440+120+120');root.update()
u=ctypes.windll.user32;u.GetForegroundWindow.restype=ctypes.c_void_p
u.GetWindowLongW.argtypes=[ctypes.c_void_p,ctypes.c_int]
u.SendMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t];u.SendMessageW.restype=ctypes.c_ssize_t
u.IsWindow.argtypes=[ctypes.c_void_p]
overlay=None
try:
    x,y=root.winfo_rootx(),root.winfo_rooty()
    values=[dict(id=str(i),title=f'Test mix {i}',bounds=(x+20+(i%2)*260,y+40+(i//2)*130,x+250+(i%2)*260,y+130+(i//2)*130),visible=True,enabled=True,group='mixes') for i in range(4)]
    snap=Choices().capture(('owned',),'mixes',values,(x,y,x+700,y+440));before=u.GetForegroundWindow()
    overlay=TargetOverlay();overlay.show(snap,snap.items[1].identity)
    end=time.monotonic()+2
    while not overlay.frames and time.monotonic()<end:root.update();time.sleep(.01)
    assert overlay.frames and not overlay.error,overlay.error
    assert u.GetForegroundWindow()==before,'overlay stole focus'
    flags=u.GetWindowLongW(overlay.hwnd,-20)
    assert flags&0x20 and flags&0x8000000 and flags&0x80000,'overlay input/transparency flags missing'
    assert u.SendMessageW(overlay.hwnd,0x84,0,0)==-1,'painted overlay would intercept clicks'
    image,position=render(snap,snap.items[1].identity)
    out=Path(__file__).resolve().parents[2]/'data/v3-dev-checks/target-overlay.png';image.save(out)
    handle=overlay.hwnd;overlay.close();assert not overlay.thread.is_alive() and not u.IsWindow(handle),'overlay leaked its window/thread'
    print('NATIVE OVERLAY: numbers/target render, no focus, click-through, exact own-window/thread cleanup passed',flush=True)
finally:
    if overlay:overlay.close()
    root.destroy()
