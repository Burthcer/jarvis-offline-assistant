"""Request-scoped YouTube card adapter through Windows accessibility, no vision/DOM port.
Only the foreground browser is read. Controls never cross COM thread boundaries.
"""
import ctypes,time,re,hashlib
from collections import deque
from urllib.parse import urlsplit,parse_qs
from pathlib import Path
from ctypes import wintypes as w
from .engine import uia
from .choices import Choices

def box(control):
    r=control.BoundingRectangle
    return (round(r.left),round(r.top),round(r.right),round(r.bottom))
def value(control):
    try:return str(control.GetValuePattern().Value or '')
    except Exception:
        try:return str(control.GetLegacyIAccessiblePattern().Value or '')
        except Exception:return ''
NAV = re.compile(r'^(?:images?|videos?|news|maps|shopping|books|flights|finance|web|all|more|tools|settings|sign in|log in|privacy|terms|help|feedback|next|previous|about|learn more|skip to (?:main )?content|advertising|business|how search works|cookies?|accept all|reject all|shorts|subscriptions|library|history|home|explore)$', re.I)
def result_link_ok(label, link, page_host):
    """A search result or ordinary page link worth a number: a real title, an http(s) target, not site navigation or something risky."""
    if len(label) < 12 or NAV.match(label.strip()) or uia.risky(label) or re.search(r'\b(?:sponsored|advertisement|ad)\b', label, re.I):
        return False
    p = urlsplit(link)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        return False
    if re.search(r'(?:^|/)(?:signin|login|account|oauth|checkout|payment|logout)(?:/|$)', p.path, re.I):
        return False
    return True
def video_key(url):
    p=urlsplit(url);query=parse_qs(p.query)
    return (p.hostname,p.path,query.get('v',[''])[0],query.get('list',[''])[0])

