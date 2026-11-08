"""Cancelled/superseded selection work cannot resurrect or close a new session."""
import os,sys,threading
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.selection import Selection
from jarvis3.choices import Choices
from jarvis3.engine.registry import Ask

class Provider:
    def __init__(self,blocked=False):self.entered=threading.Event();self.resume=threading.Event();self.blocked=blocked;self.calls=[];self.on_verify=None
    def snapshot(self,group):
        if self.blocked:self.entered.set();assert self.resume.wait(3)
        return Choices().capture(('owned',),group,[dict(id='one',title='Owned one',bounds=(0,0,80,60),visible=True,enabled=True,group=group)],(0,0,100,100))
    def invoke(self,item):self.calls.append(item.identity);return True
    def verify(self,item):
        if self.on_verify:self.on_verify()
        return item.identity in self.calls
class Overlay:
    def __init__(self):self.frames=0;self.error=None;self.closed=False
    def show(self,*a):assert not self.closed;self.frames+=1
    def close(self,wait=True):self.closed=True

def delayed_show(selection,errors):
    try:selection.show()
    except ValueError as e:errors.append(str(e))

old=Provider(True);overlays=[]
def overlay():o=Overlay();overlays.append(o);return o
selection=Selection(lambda:old,overlay);errors=[]
thread=threading.Thread(target=delayed_show,args=(selection,errors));thread.start()
try:
    assert old.entered.wait(1);selection.cancel();old.resume.set();thread.join(2)
    assert not thread.is_alive() and selection.active is None and errors and not overlays,'cancelled pending show resurrected'
finally:old.resume.set();thread.join(3);selection.cancel()

old=Provider(True);new=Provider();providers=iter([old,new]);selection=Selection(lambda:next(providers),Overlay);errors=[]
thread=threading.Thread(target=delayed_show,args=(selection,errors));thread.start()
try:
    assert old.entered.wait(1);selection.show();current=selection.active
    old.resume.set();thread.join(2)
    assert selection.active is current and errors and not current.overlay.closed,'superseded show replaced/closed a newer session'
finally:old.resume.set();thread.join(3);selection.cancel()

provider=Provider();selection=Selection(lambda:provider,Overlay)
def preview(play=False):
    selection.show(play=play)
    try:selection.pick(1,play=play);raise AssertionError('preview confirmation missing')
    except Ask as question:return question.pending
try:
    proof=preview();old_session=selection.active
    selection.on_opened=lambda *a:selection.show()
    result=selection.pick(1,True,proof)
    assert result.ok and old_session.overlay.closed and selection.active is not None and not selection.active.overlay.closed,'old commit cleanup cancelled newer choices'
    selection.cancel();selection.on_opened=lambda *a:None
    proof=preview(True);called=[];selection.on_opened=lambda *a:called.append(a)
    provider.on_verify=lambda:selection.cancel(wait=False)
    result=selection.pick(1,True,proof,play=True)
    assert not result.ok and result.facts['verified'] and result.facts['cancelled'] and not called and not result.facts['playing'],'cancel after opening still started playback'
    provider.on_verify=None;proof=preview(True)
    def unavailable(*a):raise RuntimeError('player unavailable')
    selection.on_opened=unavailable;result=selection.pick(1,True,proof,play=True)
    assert not result.ok and result.facts['verified'] and not result.facts['playing'] and 'Opened' in result.plain,'player failure lost completed navigation'
finally:selection.cancel()
print('SELECTION LIFECYCLE: pending cancel/supersession, scoped cleanup, post-open playback cancellation and partial failure passed')
