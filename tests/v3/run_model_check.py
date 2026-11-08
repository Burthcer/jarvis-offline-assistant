"""Own one silent model check; yield immediately if the owner starts either Jarvis.

Never stops a user process. Only the spawned test and its recorded children
are terminated. A private data directory prevents modifying preview settings.
"""
import os,sys,time,tempfile,subprocess
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[2]
ALLOWED={'harness.py','replay_phase1.py','replay_interrupt.py','check_full_launch.py','experiment_prewarm.py','evaluate_separation_trial.py'}

def user_jarvis(owned):
    for p in psutil.process_iter(['pid','name']):
        if p.pid==os.getpid():continue
        if p.pid in owned:
            try:
                if p.create_time()==owned[p.pid]:continue
            except psutil.NoSuchProcess:continue
            except psutil.AccessDenied:pass
        name=(p.info['name'] or '').lower()
        if name in ('jarvis.exe','jarvisv3.exe','jarvisv4.exe'):return True
        if name in ('python.exe','pythonw.exe'):
            try:
                args=p.cmdline()[1:]
                if any(a.lower() in ('jarvis','jarvis2','jarvis3') for a in args):return True
            except (psutil.AccessDenied,psutil.NoSuchProcess):pass
    return False

def main():
    script=sys.argv[1]
    if script not in ALLOWED:raise ValueError('Choose a known silent V3 model check')
    if user_jarvis({}):print('DEFERRED: an existing Jarvis is running. No model test started.');return 2
    folder=ROOT/'data/v3-dev-checks';folder.mkdir(parents=True,exist_ok=True)
    owned={};reason=None
    with tempfile.TemporaryDirectory(prefix='v3-owned-model-') as home,(folder/(script+'.log')).open('w',encoding='utf-8') as log:
        child=subprocess.Popen([sys.executable,'-u',str(ROOT/'tests/v3'/script),*sys.argv[2:]],cwd=ROOT,env={**os.environ,'JARVIS_SILENT':'1','JARVIS_V3_HOME':home},stdout=log,stderr=subprocess.STDOUT)
        process=psutil.Process(child.pid);owned[process.pid]=process.create_time();end=time.monotonic()+360
        try:
            while child.poll() is None:
                try:children=process.children(recursive=True)
                except psutil.NoSuchProcess:break
                for p in children:
                    try:owned[p.pid]=p.create_time()
                    except psutil.NoSuchProcess:pass
                if user_jarvis(owned):reason='the owner started Jarvis; owned test stopped';break
                if time.monotonic()>end:reason='Owned test exceeded its time bound';break
                time.sleep(.2)
        finally:
            # Children can outlive their parent; keep exact PID/create-time pairs.
            try:
                for p in process.children(recursive=True):
                    try:owned[p.pid]=p.create_time()
                    except psutil.NoSuchProcess:pass
            except psutil.NoSuchProcess:pass
            for pid,created in reversed(list(owned.items())):
                try:
                    p=psutil.Process(pid)
                    if p.create_time()==created:p.terminate()
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            for pid,created in owned.items():
                try:
                    p=psutil.Process(pid)
                    if p.create_time()==created:p.wait(5)
                except psutil.NoSuchProcess:pass
            child.wait(timeout=5)
    print(('DEFERRED: '+reason) if reason else 'Finished '+script+' with exit '+str(child.returncode),flush=True)
    print('Owned test tree closed. Log:',folder/(script+'.log'),flush=True)
    return 2 if reason else child.returncode

if __name__=='__main__':sys.exit(main())
