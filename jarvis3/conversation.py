"""Bounded conversations; no perpetual name-free room-command mode."""
import re,time,threading
DISMISS=re.compile(r"^(?:please\s+)?(?:dismiss(?:ed)?|let it go|never\s?mind|forget it|nothing(?: right now)?|that['’]?s all|that is all|we['’]?re done|stop listening|end conversation)(?:[, ]+please)?[.!?]*$",re.I)
class Conversation:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.lock=threading.RLock();self.state='standby';self.reason=None;self.until=0;self.generation=0;self.revoked_before=0
    def begin(self):
        with self.lock:self.generation+=1;self.state='executing';self.reason=None;self.until=0
    def open(self,reason,seconds=8):
        with self.lock:self.state='waiting' if reason=='question' else 'followup';self.reason=reason;self.until=self.clock()+seconds
    def dismiss(self):
        with self.lock:self.generation+=1;self.revoked_before=self.generation;self.state='standby';self.reason=None;self.until=0
    def independent(self,generation):
        # Beginning a different task does not cancel another fully named
        # request. Explicit dismissal does revoke every earlier capture.
        with self.lock:return type(generation) is int and self.revoked_before<=generation<=self.generation
    def allowed(self,text,known=lambda t:False,eligible=False):
        with self.lock:
            if self.state not in ('waiting','followup') or self.until<=0:return False
            # Ears may finish decoding after expiry. Only its existing onset
            # gate can admit that earlier speech; do not grant a fresh window.
            if not eligible and self.clock()>=self.until:return False
            if DISMISS.fullmatch(text.strip()):return True
            if self.reason in ('question','wake'):return True
            # Optional ordinary followups accept complete supported commands only.
            # This is a bounded session, NOT proof of speaker/addressedness.
            return self.reason in ('reply','arrival','interrupt') and known(text)
    def snapshot(self):
        with self.lock:
            remaining=max(0,self.until-self.clock())
            expired=self.until>0 and remaining==0
            # A status read must not erase the filter for speech already
            # captured inside this window and still waiting for decoding.
            return {'state':'standby' if expired else self.state,'reason':None if expired else self.reason,'seconds_left':round(remaining,1)}

class Arrival:
    """Idle-to-input hint, never a claim of physical presence. No cameras/tracking."""
    def __init__(self,clock=time.monotonic):self.clock=clock;self.away=False;self.last=-float('inf')
    def poll(self,idle_seconds,allowed,unlocked=False):
        if idle_seconds is not None and idle_seconds>=300:self.away=True
        if not unlocked and (idle_seconds is None or not self.away or idle_seconds>2):return False
        self.away=False
        if not allowed or self.clock()-self.last<900:return False
        self.last=self.clock();return True

def desktop_idle():
    import ctypes
    from ctypes import wintypes as w
    user=ctypes.WinDLL('user32',use_last_error=True)
    user.OpenInputDesktop.argtypes=[w.DWORD,w.BOOL,w.DWORD];user.OpenInputDesktop.restype=w.HANDLE
    user.CloseDesktop.argtypes=[w.HANDLE]
    desktop=user.OpenInputDesktop(0,False,0x100)
    if not desktop:return None
    user.CloseDesktop(desktop)
    class Input(ctypes.Structure):_fields_=[('cbSize',w.UINT),('dwTime',w.DWORD)]
    info=Input();info.cbSize=ctypes.sizeof(info)
    if not user.GetLastInputInfo(ctypes.byref(info)):return None
    return ((ctypes.windll.kernel32.GetTickCount()-info.dwTime)&0xffffffff)/1000
