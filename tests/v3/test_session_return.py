"""Injected Windows-session hints only; never lock/unlock the real desktop."""
import os,sys,threading
from pathlib import Path
from types import SimpleNamespace as NS
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.session_return import SessionReturn,_Windows,SESSION_LOCK,SESSION_UNLOCK

class API:
    def __init__(self,registered=True,pump_error=False,unregister_error=False):
        self.trace=[];self.handler=None;self.release=threading.Event()
        self.registered=registered;self.pump_error=pump_error;self.unregister_error=unregister_error
    def session_id(self):return 12
    def create(self,handler):self.trace.append('create');self.handler=handler;return 123
    def register(self,hwnd):assert hwnd==123;self.trace.append('register');return self.registered
    def pump(self):
        self.trace.append('pump')
        if self.pump_error:raise OSError('owned fake message failure')
        assert self.release.wait(4),'owned fake watcher was not stopped'
    def stop(self,hwnd):assert hwnd==123;self.trace.append('stop');self.release.set()
    def unregister(self,hwnd):
        assert hwnd==123;self.trace.append('unregister')
        if self.unregister_error:raise OSError('owned fake unregister failure')
    def destroy(self,hwnd):assert hwnd==123;self.trace.append('destroy')

clock=[100.0];api=API();source=SessionReturn(api,clock=lambda:clock[0])
assert not api.trace and not source.available and not source.take(),'source started without explicit opt-in'
assert source.start() and source.available
try:
    api.handler(SESSION_UNLOCK,12);assert not source.take(),'unpaired unlock produced a hint'
    for event in (1,2,3,4,5,6,9,15):api.handler(event,12)
    assert not source.take(),'connect/logon/other status was mistaken for an unlock'
    api.handler(SESSION_LOCK,99);api.handler(SESSION_UNLOCK,99)
    assert not source.locked and not source.take(),'another session produced a return hint'
    api.handler(SESSION_LOCK,12);api.handler(SESSION_LOCK,12);assert source.locked
    api.handler(SESSION_UNLOCK,12);api.handler(SESSION_UNLOCK,12)
    assert not source.locked and source.take() and not source.take(),'one pair did not produce exactly one hint'
    api.handler(SESSION_UNLOCK,12);assert not source.take(),'duplicate unlock produced another hint'
    api.handler(SESSION_LOCK,12);api.handler(SESSION_UNLOCK,12);clock[0]+=16
    assert not source.take(),'a stale return hint survived beyond fifteen seconds'
    api.handler(SESSION_LOCK,12);api.handler(SESSION_UNLOCK,12);api.handler(SESSION_LOCK,12)
    assert source.locked and not source.take(),'new lock retained an old unlock hint'
    api.handler(SESSION_UNLOCK,12);assert source.take()
    api.handler(SESSION_LOCK,12);api.handler(SESSION_UNLOCK,12)
finally:assert source.close()
assert not source.take() and not source.available
api.handler(SESSION_LOCK,12);api.handler(SESSION_UNLOCK,12);assert not source.take(),'closed source still accepted notifications'
assert api.trace.count('register')==api.trace.count('unregister')==api.trace.count('destroy')==1
assert api.trace.index('unregister')<api.trace.index('destroy'),'destroyed the window before unregistering'
assert source.close() and api.trace.count('unregister')==1,'repeat close repeated cleanup'
assert not source.start(),'closed source restarted unexpectedly'

failed=API(registered=False);source=SessionReturn(failed)
assert not source.start() and not source.available and source.error
assert source.close() and failed.trace==['create','register','destroy'],'failed registration had unmatched unregister or a leaked window'
for options in ({'pump_error':True},{'unregister_error':True}):
    api=API(**options);source=SessionReturn(api);source.start()
    if options.get('pump_error'):source._thread.join(2)
    assert source.close() and not source.available and source.error
    assert api.trace.count('unregister')==api.trace.count('destroy')==1
    assert api.trace.index('unregister')<api.trace.index('destroy')

# Exercise the thin native adapter's flag, without loading any DLL/window.
calls=[];native=_Windows.__new__(_Windows)
native.wts=NS(WTSRegisterSessionNotification=lambda h,f:(calls.append((h,f)),1)[1])
assert native.register(456) and calls==[(456,0)],'native watcher requested other users sessions'
print('SESSION RETURN: opt-in, exact same-session lock/unlock, dedup/expiry, closed suppression, cleanup/failure ordering, own-session flag passed')
