"""Real native placement/rollback on ONE owned Tk window, no user windows touched."""
import os,sys,time,threading,ctypes,tkinter as tk
from pathlib import Path
os.environ['JARVIS_SILENT']='1';sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.osapi import Real
from jarvis3.window_undo import capture
from jarvis3.engine.window_control import change
root=tk.Tk();root.title('V3 owned window rollback fixture');root.geometry('620x360+140+140');root.update()
second=tk.Toplevel(root);second.title('V3 owned second rollback fixture');second.geometry('420x280+820+140');root.update()
u=ctypes.windll.user32;u.GetAncestor.argtypes=[ctypes.c_void_p,ctypes.c_uint];u.GetAncestor.restype=ctypes.c_void_p
handle=u.GetAncestor(root.winfo_id(),2)
other=u.GetAncestor(second.winfo_id(),2)
pid=ctypes.c_ulong();u.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];u.GetWindowThreadProcessId(handle,ctypes.byref(pid));assert pid.value==os.getpid()
pc=Real();pc.window_handles=lambda target:[handle]
failure=[];done=threading.Event()
def work():
    try:
        for action in ('minimize','maximize'):
            original=capture([handle]);n,total,undo=pc.window_transition(action,'owned fixture')
            assert (n,total)==(1,1) and undo and capture([handle])!=original
            result=undo()
            assert result.ok and capture([handle])==original,(action,result.plain,original,undo.after,capture([handle]))
        assert change(handle,'maximize')
        original=capture([handle]);n,total,undo=pc.window_transition('restore','owned fixture')
        assert n==1 and undo and undo().ok and capture([handle])==original
        _,_,undo=pc.window_transition('minimize','owned fixture');assert undo
        assert change(handle,'restore')
        assert not undo().ok,'later user change was overwritten'
        assert u.IsWindow(ctypes.c_void_p(handle)),'undo closed the window'
        pc.window_handles=lambda target:[handle,other]
        before=capture([handle,other]);n,total,undo=pc.window_transition('minimize','owned two windows')
        result=undo()
        assert (n,total)==(2,2) and result.ok and capture([handle,other])==before,((n,total),result.plain,before,undo.after,capture([handle,other]))
        _,_,undo=pc.window_transition('minimize','owned two windows')
        assert change(handle,'restore')
        later=capture([handle,other])
        assert not undo().ok and capture([handle,other])==later,'batch undo overwrote a later state change'
    except Exception as ex:failure.append(ex)
    finally:done.set()
thread=threading.Thread(target=work);thread.start()
try:
    deadline=time.monotonic()+15
    while not done.is_set() and time.monotonic()<deadline:root.update();time.sleep(.005)
    assert done.is_set(),'owned window test timed out'
    thread.join(1)
    if failure:raise failure[0]
    print('NATIVE WINDOW UNDO: exact own-window position/state for minimize/maximize/restore and later-change refusal passed')
finally:root.destroy()
