"""Opt-in local lock/unlock hint; not physical presence or account monitoring.

Only a lock->unlock pair observed in this process's own Windows session can
produce a hint. No polling, account queries, keyboard hooks or synthetic events.
Native contract:
https://learn.microsoft.com/windows/win32/api/wtsapi32/nf-wtsapi32-wtsregistersessionnotification
https://learn.microsoft.com/windows/win32/termserv/wm-wtssession-change
"""
import ctypes,os,threading,time
from ctypes import wintypes as w

SESSION_CHANGE=0x02B1
SESSION_LOCK=7
SESSION_UNLOCK=8


class SessionReturn:
    def __init__(self,api=None,clock=time.monotonic):
        self._api=api;self._hwnd=None;self._thread=None;self._session=None
        self._lock=threading.Lock();self._ready=threading.Event();self._closed=threading.Event()
        self._active=False;self._locked=False;self._pending=False;self.error=''
        self.clock=clock;self._pending_at=None
        self._generation=0

    @property
    def available(self):
        with self._lock:return self._active and not self._closed.is_set()

    @property
    def locked(self):
        with self._lock:return self._locked

    @property
    def generation(self):
        with self._lock:return self._generation

    def start(self):
        if self._closed.is_set():return False
        if self._thread is None:
            self._thread=threading.Thread(target=self._run,name='jarvis-v3-session-return',daemon=True)
            self._thread.start()
        if not self._ready.wait(1.5):
            self.error='Session return notifications are unavailable.';self.close();return False
        return self.available

    def take(self):
        with self._lock:
            age=self.clock()-self._pending_at if self._pending_at is not None else None
            result=self._active and not self._closed.is_set() and self._pending and age is not None and 0<=age<=15
            self._pending=False;self._pending_at=None
            return bool(result)

    def _event(self,event,session):
        with self._lock:
            if not self._active or self._closed.is_set() or session!=self._session:return
            if event==SESSION_LOCK:
                self._generation+=1;self._locked=True;self._pending=False;self._pending_at=None
            elif event==SESSION_UNLOCK and self._locked:
                self._generation+=1;self._locked=False;self._pending=True;self._pending_at=self.clock()

    def _run(self):
        registered=False
        try:
            api=self._api=self._api or _Windows()
            self._session=api.session_id()
            self._hwnd=api.create(self._event)
            if self._closed.is_set():return
            if not api.register(self._hwnd):raise OSError('Session return notifications are unavailable.')
            registered=True
            with self._lock:self._active=not self._closed.is_set()
            self._ready.set()
            if not self._closed.is_set():api.pump()
        except Exception as error:self.error=str(error) or 'Session return notifications are unavailable.'
        finally:
            with self._lock:self._active=False;self._pending=False
            if self._api:
                try:
                    if registered:self._api.unregister(self._hwnd)
                except Exception as error:self.error=str(error)
                finally:
                    try:self._api.destroy(self._hwnd)
                    except Exception as error:self.error=str(error)
            self._hwnd=None;self._ready.set()

    def close(self):
        self._closed.set()
        with self._lock:self._active=False;self._pending=False
        if self._hwnd and self._api:
            try:self._api.stop(self._hwnd)
            except Exception as error:self.error=str(error)
        if self._thread and self._thread is not threading.current_thread():self._thread.join(2)
        return self._thread is None or not self._thread.is_alive()