class BrowserChoices:
    def __init__(self,backend,hwnd=None,fixture_folder=None):
        self.backend=backend;self.u=ctypes.windll.user32;self.u.GetForegroundWindow.restype=w.HWND
        windows=backend._browsers();front=self.u.GetForegroundWindow()
        self.hwnd=hwnd if hwnd in windows else front if front in windows else None
        if self.hwnd is None:raise ValueError('Bring the intended browser page to the front, sir.')
        # Fixture override is code-only, never exposed to UI/model arguments.
        self.fixture=Path(fixture_folder).resolve() if fixture_folder else None
        self.activated=set();self.group=None;self.targets={};self.initial_page=None;self.generic=False
    def _allowed(self,url,link=False):
        if len(url)>2048:return False
        p=urlsplit(url)
        if self.fixture:
            from urllib.request import url2pathname
            return p.scheme=='file' and not p.netloc and Path(url2pathname(p.path)).resolve().is_relative_to(self.fixture)
        if p.scheme not in ('https','http') or not p.hostname or p.username or p.password:return False
        if re.search(r'(?:^|/)(?:signin|login|account|oauth|checkout|payment)(?:/|$)',p.path,re.I):return False
        if self.generic:return True          # search results or any ordinary page: its visible links
        if p.hostname not in ('youtube.com','www.youtube.com','music.youtube.com'):return False
        return not link or p.path in ('/watch','/playlist')
    def _address_allowed(self,text):
        if self.fixture:
            return self._allowed(text) if text.startswith('file:') else Path(text).resolve().is_relative_to(self.fixture)
        return self._allowed(text if '://' in text else 'https://'+text)
    def _activate(self,renderers):
        self.u.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,ctypes.POINTER(ctypes.c_size_t)]
        for handle in renderers:
            if handle in self.activated:continue
            result=ctypes.c_size_t()
            for object_id in (-25,-4,1):self.u.SendMessageTimeoutW(handle,0x3d,0,object_id,2,200,ctypes.byref(result))
            self.activated.add(handle)
    def _native(self,auto):
        if self.u.GetForegroundWindow()!=self.hwnd:raise ValueError('The active window changed. Bring the choices back to the front, sir.')
        if not self.u.IsWindow(w.HWND(self.hwnd)):raise ValueError('That browser window closed.')
        title=self.backend._title(w.HWND(self.hwnd))
        if uia.DENY_WINDOW.search(title):raise ValueError('I do not read banking, payment or login windows, sir.')
        root=auto.ControlFromHandle(self.hwnd);queue=deque([root]);docs=[];addresses=[];renderers=[];seen=0
        while queue and seen<1200:
            node=queue.popleft();seen+=1;kind=node.ControlTypeName
            if kind=='DocumentControl':docs.append(node);continue
            if kind=='EditControl':
                if node.Name=='Address and search bar' and not node.IsPassword:addresses.append(value(node))
                continue
            if node.ClassName=='Chrome_RenderWidgetHostHWND' and node.NativeWindowHandle and not node.IsOffscreen:renderers.append(node.NativeWindowHandle)
            queue.extend(node.GetChildren())
        if queue:raise ValueError('I could not read a complete browser frame.')
        if len(addresses)!=1 or not self._address_allowed(addresses[0]):raise ValueError('I cannot number this page, sir. It must be an ordinary web page in front.')
        self._activate(renderers)
        # Re-query after requesting this renderer's standard accessibility object.
        for attempt in range(5):
            if attempt:
                docs=[];queue=deque([auto.ControlFromHandle(self.hwnd)]);seen=0
                while queue and seen<1200:
                    node=queue.popleft();seen+=1
                    if node.ControlTypeName=='DocumentControl':docs.append(node);continue
                    if node.ControlTypeName!='EditControl':queue.extend(node.GetChildren())
                if queue:raise ValueError('The browser frame is incomplete.')
            readable=[]
            for node in docs:
                try:
                    url=value(node);bounds=box(node)
                    if url and self._allowed(url) and bounds[2]>bounds[0] and bounds[3]>bounds[1] and not node.IsOffscreen:readable.append((node,url,bounds))
                except Exception:pass # an accessibility activation can replace the old document
            if len(readable)==1:break
            if attempt==4:raise ValueError('This browser has not exposed one readable page. I have not clicked anything, sir.')
            time.sleep(.08)
        return title,readable[0]
    def _collect(self,auto,group):
        if group not in ('videos','mixes','playlists','results'):raise ValueError('Choose videos, mixes, playlists or results.')
        self.generic=group=='results'
        try:title,(doc,url,viewport)=self._native(auto)
        except ValueError:
            if group!='videos' or self.fixture:raise
            self.generic=True;group='results'          # "number the videos" on a non-YouTube page: number its links instead
            title,(doc,url,viewport)=self._native(auto)
        if not self.generic and not self.fixture and urlsplit(url).hostname not in ('youtube.com','www.youtube.com','music.youtube.com'):
            self.generic=True;group='results'
        page_host=urlsplit(url).hostname
        try:scroll=doc.GetScrollPattern();position=(scroll.HorizontalScrollPercent,scroll.VerticalScrollPercent)
        except Exception:position=()
        page=(self.hwnd,tuple(doc.GetRuntimeId()),url,title,viewport,position)
        queue=deque([(doc,None)]);records=[];controls={};seen=0
        while queue and seen<1600:
            node,card=queue.popleft();seen+=1;kind=node.ControlTypeName
            if node.IsOffscreen or (kind=='EditControl' and node.IsPassword):continue
            if kind=='DocumentControl' and node is not doc:continue
            if kind=='ListItemControl':card=(str(tuple(node.GetRuntimeId())),box(node))
            if kind=='HyperlinkControl':
                link=value(node);label=' '.join((node.Name or '').split())
                if not label or not self._allowed(link,True) or uia.risky(label) or re.search(r'\b(?:sponsored|advertisement)\b',label,re.I):continue
                if self.generic and not result_link_ok(label,link,page_host):continue
                query=parse_qs(urlsplit(link).query)
                if not self.fixture and group=='mixes' and not (query.get('list',[''])[0].startswith('RD') or re.search(r'\bmix\b',label,re.I)):continue
                if not self.fixture and group=='playlists' and not query.get('list'):continue
                ident=str(tuple(node.GetRuntimeId()))+'|'+hashlib.sha256(link.encode()).hexdigest();bounds=card[1] if card else box(node)
                key=(card[0] if card else ident,link if self.generic else video_key(link))
                previous=next((r for r in records if r['_card']==key),None)
                if previous:
                    # Prefer the full named link, keeping the one physical card.
                    if len(label)<=len(previous['title']):continue
                    records.remove(previous);controls.pop(previous['id'],None)
                record={'id':ident,'title':label[:220],'bounds':bounds,'visible':True,'enabled':bool(node.IsEnabled),'group':group,'_card':key}
                records.append(record);controls[ident]=(node,link)
                continue
            if kind!='EditControl':queue.extend((c,card) for c in node.GetChildren())
        if queue:raise ValueError('There are too many controls to index safely. Choose a smaller section, sir.')
        return page,records,viewport,controls
    def snapshot(self,group):
        auto=uia._auto()
        with auto.UIAutomationInitializerInThread():
            uia.bound_client()
            page,records,viewport,_=self._collect(auto,group)
        self.group='results' if self.generic else group
        if self.initial_page is None:self.initial_page=page
        return Choices().capture(page,group,records,viewport)
    def invoke(self,item):
        auto=uia._auto()
        with auto.UIAutomationInitializerInThread():
            uia.bound_client()
            page,records,viewport,controls=self._collect(auto,self.group or 'videos')
            if page!=self.initial_page or item.identity not in controls:return False
            control,url=controls[item.identity]
            if ' '.join((control.Name or '').split())[:220]!=item.title:return False
            from .native_action import request
            self.targets[item.identity]=url
            return request(control)
    def verify(self,item):
        target=self.targets.get(item.identity)
        if not target:return False
        auto=uia._auto();end=time.monotonic()+1
        with auto.UIAutomationInitializerInThread():
            uia.bound_client()
            while time.monotonic()<end:
                try:
                    title,(doc,url,bounds)=self._native(auto)
                    if self.fixture:
                        if url==target:return True
                    elif self.generic:
                        if url==target or urlsplit(url).hostname==urlsplit(target).hostname or url!=self.initial_page[2]:return True   # a result opened: same site, or the page moved on
                    elif video_key(url)==video_key(target):return True
                except Exception:return False
                time.sleep(.04)
        return False
