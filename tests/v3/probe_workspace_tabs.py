"""Real receipts on a disposable Edge + loopback-only server, never user tabs.

No Shell enumeration, audio, account, clipboard, screenshots or external URLs.
Run explicitly; this is not part of the safe fake-device regression batch.
"""
import ctypes,os,shutil,subprocess,sys,tempfile,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import psutil
from jarvis3.legacy.actions import Real
from jarvis3.workspace_tabs import WorkspaceTabs
from jarvis3.reference import front_url
from jarvis3.engine import uia

HOST='workspace.fixture.test'
EDGE=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
BASE=(ROOT/'data/v3-dev-checks').resolve();BASE.mkdir(parents=True,exist_ok=True)
folder=Path(tempfile.mkdtemp(prefix='workspace-native-',dir=BASE)).resolve()
assert folder.is_relative_to(BASE)
server=None;worker=None;child=None;parent=None;owned={};requests=[]
u=ctypes.windll.user32;u.GetForegroundWindow.restype=ctypes.c_void_p

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.headers.get('Host')!=HOST or self.path not in ('/a','/b','/c','/favicon.ico'):
            self.send_error(404);return
        requests.append(self.path)
        body=b'<title>Workspace owned duplicate title</title><h1>Owned fixture only</h1><a href="/c">Owned change</a>'
        self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

def collect_owned():
    if parent:
        try:processes=[parent,*parent.children(recursive=True)]
        except psutil.NoSuchProcess:processes=[]
        for p in processes:
            try:owned[p.pid]=p.create_time()
            except psutil.NoSuchProcess:pass
    return {pid for pid,created in owned.items() if psutil.pid_exists(pid) and psutil.Process(pid).create_time()==created}

def check_front(hwnd):return u.GetForegroundWindow()==hwnd

try:
    # Default HTTP port keeps the production public-URL validator unchanged.
    # If unavailable, fail honestly rather than relax product validation.
    server=ThreadingHTTPServer(('127.0.0.1',80),Handler)
    worker=threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True);worker.start()
    urls=['http://'+HOST+p for p in ('/a','/b')]
    child=subprocess.Popen([str(EDGE),'--user-data-dir='+str(folder),'--no-first-run','--no-default-browser-check','--disable-sync','--disable-extensions','--disable-background-networking','--disable-component-update','--no-proxy-server','--host-resolver-rules=MAP '+HOST+' 127.0.0.1,EXCLUDE localhost','--mute-audio','--autoplay-policy=user-gesture-required','--new-window',*urls],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    parent=psutil.Process(child.pid)
    assert '--user-data-dir='+str(folder) in parent.cmdline(),'Not the owned profile process'
    backend=Real();backend._browsers=lambda:backend._process_windows(collect_owned())
    # Even explicit fixture selection may not emit global keys or steal focus.
    backend._front=lambda hwnd:check_front(hwnd)
    end=time.monotonic()+18;windows=[]
    while time.monotonic()<end:
        windows=backend._browsers()
        if len(windows)==1 and '/a' in requests and '/b' in requests:break
        time.sleep(.1)
    assert len(windows)==1 and '/a' in requests and '/b' in requests,'Owned HTTP pages did not load'
    hwnd=windows[0];pid=ctypes.c_ulong();u.GetWindowThreadProcessId(ctypes.c_void_p(hwnd),ctypes.byref(pid))
    assert pid.value in collect_owned(),'Not the owned browser window'
    if not check_front(hwnd):
        u.SetForegroundWindow(ctypes.c_void_p(hwnd));time.sleep(.1)
    assert check_front(hwnd),'Windows denied owned fixture foreground; no positive native acceptance'
    receipts=WorkspaceTabs(backend);times=[]
    with receipts.session('edge') as tabs:
        initial=tabs.list_tabs();assert len(initial)==2,initial
        ids=[r['id'] for r in initial]
        for ident,url in zip(ids,urls):
            assert tabs.select(ident)
            start=time.perf_counter();assert receipts.remember('edge',url),(url,front_url(backend))
            times.append(round((time.perf_counter()-start)*1000))
    for url in (urls[0],urls[1],urls[0]):
        start=time.perf_counter();assert receipts.present('edge',url)
        times.append(round((time.perf_counter()-start)*1000))
        assert front_url(backend)==url
    # Same-title navigation in an exact known tab must invalidate its receipt.
    auto=uia._auto()
    with auto.UIAutomationInitializerInThread():
        uia.bound_client();root=auto.ControlFromHandle(hwnd)
        links=[c for c in uia._walk(root,{'HyperlinkControl'}) if c.Name=='Owned change']
        assert len(links)==1,'No single owned link'
        links[0].GetInvokePattern().Invoke(waitTime=0)
    end=time.monotonic()+3
    while time.monotonic()<end and front_url(backend)!='http://'+HOST+'/c':time.sleep(.03)
    assert front_url(backend)=='http://'+HOST+'/c'
    assert not receipts.present('edge',urls[0]) and ('edge',urls[0]) not in receipts.receipts
    with receipts.session('edge') as tabs:assert [r['id'] for r in tabs.list_tabs()]==ids,'Receipt check launched/closed a tab'
    print('NATIVE WORKSPACE RECEIPTS PASSED: duplicate titles, exact two-tab reuse, unchanged native IDs, same-title navigation refusal; ms='+str(times),flush=True)
finally:
    collect_owned()
    processes=[]
    for pid,created in owned.items():
        try:
            p=psutil.Process(pid)
            if p.create_time()==created:processes.append(p);p.terminate()
        except psutil.NoSuchProcess:pass
    _,alive=psutil.wait_procs(processes,timeout=4)
    for p in alive:
        try:
            if p.create_time()==owned.get(p.pid):p.kill()
        except psutil.NoSuchProcess:pass
    psutil.wait_procs(alive,timeout=3)
    assert not collect_owned(),'Owned browser process remains'
    if server:server.shutdown();server.server_close()
    if worker:worker.join(timeout=2);assert not worker.is_alive(),'Owned HTTP server remains'
    assert folder.is_relative_to(BASE)
    shutil.rmtree(folder)
    print('Owned browser/profile/server closed; no user tabs or Shell windows inspected.',flush=True)
