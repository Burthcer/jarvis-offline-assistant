"""Own the exact test process tree; never launch models/mic or the user's apps."""
import os,sys,subprocess,tempfile,time
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[2]
folder=ROOT/'data/v3-dev-checks';folder.mkdir(parents=True,exist_ok=True)
log=folder/'desktop.log';owned={}
with tempfile.TemporaryDirectory(prefix='jarvis-v3-window-') as home,log.open('w',encoding='utf-8') as output:
    child=subprocess.Popen([str(ROOT/'data/runtime-v4/JarvisV4.exe'),'-u',str(ROOT/'tests/v3/test_window.py')],cwd=ROOT,env={**os.environ,'JARVIS_SILENT':'1','JARVIS_V3_HOME':home},stdout=output,stderr=subprocess.STDOUT)
    parent=psutil.Process(child.pid)
    try:
        end=time.monotonic()+80
        while child.poll() is None and time.monotonic()<end:
            try:
                for item in parent.children(recursive=True):owned[(item.pid,item.create_time())]=item
            except psutil.NoSuchProcess:break
            time.sleep(.1)
    finally:
        if child.poll() is None:parent.terminate()
        child.wait(timeout=10)
        for item in owned.values():
            try:
                if item.is_running():item.terminate()
            except psutil.NoSuchProcess:pass
        _,alive=psutil.wait_procs(list(owned.values()),timeout=5)
        for item in alive:
            try:item.kill()
            except psutil.NoSuchProcess:pass
text=log.read_text(encoding='utf-8');print(text)
assert child.returncode==0 and 'V3 UI ALL PASSED' in text,'V3 desktop test failed'
print('Owned V3 test tree closed. No test copy left running.')
