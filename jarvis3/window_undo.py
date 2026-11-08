"""Exact-state window placement rollback; never closes a window or app."""
import ctypes,time
from ctypes import wintypes as w
from dataclasses import dataclass,field
import psutil

@dataclass
class CheckedUndo:
    read:object
    restore:object
    before:object
    after:object
    def __call__(self):
        from .engine.registry import Result
        try:
            if self.read()!=self.after:return Result(False,'That window changed afterwards, sir.',exact=True)
            self.restore(self.before)
            ok=self.read()==self.before
            return Result(ok,'Undone, sir.' if ok else 'I could not fully restore that window, sir.',exact=True)
        except Exception:return Result(False,'I could not safely restore that window, sir.',exact=True)

class Placement(ctypes.Structure):
    _fields_=[('length',w.UINT),('flags',w.UINT),('show',w.UINT),('minimum',w.POINT),('maximum',w.POINT),('normal',w.RECT)]

@dataclass(frozen=True)
class Pose:
    hwnd:int
    pid:int
    started:float
    flags:int
    show:int
    normal:tuple
    # Windows changes these bookkeeping positions when minimising/restoring.
    # They are retained for restoration but are not user movement/size evidence.
    minimum:tuple=field(compare=False)
    maximum:tuple=field(compare=False)

def api():
    u=ctypes.windll.user32
    u.IsWindow.argtypes=[w.HWND]
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    u.GetWindowPlacement.argtypes=[w.HWND,ctypes.POINTER(Placement)]
    u.SetWindowPlacement.argtypes=[w.HWND,ctypes.POINTER(Placement)]
    return u

def capture(handles):
    u=api();result=[]
    for hwnd in handles:
        pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        p=Placement();p.length=ctypes.sizeof(p)
        if not u.IsWindow(hwnd) or not pid.value or not u.GetWindowPlacement(hwnd,ctypes.byref(p)):raise ValueError('Window no longer available')
        # RESTORETOMAXIMIZED matters only while minimised; Windows can leave a
        # stale copy set on a normal window and clear it on the next restore.
        flags=p.flags & 2 if p.show==2 else 0
        result.append(Pose(hwnd,pid.value,psutil.Process(pid.value).create_time(),flags,p.show,(p.normal.left,p.normal.top,p.normal.right,p.normal.bottom),(p.minimum.x,p.minimum.y),(p.maximum.x,p.maximum.y)))
    return tuple(result)

def restore(before,expected):
    handles=[r.hwnd for r in before]
    if capture(handles)!=expected:raise ValueError('Windows changed after the action')
    u=api()
    for old,after in zip(before,expected):
        current=capture([old.hwnd])
        if current==(old,):continue # restoring an owner can also restore its owned windows
        if current!=(after,):raise ValueError('Window changed during rollback')
        p=Placement();p.length=ctypes.sizeof(p);p.flags=old.flags;p.show=old.show
        p.minimum=w.POINT(*old.minimum);p.maximum=w.POINT(*old.maximum);p.normal=w.RECT(*old.normal)
        if not u.SetWindowPlacement(old.hwnd,ctypes.byref(p)):raise ValueError('Window restoration refused')
    end=time.monotonic()+.6
    while capture(handles)!=before:
        if time.monotonic()>=end:raise ValueError('Window restoration not verified')
        time.sleep(.015)

def transition(osapi,action,target):
    from .engine.window_control import change
    handles=osapi.window_handles(target)
    before=None
    try:before=capture(handles)
    except Exception:pass # explicit action still works; this attempt has no undo
    done=sum(change(h,action) for h in handles)
    undo=None
    if before:
        try:
            after=capture(handles)
            if after!=before:undo=CheckedUndo(lambda:capture(handles),lambda state:restore(state,after),before,after)
        except Exception:pass
    return done,len(handles),undo
