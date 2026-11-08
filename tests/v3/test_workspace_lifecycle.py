"""Workspace edits/cancellation cannot replay stale plans or corrupt new progress.

Only fake launches and temporary in-memory state. No native windows or models.
"""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
with tempfile.TemporaryDirectory(prefix='v3-workspace-lifecycle-') as home:
 os.environ['JARVIS_V3_HOME']=home
 from jarvis3.engine.app import App
 from jarvis3.engine.osapi import Fake
 from jarvis3.legacy.store import Store
 from jarvis3.workspaces import save

 def fresh():
  store=Store(':memory:');pc=Fake(running=());app=App(pc,store,None,natural=False)
  return app,pc,store
 def close(app,store):store.db.close();app.memory.db.close()
 def progress(app):return app.memory._q('SELECT approved,cursor,state FROM workspaces WHERE name=?','study')[0]

 app,pc,store=fresh()
 try:
  save(app.memory,'study',['notepad','chrome'],[],'edge',app.catalog)
  assert app.handle('start workspace study').plan.kind=='ask'
  original=pc.open
  def edit_after_first(*args,**kwargs):
   result=original(*args,**kwargs)
   if args[0]=='notepad':save(app.memory,'study',['edge'],[],'edge',app.catalog)
   return result
  with patch.object(pc,'open',side_effect=edit_after_first):reply=app.handle('yes')
  assert not reply.ok and reply.results[0][1].facts['profile_changed']
  assert [x[:2] for x in pc.log]==[('open','notepad')],'old plan continued after its replacement was saved'
  assert progress(app)==('',0,'ready'),'old run overwrote the new profile approval/progress'
  preview=app.handle('start workspace study')
  assert preview.plan.kind=='ask' and 'edge' in preview.text.lower()
  assert len(pc.log)==1,'replacement ran without its own preview'
 finally:close(app,store)

 app,pc,store=fresh()
 try:
  save(app.memory,'study',['notepad'],[],'edge',app.catalog)
  app.handle('start workspace study')
  def edit_during_probe(*args):
   save(app.memory,'study',['edge'],[],'edge',app.catalog)
   return False
  with patch.object(pc,'verify_open',side_effect=edit_during_probe):reply=app.handle('yes')
  assert not reply.ok and not pc.log and progress(app)==('',0,'ready'),'inspection raced a saved replacement into an old launch'
 finally:close(app,store)

 for apps,wanted_requested in ((['notepad'],0),(['notepad','chrome'],1)):
  app,pc,store=fresh()
  try:
   save(app.memory,'study',apps,[],'edge',app.catalog)
   app.handle('start workspace study');original=pc.open
   def cancel_after_first(*args,**kwargs):
    result=original(*args,**kwargs);app.workspace_cancel.set();return result
   with patch.object(pc,'open',side_effect=cancel_after_first):reply=app.handle('yes')
   assert reply.ok and reply.results[0][1].facts['cancelled'] and progress(app)[1:]==(1,'paused')
   assert len(pc.log)==1
   reply=app.handle('resume workspace study')
   assert reply.ok and reply.results[0][1].facts['verified']
   assert reply.results[0][1].facts['requested']==wanted_requested,'resume counted already completed launches as new requests'
   assert progress(app)[1:]==(len(apps),'ready') and len(pc.log)==len(apps)
   assert not app.handle('resume workspace study').ok,'completed workspace remained indefinitely resumable'
  finally:close(app,store)
print('WORKSPACE LIFECYCLE: mid-run/probe profile edits stop stale effects, replacement progress protected, completed cancellation resumes once, current-dispatch counts and ready state passed')
