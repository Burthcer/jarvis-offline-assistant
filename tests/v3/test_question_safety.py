"""A model must not turn questions/advice into effects. No model or PC access."""
import os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-question-')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
for words,raw in [('how do i open chrome','open(target="chrome")'),('what does closing chrome do','close(target="chrome")'),
                  ('can you tell me how to mute the computer','volume(action="mute")'),('is chrome open','open(target="chrome")'),
                  ('where is notepad installed','open(target="notepad")'),('how can i skip this track','media(action="next")')]:
    pc=Fake();store=Store(':memory:');app=App(pc,store,SimpleNamespace(complete=lambda *a,**k:raw),natural=False)
    result=app.handle(words)
    assert not pc.log,(words,pc.log,result.text)
    store.db.close();app.memory.db.close()
pc=Fake();store=Store(':memory:');app=App(pc,store,None,natural=False)
for words in ('could you open chrome','please close chrome','open notepad'):
    assert app.handle(words).ok,words
assert app.handle('what is my volume').ok
print('V3 QUESTIONS: instructions/status never become app or volume/media changes; direct commands preserved')
