"""An explicit music destination and a player tied to one exact native browser tab."""
import time,re
from collections import deque
from urllib.parse import urlsplit,parse_qs
from .browser_choices import BrowserChoices,value,video_key
from .engine import uia
from .engine.registry import Result

def destination(url):
    if not isinstance(url,str) or len(url)>2048:raise ValueError('Use a YouTube mix or playlist link.')
    p=urlsplit(url.strip());q=parse_qs(p.query)
    if p.scheme!='https' or p.hostname not in ('youtube.com','www.youtube.com') or p.username or p.password or p.port not in (None,443) or p.fragment or any(ord(c)<33 for c in url):raise ValueError('Use a full public YouTube link.')
    if not (p.path=='/watch' and q.get('v') or p.path=='/playlist' and q.get('list')):raise ValueError('Choose a video, mix or playlist, rather than the home page.')
    return url.strip()

class PagePlayer:
    """Invoke only native controls in the original tab. No global media/key fallback."""
    def __init__(self,provider):
        self.provider=provider;self.identity=None;self.url=None
        auto=uia._auto()
        with auto.UIAutomationInitializerInThread():
            uia.bound_client();identity,url,_,_=self._frame(auto,initial=True)
        self.identity=identity;self.url=url;self.browser=identity[3]
    @staticmethod
    def _process_identity(hwnd,user=None,process=None):
        import ctypes
        from ctypes import wintypes as w
        if user is None:
            user=ctypes.windll.user32;user.GetForegroundWindow.restype=w.HWND
        if process is None:
            import psutil
            process=psutil.Process
        handle=w.HWND(hwnd)
        if not user.IsWindow(handle) or user.GetForegroundWindow()!=hwnd:raise ValueError('The music window is no longer in front.')
        pid=w.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
        owner=process(pid.value);browser={'msedge.exe':'edge','chrome.exe':'chrome'}.get(owner.name().lower())
        if browser is None:raise ValueError('Unsupported music browser.')
        identity=(pid.value,owner.create_time(),browser)
        again=w.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(again))
        if again.value!=pid.value or user.GetForegroundWindow()!=hwnd:raise ValueError('The music window changed.')
        return identity
    def _tab(self):
        from .engine.browser_tabs import WindowsTabs
        owner=self._process_identity(self.provider.hwnd)
        tabs=WindowsTabs(self.provider.backend);tabs.hwnd=self.provider.hwnd
        selected=[t['id'] for t in tabs.list_tabs() if t['selected']]
        if len(selected)!=1:raise ValueError('The music tab is no longer selected.')
        if self._process_identity(self.provider.hwnd)!=owner:raise ValueError('The music window changed.')
        return self.provider.hwnd,*owner,selected[0]
    def _frame(self,auto,initial=False,allow_navigation=False):
        title,(doc,url,bounds)=self.provider._native(auto)
        identity=self._tab()
        if not initial:
            if identity!=self.identity:raise ValueError('Bring the original music tab to the front, sir.')
            if not allow_navigation and video_key(url)!=video_key(self.url):raise ValueError('The music page changed, sir.')
        if not self.provider.fixture and urlsplit(url).path not in ('/watch','/playlist'):raise ValueError('There is no supported player on that page, sir.')
        controls=[];queue=deque([doc]);seen=0
        while queue and seen<1400:
            node=queue.popleft();seen+=1
            if node.IsOffscreen or node.ControlTypeName=='EditControl':continue
            if node.ControlTypeName=='DocumentControl' and node is not doc:continue
            if node.ControlTypeName in ('ButtonControl','HyperlinkControl') and node.IsEnabled:
                label=' '.join((node.Name or '').split())
                if label:controls.append((label,node))
            queue.extend(node.GetChildren())
        if queue:raise ValueError('The player controls are too large to read safely, sir.')
        return identity,url,controls,title
    @staticmethod
    def _button(controls,action):
        patterns={'play':r'Play(?: \(k\))?','pause':r'Pause(?: \(k\))?','next':r'Next(?: video)?(?: \(SHIFT\+n\))?','previous':r'Previous(?: video)?(?: \(SHIFT\+p\))?','all':r'Play all'}
        found=[node for name,node in controls if re.fullmatch(patterns[action],name,re.I)]
        if len(found)>1:raise ValueError('More than one player matches. Nothing was pressed, sir.')
        return found[0] if found else None
    def _state(self,controls):
        playing=self._button(controls,'pause');paused=self._button(controls,'play')
        if (playing is None)==(paused is None):return None
        return playing is not None
    def control(self,action):
        auto=uia._auto()
        with auto.UIAutomationInitializerInThread():
            uia.bound_client();identity,url,controls,title=self._frame(auto)
            state=self._state(controls)
            if action in ('play','pause') and state==(action=='play'):return True,{'playing':state,'title':title,'verified':True}
            button=self._button(controls,'all' if action=='play' and state is None else action)
            if button is None:return False,{'playing':state,'title':title}
            # Revalidate the selected native tab immediately before the one effect.
            if self._tab()!=identity:return False,{}
            from .native_action import request
            if not request(button):return False,{'playing':state,'title':title}
            end=time.monotonic()+2
            while time.monotonic()<end:
                _,now,new,title=self._frame(auto,allow_navigation=True)
                after=self._state(new)
                if action in ('play','pause'):
                    changed=after==(action=='play')
                    if urlsplit(url).path=='/playlist':
                        changed=changed and parse_qs(urlsplit(now).query).get('list')==parse_qs(urlsplit(url).query).get('list')
                    else:changed=changed and video_key(now)==video_key(url)
                else:changed=video_key(now)!=video_key(url) and after is not None
                if changed:
                    self.url=now;return True,{'playing':after,'title':title,'verified':True}
                time.sleep(.06)
            return False,{'playing':after,'title':title}

