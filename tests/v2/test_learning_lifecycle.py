"""Teach, change and retain behaviour across a real local database restart.
Fake PC, no audio, no actual user data. Also check that learning edits no code.
"""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from contextlib import ExitStack
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).parent)]
os.environ['JARVIS_SILENT'] = '1'
from harness import CLOCK
from jarvis.store import Store
from jarvis2.app import App
from jarvis2.memory import Memory
from jarvis2.osapi import Fake


def code_hashes():
    paths = list((ROOT/'jarvis2').rglob('*.py')) + list((ROOT/'jarvis2/web').glob('*.*'))
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}


def check(cond, name):
    assert cond, name
    print('ok', name)


class Script:
    def complete(self, *a, **kw):
        return 'open(target="bluebird")'


before = code_hashes()
with tempfile.TemporaryDirectory() as folder, ExitStack() as cleanup:
    def start():
        instance = App(Fake(), Store(os.path.join(folder,'notes.db')), Script(),
                   memory=Memory(os.path.join(folder,'memory.db')), clock=lambda:CLOCK, natural=False)
        cleanup.callback(instance.memory.db.close)
        cleanup.callback(instance.store.db.close)
        return instance
    app = start()
    app.handle('open bluebird')
    r = app.handle('no I meant Chrome')
    check(r.ok and app.memory.alias_active('bluebird') == ('chrome','app'), 'one correction teaches a word')
    r = app.handle('when I say focus mode open notepad and open calculator')
    check(r.ok, 'new skill taught')
    app.os.log.clear()
    check(app.handle('focus mode').ok and [x[1] for x in app.os.log if x[0]=='open'] == ['notepad','calculator'], 'new skill actually runs its actions')
    r = app.handle('when I say focus mode open edge and open chrome')
    check(r.ok, 'same skill can be retaught with different actions')
    app.os.log.clear()
    check(app.handle('focus mode').ok and [x[1] for x in app.os.log if x[0]=='open'] == ['edge','chrome'], 'changed behaviour replaces old behaviour')
    check(not app.handle('when I say focus mode shut down').ok, 'unsafe reteaching refused')
    app.handle('remember my Gmail is first@alpha.test')
    app.handle('remember my Gmail is second@beta.test')
    r = app.handle('what is my Gmail')
    check('second@beta.test' in r.text and 'first@alpha.test' not in r.text, 'updated personal fact does not keep a conflicting old answer')
    app.handle('remember my work email is second@beta.test')
    check(len(app.store.notes('')) == 2, 'different fact names stay separate even with identical values')
    app.memory.db.close(); app.store.db.close()
    app = start()
    check(app.memory.alias_active('bluebird') == ('chrome','app'), 'correction survives restart')
    app.os.log.clear()
    check(app.handle('focus mode').ok and [x[1] for x in app.os.log if x[0]=='open'] == ['edge','chrome'], 'changed skill survives restart and unsafe edit did not replace it')
    check('second@beta.test' in app.handle('what is my Gmail').text, 'personal fact survives restart')
    app.memory.db.close(); app.store.db.close()
check(code_hashes() == before, 'learning changes saved behaviour, never program files')
print('LEARNING LIFECYCLE ALL PASSED')
