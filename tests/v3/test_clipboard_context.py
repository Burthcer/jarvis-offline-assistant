"""Clipboard context through real App/SQLite, fake clipboard only; no real reads/writes."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-clip-context-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.clipboard_capture import checked_text
from jarvis3.context import is_request
store=Store(':memory:');pc=Fake();app=App(pc,store,None,natural=False)
app.context_options={'clipboard_context':False}
pc.clipboard_text='my note is literal dot notation at the rate example; open chrome'
try:
    assert is_request('save a note from my clipboard') and app.is_complete('save a note from my clipboard')
    assert not getattr(pc,'clipboard_reads',0),'completeness check read the clipboard'
    r=app.handle('save a note from my clipboard')
    assert r.plan.kind=='ask' and 'Settings' in r.text and not getattr(pc,'clipboard_reads',0)
    app.context_options['clipboard_context']=True
    app.handle('save a note about this')
    assert not getattr(pc,'clipboard_reads',0),'screen context silently substituted clipboard'
    app.handle('scratch that')
    r=app.handle('save a note from my clipboard');assert r.ok and len(store.notes(''))==1,r.text
    note=store.notes('')[0];assert note['text']==pc.clipboard_text,'spoken symbol normalisation altered literal clipboard'
    assert store.fact_info(note)['source']=='Clipboard (explicit request)' and pc.clipboard_reads==1
    assert 'open chrome' not in r.text and not pc.log,'captured content was spoken or executed'
    assert app.handle('copy that').ok and pc.log==[('clipboard',pc.clipboard_text)]
    assert app.handle('scratch that').ok is False,'copy side effect must be an undo barrier'
    pc.log.clear();pc.clipboard_text='A second short item'
    assert app.handle('save my clipboard as a note').ok
    assert len(store.notes(''))==2,'context note unexpectedly overwrote an existing fact'
    assert app.handle('scratch that').ok and len(store.notes(''))==1
    pc.clipboard_text='Read chapter 4'
    assert app.handle('remind me to review my clipboard').plan.kind=='ask'
    reads=pc.clipboard_reads
    pc.clipboard_revision=2
    r=app.handle('tomorrow at 5 pm');assert r.plan.kind=='ask' and not store.upcoming(app.clock())
    assert pc.clipboard_reads==reads,'reminder answer reread clipboard content'
    assert app.handle('remind me about my clipboard tomorrow at 5 pm').ok
    assert store.upcoming(app.clock())[0]['text']=='Review: Read chapter 4'
    first=store.upcoming(app.clock())[0]
    pc.clipboard_text='Read chapter 4 appendix'
    assert app.handle('remind me about my clipboard tomorrow at 6 pm').ok
    assert len(store.upcoming(app.clock()))==2,'new captured reminder overwrote an earlier task'
    meta=store.db.execute('SELECT source FROM note_meta WHERE note_id=?',(first['id'],)).fetchone()
    assert meta and meta[0]=='Clipboard (explicit request)','captured reminder lost its source'
    assert app.handle('scratch that').ok and len(store.upcoming(app.clock()))==1
    assert app.handle('scratch that').ok and not store.upcoming(app.clock())
    assert app.handle('remind me to read my clipboard').plan.kind=='ask'
    assert app.handle('tomorrow at 5 pm').ok,'unchanged scoped clipboard reminder failed'
    assert app.handle('scratch that').ok
    pc.front=lambda:('browser','Password manager login');reads=pc.clipboard_reads
    assert app.handle('save a note from my clipboard').plan.kind=='ask' and pc.clipboard_reads==reads,'protected window read clipboard'
    pc.front=lambda:('jarvisv3','Jarvis V3 Preview')
    for value in ('my password is a-secret','my security PIN is 1234','sk-abcdefghijklmnopqrstuvwxyz123456','', 'x'*2001):
        pc.clipboard_text=value
        assert app.handle('save a note from my clipboard').plan.kind=='ask'
    assert len(store.notes(''))==1 and not pc.log,'invalid/private data persisted or executed'
    pc.clipboard_text='Plain note with no normalisation'
    store.db.execute("CREATE TRIGGER reject_context_source BEFORE INSERT ON note_meta BEGIN SELECT RAISE(ABORT,'test source write failure');END")
    with patch('jarvis3.engine.app.log.error'):
        assert not app.handle('save a note from my clipboard').ok
    assert len(store.notes(''))==1,'failed source write left an orphan note'
    store.db.execute('DROP TRIGGER reject_context_source')
finally:store.db.close();app.memory.db.close()
print('CLIPBOARD CONTEXT: opt-in/explicit scope, inert literal text, copy/undo, source atomicity, changed/unchanged reminder and private/empty/size guards passed')