class Music:
    def __init__(self,cfg,open_url,provider_factory,stop=lambda:False,player_factory=PagePlayer):
        self.cfg=cfg;self.open_url=open_url;self.provider_factory=provider_factory;self.player_factory=player_factory;self.stop=stop;self.player=None
    def start(self):
        try:url=destination(self.cfg.get('music_url',''))
        except ValueError:return Result(False,'Choose your music link in Settings first, sir.',exact=True)
        browser=self.cfg.get('music_browser','edge')
        if browser not in ('edge','chrome'):return Result(False,'Choose your music browser in Settings, sir.',exact=True)
        # Reuse this exact owned session if it is still on the configured link.
        if self.player and getattr(self.player,'browser',None)==browser and video_key(self.player.url)==video_key(url):return self.control('play')
        self.player=None
        if self.stop():return Result(False,'',exact=True)
        if not self.open_url(browser,url):return Result(False,'I could not open your music link, sir.',exact=True)
        end=time.monotonic()+4
        while not self.stop() and time.monotonic()<end:
            try:
                candidate=self.player_factory(self.provider_factory())
                if getattr(candidate,'browser',None)==browser and video_key(candidate.url)==video_key(url):
                    self.player=candidate;return self.control('play')
            except Exception:pass
            time.sleep(.15)
        return Result(False,'Music page requested. Bring it to the front to continue, sir.',{'requested':True},exact=True)
    def control(self,action,count=1):
        if not self.player:return Result(False,'Start your music session first, sir.',exact=True)
        if action not in ('play','pause','next','previous') or type(count) is not int or not 1<=count<=10:return Result(False,'Choose one player command and up to ten tracks, sir.',exact=True)
        if count>1 and action not in ('next','previous'):return Result(False,'Only next or previous can skip several tracks, sir.',exact=True)
        done=0
        def failed(message):
            prefix=f'Completed {done} of {count} skips. ' if count>1 else ''
            return Result(False,prefix+message,{'count':done,'requested_count':count},exact=True)
        for _ in range(count):
            if self.stop():return failed('Playback command stopped, sir.')
            try:ok,state=self.player.control(action)
            except Exception:
                r=failed('Bring the original music tab to the front, sir.');r.facts['stale']=True;return r
            if not ok:return failed('That player did not complete the command, sir.')
            done+=1
        text={'play':'Playing','pause':'Paused','next':'Next track','previous':'Previous track'}[action] if count==1 else f'{"Forward" if action=="next" else "Back"} {done} tracks'
        return Result(True,text+', sir.',{**state,'count':done},exact=True)
    def reject(self,selection):
        result=self.control('pause')
        if not result.ok:return result
        from .selection import SelectionCancelled
        def cancelled():return Result(True,'Paused. Choices cancelled, sir.',{'verified':True,'cancelled':True},exact=True)
        try:snapshot=selection.show('mixes',play=True)
        except SelectionCancelled:return cancelled()
        except ValueError:
            if self.stop():return cancelled()
            try:snapshot=selection.show('videos',play=True)
            except SelectionCancelled:return cancelled()
            except ValueError:return Result(True,'Paused. Show another playlist, sir.',{'verified':True},exact=True)
        if self.stop() or not selection.active or selection.active.choices.snapshot is not snapshot:return cancelled()
        return Result(True,'Which one do you want instead, sir?',{'verified':True,'awaiting_choice':True},exact=True)
    def adopt(self,provider,play=False):
        if self.stop():return None
        try:self.player=self.player_factory(provider)
        except Exception:self.player=None;return None
        return self.control('play') if play else None
