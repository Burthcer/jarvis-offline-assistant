"""Whole ledger/window flow, no real apps; later movement is never overwritten."""
import os,sys,tempfile
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-window-undo-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
pc=Fake();store=Store(':memory:');app=App(pc,store,None,natural=False)
try:
    for action in ('minimize','maximize','restore'):
        pc.window_poses={'edge':'maximize' if action=='restore' else 'restore'};original=dict(pc.window_poses)
        assert app.handle(action+' edge').ok
        assert app.handle('scratch that').ok and pc.window_poses==original
    app.handle('minimize edge');pc.window_poses['edge']='maximize'
    assert not app.handle('scratch that').ok and pc.window_poses['edge']=='maximize'
    app.handle('remember my city is Test City');app.handle('open notepad')
    assert not app.handle('scratch that').ok and store.notes('city'),'unsupported action undid an older local item'
    assert not any(x[0]=='close' for x in pc.log),'window rollback closed an app'
finally:store.db.close();app.memory.db.close()
print('WINDOW UNDO: exact prior minimize/maximize/restore, later-change refusal and external barrier passed')
