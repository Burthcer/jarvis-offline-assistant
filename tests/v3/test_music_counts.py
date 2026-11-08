"""Counted media uses verified prefixes and never replays after failure/cancel."""
import os,sys
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.music import Music
class Player:
    def __init__(self,fail=None):self.calls=[];self.fail=fail
    def control(self,action):
        self.calls.append(action)
        if len(self.calls)==self.fail:raise ValueError('changed native tab')
        return True,{'verified':True,'playing':True,'title':'Owned fixture'}
player=Player(2);music=Music({},None,None);music.player=player
result=music.control('next',3)
assert not result.ok and result.facts['count']==1 and result.facts['requested_count']==3 and '1 of 3' in result.plain and player.calls==['next','next']
player=Player();music.player=player;music.stop=lambda:len(player.calls)>=1
result=music.control('previous',4)
assert not result.ok and result.facts['count']==1 and '1 of 4' in result.plain and player.calls==['previous']
music.stop=lambda:False;player=Player();music.player=player
result=music.control('next',3)
assert result.ok and result.facts['count']==3 and '3 tracks' in result.plain and player.calls==['next']*3
before=list(player.calls)
for action,count in (('play',2),('next',0),('next',11),('next',True),('unknown',1)):
    assert not music.control(action,count).ok and player.calls==before
# A cancelled first group is not permission to retry another group.
from jarvis3.selection import Selection
from jarvis3.choices import Choices
class Provider:
    def __init__(self):self.groups=[]
    def snapshot(self,group):
        self.groups.append(group);selection.cancel()
        return Choices().capture(('owned',),group,[dict(id='a',title='Choice A',bounds=(0,0,80,60),visible=True,enabled=True,group=group)],(0,0,100,100))
class Overlay:
    frames=0;error=None
    def show(self,*a):self.frames+=1
    def close(self,wait=True):pass
provider=Provider();selection=Selection(lambda:provider,Overlay)
try:
    result=music.reject(selection)
    assert result.ok and result.facts.get('cancelled') and not result.facts.get('awaiting_choice')
    assert provider.groups==['mixes'] and selection.active is None,'cancelled pivot retried/resurrected another group'
finally:selection.cancel()
print('MUSIC COUNTS: partial failure/cancel prefix, no replay, counted success and invalid request refusal passed')
