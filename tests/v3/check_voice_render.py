"""Generate into memory only: confirm current Kokoro actually renders faster audio."""
import os,sys,tempfile
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-tts-speed-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.speaker import Speaker
import psutil
sp=Speaker()
try:
    sp.v._load_tts();sp.v.set_speed(1)
    slow=sp.v._synth('The speaking speed has been changed, sir.')
    for _ in range(3):sp.tune('faster')
    fast=sp.v._synth('The speaking speed has been changed, sir.')
    assert len(fast)<len(slow)*.9 and sp.v.speed==1.3,'Voice property changed without faster rendered speech'
    print('SILENT VOICE RENDER: seconds',round(len(slow)/sp.v.sr,2),'->',round(len(fast)/sp.v.sr,2),'speed',sp.v.speed,'RAM MB',round(psutil.Process().memory_info().rss/2**20),flush=True)
finally:sp.shutdown()
