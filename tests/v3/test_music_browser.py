"""Configured music browser is part of session identity, not just its URL."""
import os,sys
from pathlib import Path
from types import SimpleNamespace as NS
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.music import Music,PagePlayer
URL='https://www.youtube.com/watch?v=owned&list=RDowned'
provider=NS(url=URL,browser='edge');opened=[]
class Player:
    def __init__(self,p):self.url=p.url;self.browser=p.browser;self.calls=[]
    def control(self,action):self.calls.append(action);return True,{'playing':action=='play','verified':True}
def launch(browser,url):opened.append((browser,url));provider.browser=browser;return True
cfg={'music_url':URL,'music_browser':'edge'}
music=Music(cfg,launch,lambda:provider,player_factory=Player)
assert music.start().ok and opened==[('edge',URL)]
old=music.player;cfg['music_browser']='chrome'
assert music.start().ok and opened==[('edge',URL),('chrome',URL)] and music.player is not old,'browser preference change reused old browser'
assert old.calls==['play'] and music.player.browser=='chrome'
# A requested browser can open in the background while another browser has
# the same URL in front. That foreground player must never be adopted/played.
attempts=[];players=[]
def wrong_player(p):
    attempts.append(True);player=Player(NS(url=URL,browser='edge'));players.append(player);return player
opened.clear();music=Music(cfg,lambda b,u:(opened.append((b,u)),True)[1],lambda:provider,stop=lambda:bool(attempts),player_factory=wrong_player)
assert not music.start().ok and opened==[('chrome',URL)] and players[0].calls==[] and music.player is None
# Native owner validation uses injected Win32/process objects only.
class User:
    def __init__(self):self.front=10;self.pid=23;self.reads=0
    def IsWindow(self,handle):return True
    def GetForegroundWindow(self):return self.front
    def GetWindowThreadProcessId(self,handle,out):self.reads+=1;out._obj.value=self.pid
user=User();owner=lambda pid:NS(name=lambda:'msedge.exe',create_time=lambda:7.)
assert PagePlayer._process_identity(10,user,owner)==(23,7.,'edge')
user.front=11
try:PagePlayer._process_identity(10,user,owner);raise AssertionError('background player accepted')
except ValueError:pass
user.front=10
try:PagePlayer._process_identity(10,user,lambda pid:NS(name=lambda:'python.exe',create_time=lambda:7.));raise AssertionError('non-browser owner accepted')
except ValueError:pass
def changed(pid):user.pid=24;return owner(pid)
try:PagePlayer._process_identity(10,user,changed);raise AssertionError('changed process accepted')
except ValueError:pass
print('MUSIC BROWSER: configured browser change creates the correct scoped session passed')
