"""Private module/state isolation, real temporary SQLite, fake OS, no model/audio."""
import os,sys,tempfile,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
os.environ['JARVIS_SILENT']='1'
with tempfile.TemporaryDirectory(prefix='jarvis-v3-isolation-') as home:
    os.environ['JARVIS_V3_HOME']=home
    from jarvis3.paths import DATA,RUNTIME,prepare
    prepare()
    from jarvis3.engine import ui
    from jarvis3.engine.app import App
    from jarvis3.engine.osapi import Fake
    from jarvis3.engine.memory import Memory
    from jarvis3.legacy.store import Store
    from jarvis3.legacy import settings,voice,actions
    from jarvis3.engine import ai,credential_store
    assert not any(n=='jarvis' or n.startswith('jarvis.') or n=='jarvis2' or n.startswith('jarvis2.') for n in sys.modules),'V3 imported live V1/V2 code'
    assert Path(settings.PATH)==DATA/'settings3.json'
    assert Path(actions.START_CACHE).is_relative_to(RUNTIME)
    assert str(ROOT/'data/models') in ai.CHAT_MODEL and str(ROOT/'data/models') in voice.KOKORO[0]
    assert credential_store.TARGET=='JarvisOfflineAssistant/V4/GoogleReadOnly'
    store=Store();memory=Memory();pc=Fake();app=App(pc,store,None,memory,natural=False)
    for words in ('open notepad','what is my volume','open wifi settings','remember my university is Test College','copy my university'):
        reply=app.handle(words);assert reply.ok,(words,reply.text)
    assert (DATA/'facts.db').exists() and (DATA/'learning.db').exists()
    assert pc.log[-1]==('clipboard','Test College')
    assert len(store.notes('university'))==1
    store.db.close();memory.db.close()
baseline=json.loads((ROOT/'jarvis3/BASELINE.json').read_text(encoding='utf-8'))
for relative,digest in baseline['source_hashes'].items():
    assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,'V3 modified V2 source: '+relative
print('V3 PRIVATE IMPORTS / STATE / MODEL PATHS / V2 HASHES PASSED')
