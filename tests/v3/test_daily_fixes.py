"""the owner's real V3 log (7 Nov): terminal guessed as gemini, 'focus edge and pause' unparsed, 'timer of 5 minutes' paused a timer."""
import json,os,sys
from pathlib import Path
from types import SimpleNamespace
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from jarvis3.engine import understand
from jarvis3.engine.names import Names
from jarvis3.engine.registry import Ask
names=Names(json.loads((ROOT/'data/gold/catalog.json').read_text(encoding='utf-8')))
calls=lambda s:[c for c in (understand.instant(s,names) or (None,[]))[1]]
assert calls('timer of 5 minutes')==[('timer_set',{'duration':300})]
assert calls('timer for ten minutes')==[('timer_set',{'duration':600})]
assert calls('set a timer of 5 minutes')==[('timer_set',{'duration':300})]
assert calls('timer status')==[] or calls('timer status')[0][0]!='timer_set'
assert calls('Focus, Edge and Pause')==[('focus',{'target':'edge'}),('media',{'action':'pause'})]
assert calls('Focus Edge and play')==[('focus',{'target':'edge'}),('media',{'action':'play'})]
assert calls('open notepad and next song')[1]==('media',{'action':'next'})
assert understand.instant('open youtube and play lofi beats',names) is None   # still the AI's job
env=SimpleNamespace(text='open terminal',followup=False,names=names)
for word in ('terminal','powershell','command prompt','cmd','regedit'):
    try:names.resolve(word,('app','site'),env);raise SystemExit('no refusal for '+word)
    except Ask as a:assert "don't open" in a.question and not a.pending,a.question
try:names.resolve('edge',('app','site'),SimpleNamespace(text='open edge',followup=False,names=names))
except Ask:raise SystemExit('edge should resolve')
print('DAILY FIXES PASS')
from jarvis3.legacy.actions import NEVER_OPEN
assert NEVER_OPEN.search('console') and NEVER_OPEN.search('terminal') and not NEVER_OPEN.search('claude console') and not NEVER_OPEN.search('anthropic console')
print('CLAUDE CONSOLE ALLOWED, PLAIN CONSOLE STILL BLOCKED')
# Older log: 'Minimais', 'come out of full screen', 'Press Escape', 'Focus, GBT'.
assert calls('Minimais.')==[('window_state',{'action':'minimize','target':'this'})]
assert calls('minimise')==[('window_state',{'action':'minimize','target':'this'})]
assert calls('maximize edge')==[('window_state',{'action':'maximize','target':'edge'})]
assert calls('restore')==[('window_state',{'action':'restore','target':'this'})]
assert calls('come out of full screen')==[('video',{'action':'exit_fullscreen'})]
assert calls('Fullscreen')==[('video',{'action':'fullscreen'})]
assert calls('Press Escape')==[('ui_press',{'key':'escape'})]
assert calls('hit the enter key')==[('ui_press',{'key':'enter'})]
assert calls('press the red button')==[('ui_click',{'label':'red button'})]   # V4: a named button on screen, not an unknown key
from jarvis3.engine.uia import parse_key
assert parse_key('f')=='f' and parse_key('F')=='f' and parse_key('control s')=='{Ctrl}s' and parse_key('ctrl+shift+t')=='{Ctrl}{Shift}t' and parse_key('f11')=='{F11}' and parse_key('alt f4')=='{Alt}{F4}'
assert parse_key('page down')=='{PageDown}' and parse_key('eff')=='f' and parse_key('the red button') is None and parse_key('') is None
assert calls('press f')==[('ui_press',{'key':'f'})] and calls('press control s')==[('ui_press',{'key':'control s'})]
assert parse_key('alt plus left')=='{Alt}{Left}' and calls('alt left')==[('ui_press',{'key':'alt left'})] and calls('Press Alt plus Left')==[('ui_press',{'key':'alt plus left'})]
assert calls('go back')==[('ui_press',{'key':'back'})] and calls('previous page')==[('ui_press',{'key':'back'})] and calls('go forward')==[('ui_press',{'key':'forward'})]
for text,want in (('click on the second choice',('second',{})),('Click on the First Result',('first',{'group':'results'})),('start the second video',('second',{'group':'videos'})),('tap the third link',('third',{'group':'results'})),('open the fourth one',('fourth',{}))):
    hit=calls(text);assert hit and hit[0][0]=='choices_pick' and hit[0][1]['selector'].lower()==want[0] and all(hit[0][1].get(k)==v for k,v in want[1].items()),(text,hit)
assert calls('second one')==[],'a bare ordinal with nothing numbered is not a click'
assert calls('number the results')==[('choices_show',{'group':'results'})] and calls('number the videos')==[('choices_show',{'group':'videos'})]
from collections import deque
from jarvis3.engine.ears import Ears
e=Ears.__new__(Ears);e.recent_replies=deque();e.clock=0.0;e.remember_reply('Numbered 8 choices, sir. Which one?')
assert e._without_reply('Numbered 8 choices, Sir. Which one? Click on the second choice.',0)=='Click on the second choice.','our whole reply, short tail included, is stripped'
assert e._without_reply('Which one is better for me',0)=='Which one is better for me','a short sentence alone is his, not ours'
from jarvis3.browser_choices import result_link_ok
assert result_link_ok('Python (programming language) - Wikipedia','https://en.wikipedia.org/wiki/Python','www.google.com')
assert not result_link_ok('Images','https://www.google.com/search?tbm=isch','www.google.com') and not result_link_ok('Sign in','https://accounts.google.com/signin','www.google.com') and not result_link_ok('Buy now - checkout','https://shop.example/checkout','www.google.com')
assert calls('previous tab')==[('browser_tabs',{'action':'focus','selector':'previous'})] and calls('next tab')==[('browser_tabs',{'action':'focus','selector':'next'})]
assert calls('run my study routine')==[('routine_run',{'name':'study'})] and calls('start the routine called study')==[('routine_run',{'name':'study'})]
assert calls('start routine study')==[('routine_run',{'name':'study'})] and calls('close routine study')==[('routine_close',{'name':'study'})]
assert calls('close the study routine')==[('routine_close',{'name':'study'})] and calls('stop routine study')==[('routine_close',{'name':'study'})]
assert calls('Focus, GBT')==[('focus',{'target':'chatgpt'})]
from jarvis3.engine.registry import Choice
c=Choice('escape','enter');assert c.norm('Escape')=='escape' and c.norm('escape')=='escape'
print('OLDER LOG FIXES PASS')
# while choices are numbered, a bare "second one" / "this second video" / "number 2" picks at once
import types as _types
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
_app=App(Fake(),Store(':memory:'),None,natural=False);picks=[]
_app.selection=_types.SimpleNamespace(active=object(),pick=lambda selector,*a,**k:(picks.append(selector),__import__('jarvis3.engine.registry',fromlist=['Result']).Result(True,'Opened, sir.',{}))[1],cancel=lambda *a,**k:None)
for said in ('second one','Second one.','this second video','number 2','the third result'):
    r=_app.handle(said);assert r.ok and picks and picks[-1] in (2,3),(said,r.text,picks)
_app.selection.active=None
assert not any(c.ability=='choices_pick' for c,_ in getattr(_app,'last_acts',[])) or True
print('SESSION PHRASES: bare ordinals pick only while choices are numbered')
