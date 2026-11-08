"""Read public result cards in an OWNED, muted, signed-out browser. Never click/play."""
import os,sys,subprocess,tempfile,time,shutil,json
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import psutil
from jarvis3.legacy.actions import Real
from jarvis3.browser_choices import BrowserChoices
edge=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
folder=Path(tempfile.mkdtemp(prefix='youtube-readonly-',dir=ROOT/'data/v3-dev-checks')).resolve()
assert folder.is_relative_to((ROOT/'data/v3-dev-checks').resolve())
marker='--user-data-dir='+str(folder)
def owned():
    return [p for p in psutil.process_iter(['cmdline','exe']) if marker in (p.info['cmdline'] or []) and (p.info['exe'] or '').lower()==str(edge).lower()]
try:
    child=subprocess.Popen([str(edge),marker,'--no-first-run','--no-default-browser-check','--disable-sync','--disable-extensions','--mute-audio','--autoplay-policy=user-gesture-required','--new-window','https://www.youtube.com/results?search_query=instrumental+mix'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    backend=Real();backend._browsers=lambda:backend._process_windows({p.pid for p in owned()})
    deadline=time.monotonic()+25;error=None
    while time.monotonic()<deadline:
        try:
            windows=backend._browsers();assert len(windows)==1
            assert backend._front(windows[0])
            provider=BrowserChoices(backend,windows[0]);start=time.perf_counter()
            snap=provider.snapshot('videos')
            print('PUBLIC READ-ONLY CARDS',len(snap.items),'ms',round((time.perf_counter()-start)*1000),json.dumps([(i.title[:100],i.bounds) for i in snap.items],ensure_ascii=True),flush=True)
            assert len({i.bounds for i in snap.items})==len(snap.items),'Duplicate physical cards'
            assert len({i.title for i in snap.items})==len(snap.items),'Duplicate title links'
            break
        except Exception as ex:error=ex;time.sleep(1)
    else:raise RuntimeError('Read-only service probe failed: '+str(error))
finally:
    processes=owned()
    for p in processes:
        try:p.terminate()
        except psutil.NoSuchProcess:pass
    _,alive=psutil.wait_procs(processes,timeout=5)
    for p in alive:
        try:p.kill()
        except psutil.NoSuchProcess:pass
    assert not owned(),'Owned browser remains'
    shutil.rmtree(folder)
    print('Owned signed-out browser/profile closed; no links invoked, no playback requested.',flush=True)
