"""Window state and cumulative tab actions, no user apps or audio."""
import os, sys
from pathlib import Path
from types import SimpleNamespace
os.environ['JARVIS_SILENT']='1'
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).parent)]
from harness import fresh
from jarvis2.browser_tabs import operate
from jarvis2.understand import unsupported, Env

for text in ('minimize Edge','minimise all tabs','maximize this window','restore Chrome','minimize Edge and maximize Chrome'):
    app,pc,_=fresh(None)
    reply=app.handle(text)
    assert reply.ok, (text,reply.text,reply.error)
    assert all(entry[0]=='window_state' for entry in pc.log), pc.log
app,pc,_=fresh(None)
pc.fail.add('Edge')
assert not app.handle('minimize Edge').ok
try:
    unsupported([('close',{'target':'edge'})],Env('minimize Edge',None,None))
except ValueError: pass
else: raise AssertionError('minimize could become close')

class Tabs:
    def __init__(self):
        self.tabs=[{'id':i,'title':'Same title'} for i in range(1,7)]
        self.closed=[]; self.selected=None; self.refuse=None; self.reorder=False
    def list_tabs(self): return list(self.tabs)
    def select(self,identity): self.selected=identity; return True
    def close(self,identity):
        if identity==self.refuse: return False
        self.tabs=[t for t in self.tabs if t['id']!=identity]; self.closed.append(identity)
        if self.reorder: self.tabs.reverse()
        return True
for selector, expected in [('second, third and fourth',{2,3,4}),('second third and fourth',{2,3,4}),('fifth and second',{2,5}),('second and fifth',{2,5}),('2, 5 and 2',{2,5})]:
    tabs=Tabs(); r=operate(tabs,'close',selector)
    assert r['ok'] and set(tabs.closed)==expected, (selector,r,tabs.closed)
tabs=Tabs(); r=operate(tabs,'close','second and ninth')
assert not r['ok'] and not tabs.closed, r
tabs=Tabs(); tabs.refuse=2; r=operate(tabs,'close','second and fifth')
assert not r['ok'] and tabs.closed==[5] and len(r['done'])==1
tabs=Tabs(); tabs.reorder=True; r=operate(tabs,'close','second and fifth')
assert not r['ok'] and tabs.closed==[5], 'stop when external tab order changes'
tabs=Tabs(); r=operate(tabs,'focus','third')
assert r['ok'] and tabs.selected==3 and not tabs.closed
tabs=Tabs(); r=operate(tabs,'focus','Same title')
assert not r['ok'] and tabs.selected is None
tabs=Tabs(); tabs.tabs[1]['selected']=True
r=operate(tabs,'close','this');assert r['ok'] and tabs.closed==[2]
tabs=Tabs();tabs.tabs[-1]['title']='Other site'
r=operate(tabs,'close','all',r'Same title');assert r['ok'] and set(tabs.closed)=={1,2,3,4,5} and len(tabs.tabs)==1
app,pc,_=fresh(None)
assert app.handle('close second, third and fourth tabs').ok
assert pc.log[-1]==('browser_tabs','close','second, third and fourth')
pc.log.clear()
assert app.handle('open youtube and minimize Edge and maximize Chrome').ok
assert [entry[0] for entry in pc.log]==['open','window_state','window_state'],pc.log
print('WINDOW/TAB ACTION CHECKS PASSED')