class _Windows:
    """One hidden owned window, registered only for its own session."""
    def __init__(self):
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.wts=ctypes.WinDLL('wtsapi32',use_last_error=True)
        self.proc_type=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
        class WindowClass(ctypes.Structure):
            _fields_=[('style',w.UINT),('lpfnWndProc',self.proc_type),('cbClsExtra',ctypes.c_int),('cbWndExtra',ctypes.c_int),('hInstance',w.HINSTANCE),('hIcon',w.HICON),('hCursor',w.HANDLE),('hbrBackground',w.HBRUSH),('lpszMenuName',w.LPCWSTR),('lpszClassName',w.LPCWSTR)]
        self.window_class=WindowClass;self.class_registered=False
        self.name=f'JarvisV4SessionReturn_{os.getpid()}_{id(self)}'
        self.kernel.GetModuleHandleW.argtypes=[w.LPCWSTR];self.kernel.GetModuleHandleW.restype=w.HMODULE
        self.kernel.GetCurrentProcessId.restype=w.DWORD
        self.kernel.ProcessIdToSessionId.argtypes=[w.DWORD,ctypes.POINTER(w.DWORD)];self.kernel.ProcessIdToSessionId.restype=w.BOOL
        self.user.RegisterClassW.argtypes=[ctypes.POINTER(WindowClass)];self.user.RegisterClassW.restype=w.WORD
        self.user.UnregisterClassW.argtypes=[w.LPCWSTR,w.HINSTANCE];self.user.UnregisterClassW.restype=w.BOOL
        self.user.CreateWindowExW.argtypes=[w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,w.HWND,w.HMENU,w.HINSTANCE,ctypes.c_void_p];self.user.CreateWindowExW.restype=w.HWND
        self.user.DefWindowProcW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];self.user.DefWindowProcW.restype=ctypes.c_ssize_t
        self.user.DestroyWindow.argtypes=[w.HWND];self.user.DestroyWindow.restype=w.BOOL
        self.user.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM];self.user.PostMessageW.restype=w.BOOL
        self.user.GetMessageW.argtypes=[ctypes.POINTER(w.MSG),w.HWND,w.UINT,w.UINT];self.user.GetMessageW.restype=ctypes.c_int
        self.user.TranslateMessage.argtypes=[ctypes.POINTER(w.MSG)]
        self.user.DispatchMessageW.argtypes=[ctypes.POINTER(w.MSG)];self.user.DispatchMessageW.restype=ctypes.c_ssize_t
        self.wts.WTSRegisterSessionNotification.argtypes=[w.HWND,w.DWORD];self.wts.WTSRegisterSessionNotification.restype=w.BOOL
        self.wts.WTSUnRegisterSessionNotification.argtypes=[w.HWND];self.wts.WTSUnRegisterSessionNotification.restype=w.BOOL

    def session_id(self):
        value=w.DWORD()
        if not self.kernel.ProcessIdToSessionId(self.kernel.GetCurrentProcessId(),ctypes.byref(value)):raise ctypes.WinError(ctypes.get_last_error())
        return value.value

    def create(self,handler):
        def procedure(hwnd,message,word,param):
            if message==SESSION_CHANGE:handler(int(word),int(param));return 0
            if message==0x10:self.user.PostQuitMessage(0);return 0
            return self.user.DefWindowProcW(hwnd,message,word,param)
        self.procedure=self.proc_type(procedure);self.instance=self.kernel.GetModuleHandleW(None)
        cls=self.window_class();cls.lpfnWndProc=self.procedure;cls.hInstance=self.instance;cls.lpszClassName=self.name
        if not self.user.RegisterClassW(ctypes.byref(cls)):raise ctypes.WinError(ctypes.get_last_error())
        self.class_registered=True
        hwnd=self.user.CreateWindowExW(0,self.name,'Jarvis V4 session return watcher',0,0,0,0,0,None,None,self.instance,None)
        if not hwnd:raise ctypes.WinError(ctypes.get_last_error())
        return hwnd

    def register(self,hwnd):return bool(self.wts.WTSRegisterSessionNotification(hwnd,0))  # NOTIFY_FOR_THIS_SESSION
    def unregister(self,hwnd):
        if not self.wts.WTSUnRegisterSessionNotification(hwnd):raise ctypes.WinError(ctypes.get_last_error())
    def pump(self):
        message=w.MSG()
        while True:
            result=self.user.GetMessageW(ctypes.byref(message),None,0,0)
            if result<0:raise ctypes.WinError(ctypes.get_last_error())
            if not result:return
            self.user.TranslateMessage(ctypes.byref(message));self.user.DispatchMessageW(ctypes.byref(message))
    def stop(self,hwnd):
        if not self.user.PostMessageW(hwnd,0x10,0,0):raise ctypes.WinError(ctypes.get_last_error())
    def destroy(self,hwnd):
        try:
            if hwnd and not self.user.DestroyWindow(hwnd):raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if self.class_registered:
                if not self.user.UnregisterClassW(self.name,self.instance):raise ctypes.WinError(ctypes.get_last_error())
                self.class_registered=False
