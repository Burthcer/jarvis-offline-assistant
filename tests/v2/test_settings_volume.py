"""Reported V2 settings-page and volume queries. Fake PC; no sound or changes."""
import os,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1'
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).parent)]
from harness import fresh

app,pc,_=fresh(SimpleNamespace(complete=lambda *a,**k:'open(target="settings")'))
if '--reproduce' in sys.argv:
    for words in ('open up Wi-Fi settings','open Bluetooth settings','what is my volume'):
        reply=app.handle(words)
        print(words,'=>',reply.text,pc.log[-1:] if pc.log else [],flush=True)
    sys.exit()
for words,page in [('open up Wi-Fi settings','ms-settings:network-wifi'),('open Bluetooth settings','ms-settings:bluetooth'),
                   ('could you open sound settings','ms-settings:sound'),('show me display settings','ms-settings:display'),
                   ('open settings for wi fi','ms-settings:network-wifi')]:
    pc.log.clear();reply=app.handle(words)
    assert reply.ok and pc.log==[('settings_page',page)],(words,reply.text,pc.log)
pc.log.clear();assert not app.handle('open made up settings').ok and not pc.log
assert app.handle('open settings').ok and ('open','settings','app',1,None) in pc.log
for words in ('what is my volume','what volume is it','what is the current volume','how loud is it',"what's the volume at"):
    pc.vol=37;pc.mute=False;pc.log.clear();reply=app.handle(words)
    assert reply.ok and '37 percent' in reply.text and not pc.log,(words,reply.text,pc.log)
pc.vol=0;pc.mute=True
reply=app.handle('what is my volume');assert reply.ok and '0 percent' in reply.text and 'muted' in reply.text
pc.log.clear();pc.app_vol['edge']=62
reply=app.handle('what is the volume of youtube');assert reply.ok and '62 percent' in reply.text and not pc.log,reply.text
reply=app.handle('what is my youtube volume');assert reply.ok and '62 percent' in reply.text,reply.text
pc.log.clear();pc.fail.add('settings_page')
assert not app.handle('open bluetooth settings').ok
with patch.object(pc,'volume',side_effect=OSError('device unavailable')):
    reply=app.handle('what is my volume');assert not reply.ok and 'could not read' in reply.text.lower()
from jarvis2.osapi import Real
from jarvis import actions
sent=[]
with patch.object(actions,'backend',SimpleNamespace(launch=lambda uri:sent.append(uri))):
    real=Real()
    assert real.settings_page('ms-settings:bluetooth') and sent==['ms-settings:bluetooth']
    assert not real.settings_page('file:///arbitrary.exe') and len(sent)==1
print('SETTINGS SUBPAGES / READ-ONLY VOLUME PASSED')
