"""Injected Shell objects only; never enumerate the user's Explorer windows."""
import os,sys,subprocess,tempfile,time,json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.workspace_probe import native_folder,folder
from jarvis3.engine.osapi import Real
def item(path,exe='explorer.exe'):
 return NS(FullName=exe,Document=NS(Folder=NS(Self=NS(Path=path))))
class Windows:
 def __init__(self,items):self.items=items;self.Count=len(items)
 def Item(self,i):return self.items[i]
def shell(items):return NS(Windows=lambda:Windows(items))
assert native_folder(r'C:\Projects\Work',shell([item(r'C:\Projects\Work')])) is True
assert native_folder(r'C:\Projects\Work',shell([item('c:\\projects\\work\\')])) is True
assert native_folder(r'C:\Projects\Work',shell([item(r'C:\Other\Work')])) is False
assert native_folder(r'C:\Projects\Work',shell([item(r'C:\Projects\Work','browser.exe')])) is False
assert native_folder(r'C:\Projects\Work',shell([NS(FullName='explorer.exe')])) is None
class Changing:
 def __init__(self):self.count=0
 @property
 def Path(self):self.count+=1;return r'C:\Projects\Work' if self.count==1 else r'C:\Other'
unstable=item('');unstable.Document.Folder.Self=Changing()
assert native_folder(r'C:\Projects\Work',shell([unstable])) is None
with patch('jarvis3.workspace_probe.subprocess.run',side_effect=subprocess.TimeoutExpired('owned fake',1.5)):
 assert folder(r'C:\Projects\Work') is None
for output,wanted in [('true',True),('false',False),('null',None),('"true"',None),('broken',None)]:
 with patch('jarvis3.workspace_probe.subprocess.run',return_value=NS(stdout=output)):
  assert folder(r'C:\Projects\Work') is wanted
pc=Real.__new__(Real)
pc._workspace_tabs=NS(present=lambda *a:False,remember=lambda *a:True)
url='https://example.com/work?view=one'
with patch.object(pc,'reference',return_value={'program':'msedge','url':url}):
 assert pc.workspace_present('url',url,'edge') is True
 assert pc.workspace_present('url',url,'chrome') is False
 assert pc.workspace_present('url',url+'&other=1','edge') is False
with patch.object(pc,'reference',return_value={'program':'msedge','url':url}),patch.object(pc._workspace_tabs,'remember',return_value=False):
 assert pc.workspace_present('url',url,'edge') is False,'initial URL match hid a failed fresh tab/identity readback'
with patch.object(pc,'reference',return_value={'program':'msedge','url':None}):
 assert pc.workspace_present('url',url,'edge') is False
# Exercise the actual OS subprocess timeout and reap path with an owned helper,
# rather than claiming that a mocked TimeoutExpired proves cleanup.
real_run=subprocess.run
with tempfile.TemporaryDirectory(prefix='v3-owned-folder-timeout-') as temp:
 marker=Path(temp)/'pid.json'
 script="import os,sys,time,json;from pathlib import Path;import psutil;Path(sys.argv[1]).write_text(json.dumps([os.getpid(),psutil.Process().create_time()]));time.sleep(30)"
 def owned_helper(command,**kwargs):
  assert command[:3]==[sys.executable,'-m','jarvis3.workspace_probe']
  return real_run([sys.executable,'-c',script,str(marker)],**kwargs)
 start=time.monotonic()
 with patch('jarvis3.workspace_probe.subprocess.run',side_effect=owned_helper):
  assert folder(r'C:\Owned\Fixture') is None
 assert time.monotonic()-start<4,'helper timeout was not bounded'
 assert marker.exists(),'owned sleeping helper never started'
 import psutil
 pid,created=json.loads(marker.read_text())
 assert not psutil.pid_exists(pid) or psutil.Process(pid).create_time()!=created,'timed-out owned helper survived'
print('WORKSPACE PROBE: exact full path/case, wrong app, same-title mismatch, changed/error/timeout/invalid result refusal passed')
