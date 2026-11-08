"""Ephemeral receipts for exact workspace tabs in the current browser window.

Never discover hidden page URLs, match titles, launch a page or switch windows.
A known tab may be selected, but reuse requires fresh exact URL readback.
"""
from contextlib import contextmanager
from .engine.uia import DENY_WINDOW
from .reference import safe_url

def _foreground():
    import ctypes
    ctypes.windll.user32.GetForegroundWindow.restype=ctypes.c_void_p
    return ctypes.windll.user32.GetForegroundWindow()

class _SameWindow:
    """WindowsTabs must never recover lost focus with global keys/window focus."""
    def __init__(self,backend,foreground=_foreground):self.backend=backend;self.foreground=foreground
    def __getattr__(self,name):return getattr(self.backend,name)
    def _front(self,hwnd):return self.foreground()==hwnd


class WorkspaceTabs:
    def __init__(self,backend=None,*,session=None,identity=None,read=None,cancelled=lambda:False):
        self.backend=backend;self.receipts={};self.cancelled=cancelled
        self.session=session or self._native_session
        self.identity=identity or self._native_identity
        self.read=read or self._native_read

    @contextmanager
    def _native_session(self,browser):
        from .engine import uia
        from .engine.browser_tabs import WindowsTabs
        auto=uia._auto()
        with auto.UIAutomationInitializerInThread():
            uia.bound_client()
            tabs=WindowsTabs(_SameWindow(self.backend),browser=browser)
            tabs.workspace_browser=browser
            yield tabs

    def _native_identity(self,tabs):
        import ctypes,psutil
        u=ctypes.windll.user32
        u.GetForegroundWindow.restype=ctypes.c_void_p
        hwnd=tabs.hwnd
        if not hwnd or u.GetForegroundWindow()!=hwnd or not u.IsWindow(ctypes.c_void_p(hwnd)):return None
        title=self.backend._title(ctypes.c_void_p(hwnd))
        if DENY_WINDOW.search(title):return None
        pid=ctypes.c_ulong()
        u.GetWindowThreadProcessId(ctypes.c_void_p(hwnd),ctypes.byref(pid))
        process=psutil.Process(pid.value)
        expected={'edge':'msedge.exe','chrome':'chrome.exe'}.get(getattr(tabs,'workspace_browser',None))
        if process.name().lower()!=expected:return None
        return hwnd,pid.value,process.create_time()

    def _native_read(self,tabs):
        from .reference import front_url
        if self._native_identity(tabs) is None:return None
        url=front_url(self.backend)
        return url if self._native_identity(tabs) is not None else None

    def _observe(self,tabs,identity,selected,url):
        if self.cancelled() or self.identity(tabs)!=identity:return False
        rows=tabs.list_tabs()
        active=[r for r in rows if r.get('selected')]
        if len(active)!=1 or active[0]['id']!=selected or DENY_WINDOW.search(active[0]['title']):return False
        if self.read(tabs)!=url or self.cancelled() or self.identity(tabs)!=identity:return False
        after=tabs.list_tabs()
        active=[r for r in after if r.get('selected')]
        if len(active)!=1 or active[0]['id']!=selected or DENY_WINDOW.search(active[0]['title']):return False
        if self.read(tabs)!=url or self.cancelled() or self.identity(tabs)!=identity:return False
        final=[r for r in tabs.list_tabs() if r.get('selected')]
        return len(final)==1 and final[0]['id']==selected and not DENY_WINDOW.search(final[0]['title']) and not self.cancelled() and self.identity(tabs)==identity

    def remember(self,browser,url):
        key=(browser,url)
        self.receipts.pop(key,None)
        if browser not in ('edge','chrome') or safe_url(url)!=url or self.cancelled():return False
        try:
            with self.session(browser) as tabs:
                identity=self.identity(tabs)
                if identity is None:return False
                selected=[r for r in tabs.list_tabs() if r.get('selected')]
                if len(selected)!=1:return False
                ident=selected[0]['id']
                if not self._observe(tabs,identity,ident,url):return False
                self.receipts[key]=(identity,ident)
                while len(self.receipts)>32:self.receipts.pop(next(iter(self.receipts)))
                return True
        except Exception:return False

    def present(self,browser,url):
        key=(browser,url);receipt=self.receipts.get(key)
        if receipt is None or self.cancelled():return False
        try:
            with self.session(browser) as tabs:
                identity,ident=receipt
                if self.identity(tabs)!=identity:raise ValueError('Browser window changed')
                rows=tabs.list_tabs();target=[r for r in rows if r['id']==ident]
                active=[r for r in rows if r.get('selected')]
                if len(active)!=1 or DENY_WINDOW.search(active[0]['title']):raise ValueError('Protected or ambiguous current tab')
                if len(target)!=1 or DENY_WINDOW.search(target[0]['title']):raise ValueError('Tab changed')
                if self.cancelled() or self.identity(tabs)!=identity:raise ValueError('Request changed')
                if not target[0].get('selected') and not tabs.select(ident):raise ValueError('Selection refused')
                if not self._observe(tabs,identity,ident,url):raise ValueError('Page changed')
                return True
        except Exception:
            self.receipts.pop(key,None)
            return False
