"""Window-state requests cannot become a tab close through model routing.

Scripted bad output and fake PC only; no model/device/user browser is used.
"""
import os,sys,tempfile
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

with tempfile.TemporaryDirectory(prefix='v3-window-intent-') as home:
    os.environ['JARVIS_V3_HOME']=home
    from jarvis3.engine.app import App
    from jarvis3.engine.osapi import Fake
    from jarvis3.engine.understand import unsupported,Env
    from jarvis3.legacy.store import Store

    class Scripted:
        loaded=False
        def __init__(self):self.calls=0
        def complete(self,*a,**k):
            self.calls+=1
            return 'browser_tabs(action="close", selector="second")'

    for action in ('minimize','maximise','restore'):
        for text in (f'Do not close the second tab; just {action} Edge',
                     f'I want you to {action} the second tab, not close it'):
            pc=Fake();store=Store(':memory:');ai=Scripted();app=App(pc,store,ai,natural=False)
            try:
                reply=app.handle(text)
                assert ai.calls and not reply.ok and not pc.log,(text,reply.text,pc.log)
            finally:store.db.close();app.memory.db.close()

    # Guard all closing representations, while leaving supported focus alone.
    for ability,args in (('close',{'target':'edge'}),('tab_close',{'which':'second'}),
                         ('browser_tabs',{'action':'close','selector':'second'})):
        try:unsupported([(ability,args)],Env('minimize Edge, do not close the second tab',None,None))
        except ValueError:pass
        else:raise AssertionError('Window request allowed '+ability)
    unsupported([('browser_tabs',{'action':'focus','selector':'second'})],Env('minimize Edge and focus the second tab',None,None))

    # Deterministic clauses retain each explicit verb; a mixed request is not
    # silently rewritten into either closing everything or minimizing it all.
    for text,wanted in (
        ('minimize Edge and maximize Chrome',['window_state','window_state']),
        ('minimize Edge and close the second tab',['window_state','browser_tabs']),
        ('close second and fifth tabs and minimize Chrome',['browser_tabs','window_state']),
    ):
        pc=Fake();store=Store(':memory:');ai=Scripted();app=App(pc,store,ai,natural=False)
        try:
            reply=app.handle(text)
            assert reply.ok and ai.calls==0 and [e[0] for e in pc.log]==wanted,(text,reply.text,pc.log)
            if text.startswith('close second'):assert pc.log[0]==('browser_tabs','close','second and fifth')
            if text.startswith('minimize Edge and close'):assert pc.log[-1]==('browser_tabs','close','second')
        finally:store.db.close();app.memory.db.close()
print('WINDOW INTENT: negated close/window-state model guard, focus allowed, deterministic mixed/cumulative clauses passed')
