"""Choice identity/order/staleness core only; no live adapter or overlay claimed."""
import os,sys,tempfile
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-choice-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.choices import Choices
clock=[0];choices=Choices(lambda:clock[0]);clicked=[]
def item(i,title,x,y,**more):return dict(id=i,title=title,bounds=(x,y,x+90,y+40),visible=True,enabled=True,group='mixes',**more)
raw=[item('b','Evening mix',110,22),item('a','Morning mix',10,20),item('c','Study mix',10,90),item('x','Hidden mix',10,160)]
raw[-1]['visible']=False;raw.append(item('pay','Pay now',10,180));raw.append(dict(raw[0]))
snap=choices.capture(('window-1','page-1'),'mixes',raw,(0,0,300,200))
assert [i.identity for i in snap.items]==['a','b','c']
assert choices.resolve(2).identity=='b'
other=Choices(lambda:clock[0]);fresh=other.capture(snap.page,'mixes',raw,(0,0,300,200))
result=choices.commit(fresh,lambda i:(clicked.append(i.identity),True)[1],True)
assert clicked==['b'] and result['requested'] and not result['verified'],'Dispatch claimed verified completion'
try:choices.commit(fresh,lambda i:clicked.append(i.identity),True);raise AssertionError('preview reused')
except ValueError:pass
choices.resolve('Study');moved=[dict(r) for r in raw];moved[2]['bounds']=(120,90,210,130)
fresh=other.capture(snap.page,'mixes',moved,(0,0,300,200))
try:choices.commit(fresh,lambda i:clicked.append(i.identity),True);raise AssertionError('moved item selected')
except ValueError:pass
assert clicked==['b']
clock[0]=16
try:choices.resolve(1);raise AssertionError('expired snapshot resolved')
except ValueError:pass
try:choices.capture(snap.page,'mixes',[item('a','One',0,0),item('a','Two',100,0)],(0,0,300,200));raise AssertionError('duplicate identity accepted')
except ValueError:pass
print('CHOICE CORE: reading order, dedup, hidden/risky exclusion, unique title, one-shot preview, exact refresh and expiry passed; NOT a live adapter/overlay test')
