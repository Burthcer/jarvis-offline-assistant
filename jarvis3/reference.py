"""Request-scoped native browser address only. Never page text or clipboard polling."""
import ctypes,time,re
from collections import deque
from urllib.parse import urlsplit,parse_qs
from .engine import uia
from .browser_choices import value

def safe_url(text):
    if not isinstance(text,str) or len(text)>2048 or re.search(r'\s',text):return None
    text=text if '://' in text else 'https://'+text
    try:
        p=urlsplit(text)
        if p.scheme not in ('https','http') or not p.hostname or '.' not in p.hostname or p.username or p.password or p.port not in (None,80,443):return None
        if uia.DENY_WINDOW.search(p.hostname+p.path):return None
        keys=set(parse_qs(p.query,keep_blank_values=True))|set(parse_qs(p.fragment.split('?')[-1],keep_blank_values=True))
        if any(re.search(r'token|secret|password|credential|session|auth|(?:^|_)key$|^code$',key,re.I) for key in keys):return None
        return text
    except ValueError:return None

def front_url(backend):
    u=ctypes.windll.user32;u.GetForegroundWindow.restype=ctypes.c_void_p
    hwnd=u.GetForegroundWindow()
    if not hwnd or hwnd not in backend._browsers():return None
    title=backend._title(ctypes.c_void_p(hwnd))
    if uia.DENY_WINDOW.search(title) or uia.OWN_WINDOW.search(title):return None
    auto=uia._auto()
    with auto.UIAutomationInitializerInThread():
        uia.bound_client();queue=deque([auto.ControlFromHandle(hwnd)]);found=[];seen=0;end=time.monotonic()+1
        while queue and seen<800 and time.monotonic()<end:
            node=queue.popleft();seen+=1;kind=node.ControlTypeName
            if kind=='DocumentControl':continue
            if kind=='EditControl':
                if not node.IsPassword and node.Name=='Address and search bar':found.append(value(node))
                continue
            queue.extend(node.GetChildren())
        if queue or len(found)!=1 or u.GetForegroundWindow()!=hwnd or backend._title(ctypes.c_void_p(hwnd))!=title:return None
    return safe_url(found[0])
