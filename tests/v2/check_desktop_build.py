"""Check the actual desktop interpreter with fake data/OS/audio, then close our tree."""
import os,sys,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
import psutil
folder=ROOT/'data'/'completed-improvements-ui'
folder.mkdir(parents=True,exist_ok=True)
log=folder/'desktop-check.log'
owned={}
with log.open('w',encoding='utf-8') as output:
    child=subprocess.Popen([str(ROOT/'data/runtime/Jarvis.exe'),'-u',str(ROOT/'tests/v2/test_window.py'),str(folder),'--dark-start'],cwd=ROOT,env={**os.environ,'JARVIS_SILENT':'1'},stdout=output,stderr=subprocess.STDOUT)
    process=psutil.Process(child.pid)
    try:
        end=time.monotonic()+100
        while child.poll() is None and time.monotonic()<end:
            try:
                for item in process.children(recursive=True):owned[(item.pid,item.create_time())]=item
            except psutil.NoSuchProcess:break
            time.sleep(.2)
    finally:
        if child.poll() is None:process.terminate()
        child.wait(timeout=10)
        for item in owned.values():
            try:
                if item.is_running():item.terminate()
            except psutil.NoSuchProcess:pass
        _,alive=psutil.wait_procs(list(owned.values()),timeout=5)
        for item in alive:
            try:item.kill()
            except psutil.NoSuchProcess:pass
text=log.read_text(encoding='utf-8')
print(text)
assert child.returncode==0 and 'ALL OK' in text,'Desktop check failed; see '+str(log)
print('Actual desktop runtime checked; owned processes closed.')
