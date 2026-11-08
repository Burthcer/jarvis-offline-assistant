"""Read only our disposable Edge accessibility tree; never user's browser/profile."""
import os,sys,tempfile,subprocess,time,shutil
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import psutil
from jarvis3.legacy.actions import Real
from jarvis3.engine.browser_tabs import WindowsTabs,operate
from jarvis3.engine import uia
edge=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
folder=Path(tempfile.mkdtemp(prefix='browser-probe-',dir=ROOT/'data/v3-dev-checks')).resolve()
marker='--user-data-dir='+str(folder)
def owned():return [p for p in psutil.process_iter(['cmdline','exe']) if marker in (p.info['cmdline'] or []) and (p.info['exe'] or '').lower()==str(edge).lower()]

def focus_owned(hwnd):
    """Focus this fixture without sending any global keyboard input."""
    import ctypes
    from ctypes import wintypes as w
    u=ctypes.windll.user32;k=ctypes.windll.kernel32
    u.GetForegroundWindow.restype=w.HWND
    u.GetWindowThreadProcessId.argtypes=[w.HWND,ctypes.POINTER(w.DWORD)]
    u.SetForegroundWindow.argtypes=[w.HWND]
    pid=w.DWORD();u.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
    assert pid.value in {p.pid for p in owned()},'Not an owned window'
    if u.GetForegroundWindow()==hwnd:return True
    current=k.GetCurrentThreadId();front=u.GetWindowThreadProcessId(u.GetForegroundWindow(),None)
    attached=bool(front and front!=current and u.AttachThreadInput(current,front,True))
    try:
        ok=u.SetForegroundWindow(hwnd);time.sleep(.08)
        print('OWNED FOCUS',bool(ok),u.GetForegroundWindow()==hwnd,flush=True)
        return u.GetForegroundWindow()==hwnd
    finally:
        if attached:u.AttachThreadInput(current,front,False)
