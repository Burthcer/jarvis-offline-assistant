"""Whole request routing, scoped-session readback and pivot. Never plays actual media."""
import os,sys,tempfile
from pathlib import Path
os.environ['JARVIS_SILENT']='1';os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='v3-music-')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.music import Music,destination,PagePlayer
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.legacy import settings
from jarvis3.selection import Selection
from jarvis3.choices import Choices

URL='https://www.youtube.com/watch?v=test&list=RDtest'
class Player:
    def __init__(self,provider):self.url=provider.url;self.browser=provider.browser;self.provider=provider;self.playing=False;self.calls=[];self.changed=False
    def control(self,action):
        if self.changed:raise ValueError('different tab')
        self.calls.append(action)
        if action in ('play','pause'):self.playing=action=='play'
        return True,{'playing':self.playing,'verified':True,'title':'Owned fake mix'}
class Provider:
    url=URL
    browser='edge'
    def __init__(self):self.opened=[]
    def snapshot(self,group):return Choices().capture(('own',),group,[dict(id=str(i),title='Mix '+str(i),bounds=(i*100,0,i*100+80,70),visible=True,enabled=True,group=group) for i in range(3)],(0,0,500,300))
    def invoke(self,item):self.opened.append(item.identity);return True
    def verify(self,item):return item.identity in self.opened
class Overlay:
    frames=0;error=None
    def show(self,*args):self.frames+=1
    def close(self,wait=True):pass

for bad in ('javascript:alert(1)','https://www.youtube.com/','https://user:secret@www.youtube.com/watch?v=x','https://www.youtube.com.evil.example/watch?v=x','https://www.youtube.com:8443/watch?v=x','https://www.youtube.com/account'):
    try:destination(bad);raise AssertionError(bad)
    except ValueError:pass
assert destination(URL)==URL
store=Store(':memory:');pc=Fake();app=App(pc,store,None,natural=False);provider=Provider();cfg={'music_url':URL,'music_browser':'edge'}
app.music=Music(cfg,pc.url,lambda:provider,app.stop_requested.is_set,Player)
app.selection=Selection(lambda:provider,Overlay,on_opened=app.music.adopt)
try:
    r=app.handle('I want to listen to music');assert r.ok and pc.log==[('url','edge',URL)] and app.music.player.calls==['play'],r.text
    assert app.handle('play music').ok and len(pc.log)==1,'existing session opened twice'
    assert app.handle('next two songs').ok and app.music.player.calls[-2:]==['next','next']
    from jarvis3.engine.understand import Plan,Call
    from datetime import datetime
    app.memory.routine_save('something else',[{'a':'open','args':{'target':'notepad'}}],datetime.now())
    before=list(pc.log);player=app.music.player;player.changed=True
    r=app.handle('pause');assert r.ok and pc.log!=before and app.music.player is None,('a music tab that is no longer in front hands over to whatever is in front (the owner, 7 Nov)',r.text)
    player.changed=False;app.music.player=player
    r=app.handle('something else');assert r.ok and r.results[0][1].facts.get('awaiting_choice') and app.music.player.calls[-1]=='pause',(r.text,r.plan,r.results)
    app.memory.routine_save('the second one',[{'a':'open','args':{'target':'notepad'}}],datetime.now())
    r=app.handle('the second one');assert r.ok and provider.opened==['1'] and app.music.player.calls==['play'],('a numbered choice opens at once, no yes first (the owner, 7 Nov)',r.text)
    app.music.player=None;pc.log.clear();cfg['music_url']=''
    assert not app.handle('I want to listen to music').ok and not pc.log
    assert not app.handle("I don't like this").ok and not pc.log
    cfg['music_url']=URL;app.stop_requested.set()
    assert not app.handle('I want to listen to music').ok and not pc.log
    app.stop_requested.clear()
    cfg=dict(settings.DEFAULTS,music_url=URL,music_browser='chrome');settings.save(cfg)
    assert settings.load()['music_url']==URL and settings.load()['music_browser']=='chrome','music preference lost after restart'
    class Button:pass
    try:PagePlayer._button([('Play (k)',Button()),('Play',Button())],'play');raise AssertionError('ambiguous player accepted')
    except ValueError:pass
finally:app.selection.cancel();store.db.close();app.memory.db.close()
print('MUSIC: whole start/reuse/scoped next-count/no global fallback/rejection/preview+yes pivot/cancellation/settings/URL/ambiguity checks passed')
