"""Next/previous act on the focused YouTube tab; other windows keep the normal media keys. Fake PC, no model."""
import os,sys,tempfile,types
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-frontmedia-')
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tests/v2')]
private=lambda text:text.replace('jarvis2.','jarvis3.engine.').replace('from jarvis import','from jarvis3.legacy import').replace('from jarvis.','from jarvis3.legacy.').replace("'jarvis.","'jarvis3.legacy.").replace('"jarvis.','"jarvis3.legacy.')
harness=types.ModuleType('harness');harness.__file__=str(ROOT/'tests/v2/harness.py');sys.modules['harness']=harness
exec(compile(private((ROOT/'tests/v2/harness.py').read_text(encoding='utf-8')),harness.__file__,'exec'),harness.__dict__)
class NoAI:
    def complete(self,msgs,temperature=0.0,max_tokens=90):raise AssertionError('model consulted: '+msgs[-1]['content'][-60:])
app,os_,store=harness.fresh(NoAI());app.natural=False
os_.front_title=('msedge','lofi hip hop radio - YouTube - Microsoft Edge')
os_.log.clear();r=app.handle('next');assert r.ok and ('front_keys',0x4E,True) in os_.log and not any(x[0]=='media' for x in os_.log),(r.text,os_.log)
os_.log.clear();r=app.handle('previous video');assert r.ok and ('front_keys',0x50,True) in os_.log,(r.text,os_.log)
os_.log.clear();r=app.handle('next two songs');assert r.ok and os_.log.count(('front_keys',0x4E,True))==2,(r.text,os_.log)
os_.log.clear();r=app.handle('pause');assert r.ok and not any(x[0]=='front_keys' for x in os_.log),'play/pause keep the system media path (K would toggle blindly)'
os_.log.clear();r=app.handle('fullscreen');assert r.ok and ('front_keys',0x46,False) in os_.log,'fullscreen goes to the focused YouTube tab'
os_.front_title=('msedge','Mix - YouTube Music - Microsoft Edge')
os_.log.clear();app.handle('next');assert not any(x[0]=='front_keys' for x in os_.log),'YouTube Music is not a watch page: media keys'
os_.front_title=('spotify','Spotify Premium')
os_.log.clear();app.handle('next');assert not any(x[0]=='front_keys' for x in os_.log),'other players: media keys'
print('FRONT MEDIA: next/previous go to the focused YouTube tab, play/pause and other players use media keys')
