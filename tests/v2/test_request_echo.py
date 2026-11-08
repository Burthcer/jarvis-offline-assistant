"""Reject repeated action requests; retry once, retaining useful questions."""
import os
import sys
from pathlib import Path
os.environ['JARVIS_SILENT'] = '1'
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).parent)]
from harness import fresh
from jarvis2.understand import request_echo

class Script:
    def __init__(self, replies): self.replies=iter(replies); self.calls=0
    def complete(self,*args,**kwargs): self.calls+=1; return next(self.replies)

ai=Script(['ASK: Open the Chrome browser, sir?', 'open(target="chrome")'])
app,pc,_=fresh(ai)
r=app.handle('I would like you to open the Chrome browser')
assert r.ok and ('open','chrome','app',1,None) in pc.log and ai.calls==2, (r.text,pc.log)
ai=Script(['ASK: Close Discord?', 'ASK: Close Discord?'])
app,pc,_=fresh(ai)
r=app.handle('Would you kindly close Discord')
assert not pc.log and r.error and 'Close Discord?' not in r.text
for text in ('Can you search up what is the weather?', 'search up on Edge what is the weather tomorrow'):
    app,pc,_=fresh(None)
    r=app.handle(text)
    assert r.ok and pc.log[-1][0]=='url', (text,r.text,pc.log)
assert not request_echo('open Chrome', 'Which app, sir?')
assert not request_echo('set a timer', 'How long, sir?')
assert request_echo('close the first tab','Did you mean to close the first tab?')
print('REQUEST ECHO CHECKS PASSED')
