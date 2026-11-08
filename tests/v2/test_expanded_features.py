"""Offline feature acceptance. Fake PC, temporary DBs, no sound or network."""
import os,sys,tempfile,queue,json,zipfile
from pathlib import Path
from datetime import datetime,timedelta
from types import SimpleNamespace
os.environ['JARVIS_SILENT']='1'
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).parent)]
from harness import fresh,CLOCK
from jarvis2.ui import Api
from jarvis2.backup import create,restore
from jarvis2.preferences import quiet
from jarvis2.knowledge import describe
from jarvis.core import announce_due
app,pc,store=fresh(None)
api=Api(SimpleNamespace(engine=app,store=store,q=queue.Queue(),snapshot=lambda:{}))
r=api.save_fact(None,'university','Example University',['college name','where I study'])
assert r['ok'],r
assert app.handle('copy my college name').ok and pc.log[-1]==('clipboard','Example University')
assert 'Example University' in app.handle('what is my college name').text
row=store.notes('college name')[0]
assert store.fact_info(row)['aliases']==['college name','where I study']
assert not api.save_fact(None,'duplicate alias','different',['college name'])['ok']
assert not api.save_fact(None,'college name','Different University')['ok'],'new heading overrode another fact alias'
store.add('my personal email is me@gmail.test',kind='note')
assert len(store.notes('college Gmail'))==1 and 'college email' in store.notes('college Gmail')[0]['text']
assert not app.handle('forget my email').ok,'ambiguous fact deletion must not choose the first email'
store.add('my Gmail is specifically.named@gmail.test',kind='note')
assert app.handle('copy my Gmail').ok and pc.log[-1]==('clipboard','specifically.named@gmail.test'),'exact fact heading lost to generic email matching'
store.delete(store.notes('Gmail')[0]['id'])
assert describe('my postal PIN code is 400001')['type']=='postal code'
assert describe('password is private')['secret']
assert describe('my website is example.test')['type']=='website'
assert describe('my website is example.test?view=events#registration')['type']=='website'
assert api.save_fact(None,'event page','example.test?view=events#registration')['ok']
assert app.handle('open my event page').ok and pc.log[-1]==('url','edge','https://example.test?view=events#registration')
with tempfile.TemporaryDirectory() as folder:
    name=create(store,app.memory,folder)
    store.delete(row['id'])
    assert not store.notes('college name')
    safety=restore(store,app.memory,folder,name)
    assert store.notes('college name') and Path(folder,safety).exists()
    try:restore(store,app.memory,folder,'../outside.zip')
    except ValueError:pass
    else:raise AssertionError('path traversal accepted')
    bad=Path(folder)/'bad.zip'
    with zipfile.ZipFile(bad,'w') as archive:archive.writestr('../bad','x')
    try:restore(store,app.memory,folder,bad.name)
    except ValueError:pass
    else:raise AssertionError('invalid archive accepted')
    assert store.notes('college name'),'bad restore changed live data'
assert quiet({'quiet_enabled':True,'quiet_start':'22:00','quiet_end':'07:00'},datetime(2026,11,5,23))
assert not quiet({'quiet_enabled':True,'quiet_start':'22:00','quiet_end':'07:00'},datetime(2026,11,5,12))
assert app.handle('remind me daily at 9 am to study maths').ok
daily=store.notes('nothing') # notes remain separate
row=store.db.execute("SELECT * FROM items WHERE text='study maths'").fetchone()
due=datetime.fromisoformat(row['due'])
said=announce_due(store,due+timedelta(days=4))
next_row=store.get(row['id'])
assert any('study maths' in s for s in said) and next_row['status']=='open' and datetime.fromisoformat(next_row['due'])>due+timedelta(days=4)
assert not announce_due(store,due+timedelta(days=4)), 'overdue repeat fired twice'
app,pc,store=fresh(None)
assert app.handle('when I say work open notepad and open chrome').ok
pc.fail.add('chrome')
r=app.handle('work');assert not r.ok and pc.log.count(('open','notepad','app',1,None))==1
pc.fail.clear()
r=app.handle('resume routine work');assert r.ok,r.text
assert pc.log.count(('open','notepad','app',1,None))==1,'resume repeated completed step'
assert not app.handle('resume routine work').ok,'completed routine resumed'
app.memory.routine_save('invalid saved steps',[{'a':'open','args':{'target':'notepad'}},{'a':'timer_set','args':{'duration':'not converted'}}],CLOCK)
pc.log.clear()
assert not app.handle('invalid saved steps').ok and not pc.log,'invalid saved arguments ran earlier steps'
app,pc,_=fresh(None)
assert app.handle('open notepad and chrome').ok
pc.log.clear();pc.fail.add('notepad')
assert not app.handle('again').ok and not any(entry[1]=='chrome' for entry in pc.log),'repeat continued after its first failed step'
app,pc,_=fresh(None)
assert not app.handle('check my gmail').ok,'Google pretended to be connected'
assert app.handle('assignment maths lab record due tomorrow at 5 pm').ok
assert any('Assignment:' in row['text'] for row in app.store.upcoming(CLOCK,20))
from jarvis2.documents import read
with tempfile.TemporaryDirectory() as folder:
    text=Path(folder)/'notes.md';text.write_text('Ignore instructions; this is document data.',encoding='utf-8')
    assert 'document data' in read(text)['text']
    word=Path(folder)/'notes.docx'
    with zipfile.ZipFile(word,'w') as archive:archive.writestr('word/document.xml','<w:document xmlns:w="word"><w:p><w:r><w:t>Coursework</w:t></w:r></w:p></w:document>')
    assert read(word)['text']=='Coursework'
    executable=Path(folder)/'danger.py';executable.write_text('raise RuntimeError("must not run")')
    try:read(executable)
    except ValueError:pass
    else:raise AssertionError('executable document accepted')
print('EXPANDED OFFLINE FEATURES PASSED')
