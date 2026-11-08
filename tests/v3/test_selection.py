"""Whole app selection/preview/confirmation/session path; no native screen access."""
import os,sys,tempfile,time
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-selection-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.selection import Selection
from jarvis3.choices import Choices
from dataclasses import replace
class Provider:
    def __init__(self):self.page=('owned','one');self.clicked=[];self.moved=False
    def snapshot(self,group):
        raw=[dict(id=str(i),title=f'Test {i}',bounds=(i*100,0,i*100+80,70),visible=True,enabled=True,group=group) for i in range(1,4)]
        if self.moved:raw.reverse();raw[0]['bounds']=(10,100,90,170)
        return Choices().capture(self.page,group,raw,(0,0,500,300))
    def invoke(self,item):self.clicked.append(item.identity);return True
    def verify(self,item):return item.identity in self.clicked
class Overlay:
    def __init__(self):self.frames=0;self.error=None;self.closed=False;self.selected=None
    def show(self,snapshot,selected=None):self.frames+=1;self.selected=selected
    def close(self,wait=True):self.closed=True
provider=Provider();store=Store(':memory:');app=App(Fake(),store,None,natural=False)
app.selection=Selection(lambda:provider,Overlay)
try:
    reply=app.handle('number mixes');assert reply.ok and reply.results[0][1].facts['awaiting_choice']
    overlay=app.selection.active.overlay
    # V3 7 Nov: a chosen number opens at once (the owner asked for no 'Open X, sir?' step); the exact-target and fresh-scene checks remain.
    reply=app.handle('the second one');assert reply.ok and provider.clicked==['2'] and app.selection.active is None and overlay.closed
    app.handle('number mixes');provider.moved=True
    reply=app.handle('choose the first one');assert not reply.ok and provider.clicked==['2'],'reordered scene was clicked'
    provider.moved=False;app.handle('show choices');app.handle('cancel choices')
    assert app.selection.active is None and provider.clicked==['2']
    app.handle('show choices');session=app.selection.active
    session.choices.snapshot=replace(session.choices.snapshot,at=time.monotonic()-16)
    assert not app.handle('pick the second one').ok and app.selection.active is None and provider.clicked==['2']
    app.handle('show videos');reply=app.handle('pick the second mix playlist on screen')
    assert reply.ok and provider.clicked==['2','2'] and app.selection.active is None,'group change renumbers the mixes, then opens the second'
finally:app.selection.cancel();store.db.close();app.memory.db.close()
print('WHOLE SELECTION: bare ordinal, preview before yes, exact target, no/scratch/cancel, stale/moved scene, group change and expiry passed')
