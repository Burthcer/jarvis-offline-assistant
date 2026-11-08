"""Reuse requires exact OS readback, never title matching or a launch return."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-reuse-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.workspaces import save
pc=Fake(running=());store=Store(':memory:');app=App(pc,store,None,natural=False)
try:
 with tempfile.TemporaryDirectory(prefix='v3-folder-') as folder:
  url='https://example.com/project?view=work'
  save(app.memory,'reuse',['notepad'],[url],'edge',app.catalog,[folder])
  assert app.handle('start workspace reuse').plan.kind=='ask' and not pc.log
  assert app.handle('yes').ok
  before=list(pc.log)
  result=app.handle('start workspace reuse')
  assert result.ok and pc.log==before,'repeated workspace opened duplicate folder/URL'
  assert result.results[0][1].facts['verified'] and result.results[0][1].facts['reused']==3
  # Unknown observation must remain a dispatch, not a completion claim.
  with patch.object(pc,'workspace_present',return_value=None),patch.object(pc,'verify_open',return_value=None):
   result=app.handle('start workspace reuse')
  assert result.ok and not result.results[0][1].facts['verified']
  assert 'requested' in result.text.lower() and 'ready' not in result.text.lower()
  # Cancellation during slow inspection must prevent its following launch.
  save(app.memory,'cancel probe',[],[],'edge',app.catalog,[folder])
  assert app.handle('start workspace cancel probe').plan.kind=='ask'
  before=list(pc.log)
  def cancel(*args):app.workspace_cancel.set();return False
  with patch.object(pc,'workspace_present',side_effect=cancel):
   result=app.handle('yes')
  assert result.ok and result.results[0][1].facts.get('cancelled') and pc.log==before
  app.workspace_cancel.clear()
  # A later step can invalidate an earlier one; stale booleans cannot say ready.
  save(app.memory,'vanishing',['notepad','chrome'],[],'edge',app.catalog)
  pc._running.clear();assert app.handle('start workspace vanishing').plan.kind=='ask'
  original=pc.open
  def vanishing(*args,**kwargs):
   ok=original(*args,**kwargs)
   if args[0]=='chrome':pc._running.discard('notepad')
   return ok
  with patch.object(pc,'open',side_effect=vanishing):result=app.handle('yes')
  assert result.ok and not result.results[0][1].facts['verified'] and 'ready' not in result.text.lower()
  # Each URL must acquire a checked receipt before it can be reused later.
  save(app.memory,'two pages',[],[url,'https://example.com/other'],'edge',app.catalog)
  assert app.handle('start workspace two pages').plan.kind=='ask'
  assert app.handle('yes').ok
  before=list(pc.log)
  result=app.handle('start workspace two pages')
  assert result.ok and pc.log==before and result.results[0][1].facts['reused']==2
finally:store.db.close();app.memory.db.close()
print('WORKSPACE REUSE: exact folder/URL/app reuse and honest unknown readback passed')
