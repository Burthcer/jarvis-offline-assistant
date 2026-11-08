"""Overload is explicit and bounded; cached exact names keep corrections."""
import os,sys,queue
import threading
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
os.environ['JARVIS_SILENT']='1'
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).parent)]
import numpy as np
from jarvis2.ears import Ears,SR
from harness import fresh,CLOCK
from jarvis.actions import Real
from jarvis2.speaker import Speaker
ear=Ears(None,None,None,lambda h:None);notices=[];ear.on_problem=notices.append
for _ in range(16):ear.jobs.put(object())
job=ear._submit([np.zeros(SR,np.int16)],0,0)
assert job.cancelled and ear.jobs.qsize()==16 and notices
speaker=Speaker.__new__(Speaker);spoken=[]
speaker.v=SimpleNamespace(speakq=queue.Queue(),speak=spoken.append)
for i in range(5):speaker.v.speakq.put(str(i))
speaker.speak('latest')
assert speaker.v.speakq.qsize()==3 and spoken==['latest']
app,pc,_=fresh(None)
app.memory.alias_correct('edge','chrome','app',CLOCK)
assert app.names.match('edge',('app',))[0]=='chrome','exact name shortcut erased a correction'
backend=Real(); calls=[]
def command(*args,**kwargs):calls.append(1);return SimpleNamespace(stdout=r'C:\Program Files\Example.exe')
with patch('jarvis.actions.os.stat',return_value=SimpleNamespace(st_mtime_ns=1)),patch('jarvis.actions.subprocess.run',side_effect=command):
    assert backend.target('example.lnk')=='Example.exe'
    assert backend.target('example.lnk')=='Example.exe' and len(calls)==1
with patch('jarvis.actions.os.stat',return_value=SimpleNamespace(st_mtime_ns=2)),patch('jarvis.actions.subprocess.run',side_effect=command):
    backend.target('example.lnk');assert len(calls)==2,'changed shortcut was not invalidated'
from jarvis2.ui import Voice,UiApp
owner=SimpleNamespace(cfg={'voice_on':True,'speak_replies':True,'quiet_enabled':True,'quiet_start':'00:00','quiet_end':'23:59'})
voice=Voice(owner);voice.pending_speech=['queued before quiet hours'];voice.speaker=SimpleNamespace(speak=spoken.append)
with patch('jarvis2.preferences.quiet',return_value=True):voice.flush_speech()
assert spoken==['latest'] and not voice.pending_speech,'startup queue ignored quiet hours'
started=threading.Event();release=threading.Event();catalogs=[]
def discover(*args):catalogs.append(1);started.set();release.wait(2)
owner=SimpleNamespace(_catalog_refresh=threading.Lock(),q=queue.Queue(),engine=SimpleNamespace(os=SimpleNamespace(catalog=lambda:{'new app':'app'})))
with patch('jarvis2.ui.actions.start_apps',side_effect=discover):
    UiApp.refresh_apps(owner)
    assert started.wait(1)
    UiApp.refresh_apps(owner)
    release.set()
    assert owner.q.get(timeout=2)==('catalog',{'new app':'app'}) and catalogs==[1],'duplicate discovery workers were started'
print('BOUNDED VOICE QUEUE / EXACT NAMES / SHORTCUT CACHE PASSED')
