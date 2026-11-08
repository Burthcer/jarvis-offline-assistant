"""Explicit project aliases and natural starts, with no guessed profile or AI."""
import os,sys,tempfile
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-project-names-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.workspaces import save
pc=Fake(running=());store=Store(':memory:');app=App(pc,store,None,natural=False)
try:
 save(app.memory,'study',['notepad'],[],'edge',app.catalog,aliases=['College work','course-work'])
 for text in ('I want to continue working on college work','I would like to work on coursework','let\'s get back to college work','continue with course work'):
  # coursework has no explicit alias: it must not guess the closest profile.
  result=app.handle(text)
  if 'coursework' in text:
   assert not result.ok and not pc.log
  else:assert result.plan.kind=='ask' and 'study' in result.text and not pc.log,(text,result.plan.kind,result.text,pc.log)
 assert app.handle('I want to continue working on college work').plan.kind=='ask'
 assert app.handle('yes').ok and len(pc.log)==1
 assert app.handle('work on study').ok and len(pc.log)==1
 for name,aliases in [('college work',[]),('other',['study']),('other',['course work'])]:
  try:save(app.memory,name,['notepad'],[],'edge',app.catalog,aliases=aliases);raise AssertionError('ambiguous project name accepted')
  except ValueError:pass
 assert not app.handle('work on unlisted project').ok and len(pc.log)==1
finally:store.db.close();app.memory.db.close()
print('WORKSPACE NAMES: natural start, exact editable aliases, collision/unknown refusal, first preview and no repeated app launch passed')
