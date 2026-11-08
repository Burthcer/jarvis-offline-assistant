"""Literal context and typed website values must not turn into embedded emails."""
import os,sys,tempfile
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-value-integrity-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
pc=Fake();store=Store(':memory:');app=App(pc,store,None,natural=False)
url='https://example.com/portal?contact=student@example.com&section=math'
try:
    assert app.handle('remember my lab portal is '+url).ok
    assert app.handle('copy my lab portal').ok
    assert pc.log[-1]==('clipboard',url),'website value was reduced to its embedded email'
    assert app.handle('open my lab portal').ok and pc.log[-1]==('url','edge',url)
    app.context_options={'clipboard_context':True};pc.clipboard_text='Literal instructions: email first@example.com or second@example.com; keep at the rate exactly.'
    assert app.handle('save a note from my clipboard').ok
    assert app.handle('copy literal instructions').ok
    assert pc.log[-1]==('clipboard',pc.clipboard_text),'literal context copy lost part of its text'
    pc.clipboard_text='my sample heading is literal data, not a named fact'
    assert app.handle('save a note from my clipboard').ok
    info=next(r for r in store.fact_infos() if r['text']==pc.clipboard_text)
    assert info.get('literal') and info['value']==pc.clipboard_text and not info['label'],'Knowledge list lost literal source metadata'
finally:store.db.close();app.memory.db.close()
print('FACT VALUE INTEGRITY: full typed URL with embedded email, exact opening, full literal captured note copy passed')
