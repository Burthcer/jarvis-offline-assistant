"""V3 entry: one voice owner, private state, no automatic shutdown of V2."""
import ctypes,logging
from ctypes import wintypes as w
from .paths import enter,LOGS
_mutex=None

def acquire_voice(kernel=None):
    global _mutex
    k=kernel or ctypes.WinDLL('kernel32',use_last_error=True)
    if kernel is None:
        k.CreateMutexW.argtypes=[ctypes.c_void_p,w.BOOL,w.LPCWSTR];k.CreateMutexW.restype=w.HANDLE
        k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
    handle=k.CreateMutexW(None,False,'JarvisOfflineAssistant')
    if not handle:raise OSError('Windows could not check the active assistant.')
    if ctypes.get_last_error()==183:
        k.CloseHandle(handle)
        return False
    _mutex=handle
    return True

def main():
    if not acquire_voice():
        ctypes.windll.user32.MessageBoxW(None,'Another Jarvis (V1, V2, V3 or V4) is already running. Please quit it yourself before opening V4. V4 has not changed or closed it.','Jarvis V4',0x40)
        return
    enter()
    logging.basicConfig(filename=str(LOGS/'jarvis3.log'),level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    from .engine.ui import main as start
    start()
