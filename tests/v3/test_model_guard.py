"""Never compete with another Jarvis or terminate a process outside our test.
Only disposable Python sleepers are launched; no model or user app starts.
"""
import os,sys,tempfile,subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_model_check as guard
fake=NS(pid=999999,info={'name':'Jarvis.exe'},create_time=lambda:200)
with patch.object(guard.psutil,'process_iter',return_value=[fake]):
 assert guard.user_jarvis({999999:100}),'reused owned PID hid a new user Jarvis'
 assert not guard.user_jarvis({999999:200}),'current owned child was mistaken for user app'
with tempfile.TemporaryDirectory(prefix='v3-guard-test-') as root:
 with patch.object(guard,'ROOT',Path(root)),patch.object(guard.sys,'argv',['guard','harness.py']),patch.object(guard,'user_jarvis',return_value=True),patch.object(guard.subprocess,'Popen') as launch:
  assert guard.main()==2 and not launch.called,'model check started with a user Jarvis already running'
 actual=subprocess.Popen;children=[];other=actual([sys.executable,'-c','import time;time.sleep(30)'],creationflags=subprocess.CREATE_NO_WINDOW)
 def sleeper(*args,**kwargs):
  child=actual([sys.executable,'-c','import time;time.sleep(30)'],**kwargs);children.append(child);return child
 try:
  with patch.object(guard,'ROOT',Path(root)),patch.object(guard.sys,'argv',['guard','harness.py']),patch.object(guard,'user_jarvis',side_effect=[False,True]),patch.object(guard.subprocess,'Popen',side_effect=sleeper):
   assert guard.main()==2
  assert len(children)==1 and children[0].poll() is not None,'owned model fixture survived deferral'
  assert other.poll() is None,'deferral stopped an unrelated fixture'
 finally:
  for child in children+[other]:
   if child.poll() is None:child.terminate()
   child.wait(5)
print('MODEL GUARD: reused-PID detection, no competing launch, exact owned cleanup and unrelated process preserved passed')
