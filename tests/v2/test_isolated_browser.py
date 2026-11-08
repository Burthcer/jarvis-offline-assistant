"""Only an isolated Edge profile with disposable local HTML tabs is operated.
Never attach to the user's browser windows/profile, clipboard or accounts.
"""
import os,sys,time,tempfile,subprocess,shutil
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import psutil
from jarvis.actions import Real
from jarvis2.browser_tabs import WindowsTabs,operate
edge=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
profile=Path(tempfile.mkdtemp(prefix='jarvis-isolated-browser-',dir=ROOT/'data')).resolve()
assert profile.is_relative_to((ROOT/'data').resolve())
marker='--user-data-dir='+str(profile)
def owned():
    return [p for p in psutil.process_iter(['pid','cmdline','exe']) if marker in (p.info['cmdline'] or []) and (p.info['exe'] or '').lower()==str(edge).lower()]
try:
    pages=[]
    for i in range(6):
        title='Jarvis isolated unique' if i==5 else 'Jarvis isolated duplicate'
        file=profile/f'fixture-{i}.html';file.write_text('<title>'+title+'</title><p>Disposable test tab '+str(i)+'</p>',encoding='utf-8');pages.append(file.as_uri())
    child=subprocess.Popen([str(edge),marker,'--no-first-run','--no-default-browser-check','--disable-sync','--disable-extensions','--disable-background-networking','--force-renderer-accessibility','--new-window',*pages],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    backend=Real()
    backend._browsers=lambda:backend._process_windows({p.pid for p in owned()})
    end=time.monotonic()+15; tabs=[]; last=None
    while time.monotonic()<end:
        try:
            adapter=WindowsTabs(backend);tabs=adapter.list_tabs()
            if len(tabs)==6:break
        except Exception as error:last=str(error)
        time.sleep(.2)
    assert len(tabs)==6,('own isolated browser tabs not accessible',last,len(tabs))
    original=[t['id'] for t in tabs]
    if not backend._front(adapter.hwnd):
        keys=[];backend._chord=lambda *args:(keys.append(args),True)[1]
        result=operate(adapter,'focus','third')
        assert not result['ok'] and not keys,result
        print('SKIPPED active-tab actions: Windows denied foreground focus. Safe refusal verified.',flush=True)
        sys.exit(0)
    result=operate(adapter,'focus','third');assert result['ok'],result
    result=operate(adapter,'close','fifth and second');assert result['ok'],result
    remaining=[t['id'] for t in adapter.list_tabs()]
    assert remaining==[identity for index,identity in enumerate(original,1) if index not in (2,5)],remaining
    result=operate(adapter,'close','second and ninth');assert not result['ok'] and not result['done']
    assert len(adapter.list_tabs())==4
    from unittest.mock import patch
    from jarvis import actions
    from jarvis2.osapi import Real as AppOS
    opened=[];backend.open_url=lambda *args:opened.append(args)
    api=AppOS();api.sites['isolated unique']=('edge',pages[-1],None)
    with patch.object(actions,'backend',backend):
        assert api.open('isolated unique','site') and not opened,'existing unique tab was duplicated'
    result=operate(adapter,'close','all',r'duplicate')
    assert result['ok'] and len(result['done'])==3 and len(adapter.list_tabs())==1,result
    result=operate(adapter,'close','this')
    assert result['ok'] and not adapter.list_tabs(),result
    print('ISOLATED EDGE: duplicate titles, verified focus, original positions 5+2, absent position refusal PASSED',flush=True)
finally:
    processes=owned()
    for process in processes:
        try:process.terminate()
        except psutil.NoSuchProcess:pass
    _,alive=psutil.wait_procs(processes,timeout=5)
    for process in alive:
        if process in owned():process.kill()
    psutil.wait_procs(alive,timeout=3)
    assert not owned(),'own isolated browser still running'
    assert profile.is_relative_to((ROOT/'data').resolve())
    shutil.rmtree(profile,ignore_errors=True)
