"""Own hidden notification window lifecycle only: no synthetic session events.

Never calls lock/unlock/logon/session-changing APIs or posts session-change
messages. This proves registration/cleanup, not a real arrival notification.
"""
import os,sys,ctypes
from ctypes import wintypes as w
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.session_return import SessionReturn,_Windows

class Owned(_Windows):
    def __init__(self):super().__init__();self.trace=[];self.created=None
    def create(self,handler):
        hwnd=super().create(handler);self.created=hwnd;self.trace.append('create')
        self.user.IsWindow.argtypes=[w.HWND];self.user.IsWindow.restype=w.BOOL
        self.user.IsWindowVisible.argtypes=[w.HWND];self.user.IsWindowVisible.restype=w.BOOL
        assert self.user.IsWindow(hwnd) and not self.user.IsWindowVisible(hwnd),'owned watcher window was visible'
        return hwnd
    def register(self,hwnd):
        result=super().register(hwnd)
        if result:self.trace.append('register')
        return result
    def unregister(self,hwnd):self.trace.append('unregister');super().unregister(hwnd)
    def destroy(self,hwnd):
        super().destroy(hwnd);self.trace.append('destroy')
        if hwnd:assert not self.user.IsWindow(hwnd),'owned watcher window survived cleanup'

api=Owned();source=SessionReturn(api)
try:
    available=source.start()
    if available:assert source.available
finally:assert source.close(),'owned notification thread did not close'
assert not source.available and not source.take() and not source._thread.is_alive()
assert api.trace.count('destroy')==1 and not api.class_registered
if available:
    assert api.trace==['create','register','unregister','destroy'] and not source.error,source.error
    print('NATIVE SESSION RETURN: own hidden window registered for current session, unregistered before destruction, thread/window/class closed; no lock/unlock tested')
else:
    print('NATIVE SESSION RETURN unavailable:',source.error,'; owned window/class/thread cleaned')
