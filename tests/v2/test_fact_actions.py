"""Saved facts and browser actions must act, never merely claim success."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ['JARVIS_SILENT'] = '1'
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).parent)]
from harness import fresh
from jarvis2.osapi import Real
from jarvis import actions

app, pc, store = fresh(None)
for heading, value in [('university','Example University'),('PIN code','400001'),('personal website','example.test'),('favourite book','A Book')]:
    store.add(f'my {heading} is {value}', kind='note')
    r = app.handle(f'copy my {heading} to the clipboard')
    assert r.ok and pc.log[-1] == ('clipboard',value), (heading,r.text,pc.log)
    assert value in app.handle(f'what is my {heading}').text
assert app.handle('open my personal website').ok
assert app.handle('open my website').ok
assert pc.log[-1] == ('url','edge','https://example.test'), pc.log
store.add('my unsafe link is javascript:alert(1)',kind='note')
assert not app.handle('open my unsafe link').ok
store.add('my security PIN is 1234',kind='note')
assert not app.handle('copy my security PIN').ok
pc.fail.add('clipboard')
assert not app.handle('copy my university').ok
app.handle('what is my nonexistent fact')
assert not app.handle('copy that').ok
for position in ('first','second','third','last'):
    assert app.handle(f'focus on the {position} tab').ok
    assert app.handle(f'switch to the {position} tab').ok
    assert pc.log[-1] == ('browser_tabs','focus',position)

real = Real()
real.entries['quick share'] = 'shell:AppsFolder\\NearbyShare_package!NearbyShare'
with patch.object(actions,'backend',SimpleNamespace(running=lambda:['NearbyShare.exe'])):
    assert real._app_exes('quick share') == ['NearbyShare.exe']
with patch.object(real,'browser_tabs',return_value={'ok':False,'done':[],'message':'No verified selection'}):
    assert not real.focus_tab('first'),'unverified key dispatch must not count as selection'
ai = SimpleNamespace(complete=lambda *a, **k:'CHAT: Your university has been copied to the clipboard, sir.')
app,pc,_ = fresh(ai)
assert 'has been copied' not in app.handle('perform something unknown').text
print('FACT ACTIONS PASSED (fake clipboard, browser and processes)')
