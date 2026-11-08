"""Uncertain objects, explicit kinds and oversized plans cannot partly execute."""
import os,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
with tempfile.TemporaryDirectory(prefix='v3-command-integrity-') as home:
 os.environ['JARVIS_V3_HOME']=home
 from jarvis3.engine.app import App
 from jarvis3.engine.osapi import Fake
 from jarvis3.legacy.store import Store
 from jarvis3.engine.understand import parse,system_prompt
 from jarvis3.engine.registry import Name,Ask
 from jarvis3.engine.understand import Env
 from datetime import datetime
 catalog={'chrome':'app','edge':'app','studio':'app','studio files':'folder','photos':'folder','youtube':'site','health and safety':'folder'}
 class PC(Fake):
  def catalog(self):return catalog
 for request,raw in [('close chrome and lunar doodad','close(target="chrome")'),
  ('open chrome, lunar doodad and edge','open(target="chrome")\nopen(target="edge")'),
  ('close edge and lunar doodad','close(target="edge")\nclose(target="microsoft edge")'),
  ('do not open chrome','open(target="chrome")'),("don't set a five minute timer",'timer_set(duration="five minutes")')]:
  pc=PC();st=Store(':memory:');app=App(pc,st,SimpleNamespace(complete=lambda *a,**k:raw),natural=False)
  try:
   reply=app.handle(request)
   assert reply.plan.kind=='ask' and not pc.log,(request,reply.text,pc.log)
   app.ai=SimpleNamespace(complete=lambda *a,**k:'close(target="edge")')
   assert not app.handle('yes').ok and not pc.log,'unbound yes revived a rejected action'
  finally:st.db.close();app.memory.db.close()
 pc=PC();st=Store(':memory:');app=App(pc,st,None,natural=False)
 try:
  assert app.handle('open photos folder').ok and pc.log[-1]==('open','photos','folder',1,None)
  pc.log.clear()
  reply=app.handle('open studio folder')
  assert not pc.log or all(row[2]=='folder' for row in pc.log),'explicit folder became app'
  pc.log.clear()
  env=Env('open edge folder',app.names,datetime.now())
  try:Name().convert('edge',env)
  except Ask:pass
  else:raise AssertionError('model stripped folder qualifier')
  assert app.handle('open studio app').ok and pc.log[-1][1]=='studio'
  pc.log.clear();assert app.handle('open the health and safety folder').ok
  assert pc.log==[('open','health and safety','folder',1,None)],'an exact named folder was split at and'
  for command in ('close both chrome and edge',):
   pc.log.clear();reply=app.handle(command)
   assert reply.ok and pc.log and all(row[0]=='close' for row in pc.log),(command,reply.text,pc.log)
  pc.log.clear()
  assert not app.handle('lewis lunar doodad').ok and not pc.log,'misheard target was guessed'
 finally:st.db.close();app.memory.db.close()
 try:parse('\n'.join('open(target="chrome")' for _ in range(6)))
 except ValueError:pass
 else:raise AssertionError('oversized model plan silently truncated')
print('COMMAND INTEGRITY: uncertain compounds execute nothing, explicit kinds respected, oversized plans refused')