try:
    pages=[]
    for i in range(6):
        p=folder/f'{i}.html';p.write_text(f'<title>V3 owned probe {i}</title><p>Test {i}</p>');pages.append(p.as_uri())
    if '--links' in sys.argv or '--adapter' in sys.argv:
        (folder/'0.html').write_text('<title>V3 owned probe 0</title><style>ul{display:grid;grid-template-columns:220px 220px;gap:30px;list-style:none}li{height:120px;border:1px solid #555}a{display:block;padding:15px}</style><ul>'+''.join(f'<li><a href="{pages[i+1]}">Test mix {i+1}</a></li>' for i in range(4))+'</ul>',encoding='utf-8')
    if '--player' in sys.argv:
        (folder/'0.html').write_text('''<title>V3 owned probe 0 silent player</title><h1>Fake controls, no audio/video element</h1>
<button id="play" aria-label="Play (k)" onclick="this.setAttribute('aria-label',this.getAttribute('aria-label')==='Play (k)'?'Pause (k)':'Play (k)')">Play / pause</button>
<button aria-label="Next (SHIFT+n)" onclick="move(1)">Next</button><button aria-label="Previous (SHIFT+p)" onclick="move(-1)">Previous</button>
<script>function move(n){let u=new URL(location.href);u.searchParams.set('v',Number(u.searchParams.get('v')||0)+n);history.pushState({},'',u);}</script>''',encoding='utf-8')
    child=subprocess.Popen([str(edge),marker,'--no-first-run','--no-default-browser-check','--disable-sync','--disable-extensions','--disable-background-networking','--new-window',*pages],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    backend=Real();backend._browsers=lambda:backend._process_windows({p.pid for p in owned()})
    end=time.monotonic()+15
    while time.monotonic()<end:
        windows=backend._browsers()
        if len(windows)==1 and 'V3 owned probe' in backend._title(windows[0]):break
        time.sleep(.2)
    assert len(windows)==1,'No single owned browser window'
    try:print('FIRST TAB RESULT',WindowsTabs(backend).list_tabs(),flush=True)
    except Exception as e:print('FIRST TAB ERROR',repr(e),flush=True)
    auto=uia._auto();root=auto.ControlFromHandle(windows[0]);queue=[(root,0)];n=0
    while queue and n<650:
        node,depth=queue.pop(0);n+=1
        if node.ControlTypeName in ('DocumentControl','EditControl'):continue
        if node.ControlTypeName in ('TabControl','TabItemControl'):print(depth,node.ControlTypeName,repr(node.Name),flush=True)
        queue.extend((c,depth+1) for c in node.GetChildren())
    try:print('TAB RESULT',WindowsTabs(backend).list_tabs(),flush=True)
    except Exception as e:print('TAB ERROR',repr(e),flush=True)
    if '--player' in sys.argv:
        focused=focus_owned(windows[0])
        assert focused or '--owned-background' in sys.argv,'Windows denied foreground; use the explicit owned-only background fixture mode'
        from jarvis3.browser_choices import BrowserChoices
        from jarvis3.music import PagePlayer
        provider=BrowserChoices(backend,windows[0],fixture_folder=folder)
        if not focused:
            # Exercise actual native page/controls while injecting ONLY the focus
            # boundary for this exact PID-checked fixture, never in product code.
            class OwnFocus:
                def __init__(self,u):self.u=u;self.handle=windows[0]
                def GetForegroundWindow(self):return self.handle
                def __getattr__(self,key):return getattr(self.u,key)
            provider.u=OwnFocus(provider.u)
            print('OWNED BACKGROUND FIXTURE: foreground check injected; native controls/URL/tab identity remain real',flush=True)
        player=PagePlayer(provider)
        times={'page':[],'tabs':[]}
        def measure(fn,key):
            def measured(*a,**k):
                started=time.perf_counter()
                try:return fn(*a,**k)
                finally:times[key].append(round((time.perf_counter()-started)*1000))
            return measured
        provider._native=measure(provider._native,'page');player._tab=measure(player._tab,'tabs')
        import cProfile,pstats
        profile=cProfile.Profile()
        if '--legacy-action' in sys.argv:
            class DefaultAction:
                def __init__(self,control):self.control=control
                def Invoke(self,waitTime=0):return self.control.GetLegacyIAccessiblePattern().DoDefaultAction(waitTime=waitTime)
            auto.ButtonControl.GetInvokePattern=lambda control:DefaultAction(control)
        for action in (('play','next','pause') if '--quick' in sys.argv else ('play','pause','play','next','next','previous','pause')):
            if '--profile' in sys.argv:profile.enable()
            start=time.perf_counter();ok,state=player.control(action)
            if '--profile' in sys.argv:profile.disable()
            print('NATIVE SILENT PLAYER',action,ok,state,'ms',round((time.perf_counter()-start)*1000),'parts',times,flush=True)
            times={'page':[],'tabs':[]}
            assert ok,(action,state)
        if '--profile' in sys.argv:pstats.Stats(profile).strip_dirs().sort_stats('cumtime').print_stats(15)
        if not focused:
            provider.u.handle=0
            try:player.control('play');raise AssertionError('Lost focus accepted')
            except ValueError:pass
            provider.u.handle=windows[0]
        tabs=WindowsTabs(backend);items=tabs.list_tabs()
        tabs.controls[items[1]['id']].GetSelectionItemPattern().Select()
        try:player.control('play');raise AssertionError('Wrong tab accepted')
        except ValueError:print('NATIVE PLAYER rejected a changed tab without a fallback',flush=True)
    if '--adapter' in sys.argv:
        assert focus_owned(windows[0]),'Windows denied the owned browser foreground'
        from jarvis3.browser_choices import BrowserChoices
        from jarvis3.selection import Selection
        from jarvis3.engine.app import App
        from jarvis3.engine.osapi import Fake
        from jarvis3.legacy.store import Store
        from jarvis3.overlay import TargetOverlay
        provider=BrowserChoices(backend,windows[0],fixture_folder=folder);start=time.perf_counter()
        store=Store(':memory:');app=App(Fake(),store,None,natural=False)
        app.selection=Selection(lambda:provider,TargetOverlay)
        try:
            reply=app.handle('number mixes');assert reply.ok,reply.text
            snapshot=app.selection.active.choices.snapshot;assert len(snapshot.items)==4,len(snapshot.items)
            print('NATIVE CARD CAPTURE+OVERLAY ms',round((time.perf_counter()-start)*1000),[i.title for i in snapshot.items],flush=True)
            time.sleep(1.5) # exercise repeated COM reads on the watcher thread
            assert app.selection.active is not None,'unchanged native scene was incorrectly invalidated by watcher'
            reply=app.handle('the second one');assert reply.plan.kind=='ask',reply.text
            reply=app.handle('yes');assert reply.ok and reply.results[0][1].facts.get('verified'),reply.text
            assert app.selection.active is None
            print('NATIVE WHOLE APP SELECT + OVERLAY: watcher thread, bare second, preview/yes, exact local navigation and cleanup PASSED',flush=True)
        finally:app.selection.cancel();store.db.close();app.memory.db.close()
    if '--links' in sys.argv:
        print('OWN BROWSER FOREGROUND',backend._front(windows[0]),flush=True)
        time.sleep(.8)
        import ctypes
        from ctypes import wintypes as wt
        user=ctypes.windll.user32;user.SendMessageTimeoutW.argtypes=[wt.HWND,wt.UINT,wt.WPARAM,wt.LPARAM,wt.UINT,wt.UINT,ctypes.POINTER(ctypes.c_size_t)]
        renderers=[c for c in uia._walk(root) if c.ClassName=='Chrome_RenderWidgetHostHWND' and c.NativeWindowHandle]
        print('OWN RENDERER HANDLES',len(renderers),flush=True)
        for c in renderers:
            result=ctypes.c_size_t();user.SendMessageTimeoutW(c.NativeWindowHandle,0x3d,0,-25,2,250,ctypes.byref(result))
            user.SendMessageTimeoutW(c.NativeWindowHandle,0x3d,0,-4,2,250,ctypes.byref(result))
            user.SendMessageTimeoutW(c.NativeWindowHandle,0x3d,0,1,2,250,ctypes.byref(result))
        time.sleep(.4)
        for c in uia._walk(root):
            if c.ControlTypeName in ('EditControl','HyperlinkControl','DocumentControl','ListItemControl'):
                try:value=c.GetValuePattern().Value
                except Exception:
                    try:value=c.GetLegacyIAccessiblePattern().Value
                    except Exception:value='NO VALUE'
                print('OWN PAGE',c.ControlTypeName,repr(c.Name),repr(value),c.BoundingRectangle,flush=True)
    if '--menu' in sys.argv:
        controls=uia._walk(root)
        buttons=[c for c in controls if c.ControlTypeName=='ButtonControl' and c.Name=='Tab search' and not c.IsOffscreen]
        assert len(buttons)==1,'No single observed owned Tab search button'
        buttons[0].GetInvokePattern().Invoke();time.sleep(.2)
        pids={p.pid for p in owned()}
        vertical=[]
        import ctypes
        from ctypes import wintypes as wt
        handles=[];user=ctypes.windll.user32
        callback=ctypes.WINFUNCTYPE(wt.BOOL,wt.HWND,wt.LPARAM)
        def collect(handle,unused):
            pid=wt.DWORD();user.GetWindowThreadProcessId(handle,ctypes.byref(pid))
            if pid.value in pids and user.IsWindowVisible(handle):handles.append(handle)
            return True
        scan=callback(collect);user.EnumWindows(scan,0)
        for handle in handles:
            top=auto.ControlFromHandle(handle)
            for c in uia._walk(top,{'MenuItemControl'}):
                print('OWN MENU',repr(c.Name),flush=True)
                if c.Name=='Turn on vertical tabs':vertical.append(c)
        vertical=list({tuple(c.GetRuntimeId()):c for c in vertical}.values())
        assert len(vertical)==1,[(c.Name,c.GetRuntimeId()) for c in vertical]
        vertical[0].GetInvokePattern().Invoke();time.sleep(.25)
        try:print('VERTICAL TAB RESULT',WindowsTabs(backend).list_tabs(),flush=True)
        except Exception as e:print('VERTICAL TAB ERROR',repr(e),flush=True)
        queue=[(root,0)];n=0
        while queue and n<650:
            node,depth=queue.pop(0);n+=1
            if node.ControlTypeName in ('DocumentControl','EditControl'):continue
            if node.ControlTypeName in ('TabControl','TabItemControl'):print('VERTICAL',depth,node.ControlTypeName,repr(node.Name),flush=True)
            queue.extend((c,depth+1) for c in node.GetChildren())
        if '--actions' in sys.argv:
            adapter=WindowsTabs(backend);original=[t['id'] for t in adapter.list_tabs()]
            result=operate(adapter,'close','second and third');assert result['ok'] and len(result['done'])==2,result
            assert [t['id'] for t in adapter.list_tabs()]==[i for n,i in enumerate(original,1) if n not in (2,3)]
            result=operate(adapter,'close','second and fourth');assert result['ok'] and len(result['done'])==2,result
            assert [t['id'] for t in adapter.list_tabs()]==[original[0],original[4]]
            result=operate(adapter,'close','second and fifth');assert not result['ok'] and not result['done']
            assert len(adapter.list_tabs())==2
            print('REAL VERTICAL CLOSE: consecutive/cumulative/nonconsecutive original positions and absent-target refusal PASSED',flush=True)
finally:
    processes=owned()
    for p in processes:
        try:p.terminate()
        except psutil.NoSuchProcess:pass
    _,alive=psutil.wait_procs(processes,timeout=4)
    for p in alive:
        if p in owned():p.kill()
    psutil.wait_procs(alive,timeout=3)
    assert not owned()
    assert folder.is_relative_to((ROOT/'data/v3-dev-checks').resolve())
    shutil.rmtree(folder,ignore_errors=True)
