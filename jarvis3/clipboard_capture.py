"""Explicit clipboard text capture, isolated from the app with a hard timeout.

No listener/history/paste/clipboard writes. Native privacy formats are honoured:
https://learn.microsoft.com/windows/win32/dataxchg/clipboard-formats
"""
import ctypes,json,os,re,subprocess,sys
from ctypes import wintypes as w

LIMIT=2000

def checked_text(text):
    if not isinstance(text,str) or not text.strip() or len(text)>LIMIT or any(ord(c)<32 and c not in '\r\n\t' for c in text):raise ValueError('Copy a short piece of plain text first, sir.')
    from .engine.knowledge import describe
    if describe(text)['secret'] or re.search(r'\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b|[?&#](?:access_token|refresh_token|token|auth|code|api_key)=',text,re.I):raise ValueError('That clipboard text looks private. I have not saved it, sir.')
    return text

def native_read(u=None,k=None):
    u=u or ctypes.windll.user32;k=k or ctypes.windll.kernel32
    u.OpenClipboard.argtypes=[w.HWND]
    u.GetClipboardData.argtypes=[w.UINT];u.GetClipboardData.restype=ctypes.c_void_p
    u.RegisterClipboardFormatW.argtypes=[w.LPCWSTR];u.RegisterClipboardFormatW.restype=w.UINT
    u.GetClipboardSequenceNumber.restype=w.DWORD
    k.GlobalSize.argtypes=[ctypes.c_void_p];k.GlobalSize.restype=ctypes.c_size_t
    k.GlobalLock.argtypes=[ctypes.c_void_p];k.GlobalLock.restype=ctypes.c_void_p
    k.GlobalUnlock.argtypes=[ctypes.c_void_p]
    exclude=u.RegisterClipboardFormatW('ExcludeClipboardContentFromMonitorProcessing')
    history=u.RegisterClipboardFormatW('CanIncludeInClipboardHistory')
    if not exclude or not history:raise ValueError('Clipboard privacy status is unavailable, sir.')
    if not u.OpenClipboard(None):raise ValueError('Clipboard is busy. Please try again, sir.')
    try:
        if u.IsClipboardFormatAvailable(exclude):raise ValueError('That clipboard item is marked private, sir.')
        if u.IsClipboardFormatAvailable(history):
            handle=u.GetClipboardData(history)
            if not handle or not 4<=k.GlobalSize(handle)<=16:raise ValueError('Clipboard privacy status is unavailable, sir.')
            ptr=k.GlobalLock(handle)
            if not ptr:raise ValueError('Clipboard is busy, sir.')
            try:allowed=ctypes.c_uint32.from_address(ptr).value==1
            finally:k.GlobalUnlock(handle)
            if not allowed:raise ValueError('That clipboard item is marked private, sir.')
        if not u.IsClipboardFormatAvailable(13):raise ValueError('Copy plain text first, sir.')
        sequence=int(u.GetClipboardSequenceNumber())
        if not sequence:raise ValueError('Clipboard identity is unavailable, sir.')
        handle=u.GetClipboardData(13)
        if not handle:raise ValueError('Clipboard text is unavailable, sir.')
        size=k.GlobalSize(handle)
        # Non-BMP characters use two UTF16 units. Allow bounded allocator
        # padding, then enforce the actual decoded character count below.
        if size<2 or size%2 or size>8192:raise ValueError('Copy a shorter piece of plain text, sir.')
        ptr=k.GlobalLock(handle)
        if not ptr:raise ValueError('Clipboard is busy, sir.')
        try:data=ctypes.string_at(ptr,size)
        finally:k.GlobalUnlock(handle)
        end=next((i for i in range(0,len(data),2) if data[i:i+2]==b'\0\0'),None)
        if end is None:raise ValueError('Clipboard text is incomplete, sir.')
        try:text=data[:end].decode('utf-16-le')
        except UnicodeError:raise ValueError('Clipboard text is invalid, sir.') from None
        if len(text)>LIMIT:raise ValueError('Copy a shorter piece of plain text, sir.')
        if int(u.GetClipboardSequenceNumber())!=sequence:raise ValueError('Clipboard changed. Please ask again, sir.')
        return {'text':text,'sequence':sequence}
    finally:u.CloseClipboard()

def read():
    from .paths import PROJECT
    try:
        result=subprocess.run([sys.executable,'-m','jarvis3.clipboard_capture','--native'],cwd=str(PROJECT),env={**os.environ,'JARVIS_SILENT':'1'},capture_output=True,text=True,encoding='utf-8',timeout=1.5,creationflags=subprocess.CREATE_NO_WINDOW)
        data=json.loads(result.stdout)
    except (OSError,ValueError,subprocess.TimeoutExpired):raise ValueError('Clipboard is busy or unavailable. Please try again, sir.') from None
    if not isinstance(data,dict):raise ValueError('Clipboard text is unavailable, sir.')
    if not data.get('ok'):raise ValueError(data.get('message','Clipboard text is unavailable, sir.'))
    if type(data.get('sequence')) is not int or data['sequence']<=0:raise ValueError('Clipboard identity is unavailable, sir.')
    return {'text':checked_text(data.get('text')),'sequence':data['sequence']}

if __name__=='__main__' and '--native' in sys.argv:
    try:result={'ok':True,**native_read()}
    except ValueError as error:result={'ok':False,'message':str(error)}
    except Exception:result={'ok':False,'message':'Clipboard text is unavailable, sir.'}
    print(json.dumps(result,ensure_ascii=True),flush=True)
