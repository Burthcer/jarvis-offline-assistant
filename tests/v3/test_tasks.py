"""V4 multi-step tasks (observe -> act -> verify, max 5 steps). Fake screens that change when clicked, fake model; nothing real is opened or clicked."""
import json, os, sys
from datetime import datetime
from pathlib import Path
os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.screen_index import ScreenIndex, Element
from jarvis3.engine.abilities import tasks
tasks.SETTLE_S = tasks.APP_SETTLE_S = 0

passed = failed = 0
def check(ok, name):
    global passed, failed
    passed += bool(ok); failed += not ok
    print(('PASS ' if ok else 'FAIL ') + name)

def el(name, kind='TreeItemControl', y=0):
    return Element(name, kind, (0, y, 300, y + 40))

class Discord:
    """Three screens: server list -> server's channels -> the channel. Clicking moves between them."""
    def __init__(self):
        self.screens = {'home': [el('Direct Messages'), el('Gaming Hub', y=60), el('Study Group', y=120), el('Add a Server', 'ButtonControl', 180)],
                        'Gaming Hub': [el('Gaming Hub', y=60), el('general (text channel)', 'HyperlinkControl', 200), el('memes (text channel)', 'HyperlinkControl', 240),
                                       el('Delete channel', 'ButtonControl', 400), el('Inert button', 'ButtonControl', 440)],
                        'general (text channel)': [el('Message #general', 'EditControl', 900), el('Gaming Hub', y=60)]}
        self.now, self.invoked = 'home', []
    def scan(self): return ('discord', self.now), list(self.screens[self.now])
    def invoke(self, e):
        self.invoked.append(e.name)
        if e.name in self.screens: self.now = e.name
        return True

class Model:
    def __init__(self, *replies): self.replies, self.asked = list(replies), []
    def complete(self, msgs, **kw):
        self.asked.append(msgs[-1]['content']); return self.replies.pop(0) if self.replies else '{"action":"DONE"}'

def setup(ai=None):
    pc = Fake(); src = Discord(); pc.screen = ScreenIndex(src)
    app = App(pc, Store(':memory:'), None, natural=False, clock=lambda: datetime(2026, 11, 8, 12, 0), chat_ai=ai)
    app.set_catalog({**app.catalog, 'discord': 'app'})          # the fake PC has Discord installed
    return pc, src, app

# 1. The spec's example, no model needed
pc, src, app = setup()
r = app.handle('Go to Discord, open the Gaming Hub server, and click the general channel')
opened = [x for x in pc.log if x[0] in ('open', 'focus')]
check(opened and opened[0][1] == 'discord', f'step 1 brings Discord up: {opened}')
check(src.invoked == ['Gaming Hub', 'general (text channel)'] and r.ok, f'steps 2 and 3 click the server then the channel: {src.invoked} / {r.text!r}')
check('general' in r.text and 'Done' in r.text, f'he hears what was done: {r.text!r}')

# 2. A step that is not on screen and no model: stops, says how far it got, clicks nothing else
pc, src, app = setup()
r = app.handle('open discord, click the music server and click the general channel')
check(not r.ok and src.invoked == [] and 'music server' in r.text, f'stops at the missing step: {r.text!r}')

# 3. The model fills in a step it could not parse, with ONE numbered choice from the screen
ai = Model('{"action":"CLICK","n":2}')
pc, src, app = setup(ai)
r = app.handle('open discord, then open the server for gamers, then click the general channel')
check(src.invoked == ['Gaming Hub', 'general (text channel)'] and r.ok, f'model picked item 2 (Gaming Hub) for the vague step: {src.invoked} / {r.text!r}')
check(ai.asked and '[2]' in ai.asked[0] and 'Gaming Hub' in ai.asked[0] and 'open the server for gamers' in ai.asked[0], 'the model saw the numbered screen and the step')
for bad, why in (('{"action":"CLICK","n":99}', 'a number not on the screen'), ('I think you should click Gaming Hub', 'not JSON'),
                 ('{"action":"TYPE","n":1,"text":"rm -rf"}', 'typing words he never said'), ('{"action":"CLICK","n":4}', 'nothing changed after the click')):
    ai = Model(bad); pc, src, app = setup(ai)
    src.screens['home'][3] = el('Add a Server', 'ButtonControl', 180)
    r = app.handle('open discord, then open the server for gamers, then click the general channel')
    check(not r.ok and 'general (text channel)' not in src.invoked, f'model answer refused ({why}): {r.text!r}')
ai = Model('{"action":"ASK","question":"Which server do you mean, sir?"}'); pc, src, app = setup(ai)
r = app.handle('open discord, then open the server for gamers, then click the general channel')
check(r.plan.kind == 'ask' and 'Which server' in r.text and not src.invoked, 'the model may ask instead of guessing')

# 4. Ambiguous step: which one, then the rest continues
pc, src, app = setup(); src.screens['Gaming Hub'].append(el('general-2 (text channel)', 'HyperlinkControl', 280))
r = app.handle('open discord, click gaming hub, then click general')
check(r.plan.kind == 'ask' and 'Which one' in r.text and src.invoked == ['Gaming Hub'], f'two "general" channels: asks which: {r.text!r}')
r = app.handle('the first one')
check(src.invoked == ['Gaming Hub', 'general (text channel)'] and r.ok and 'Done' in r.text, f'the answer finishes the task: {r.text!r}')

# 5. Risky step needs a yes; no stops
pc, src, app = setup()
r = app.handle('open discord, click gaming hub, then click delete channel')
check(r.plan.kind == 'ask' and 'Delete channel' not in src.invoked, f'risky step asks first: {r.text!r}')
r = app.handle('no')
check('Delete channel' not in src.invoked, 'no: it is not clicked')
pc, src, app = setup()
app.handle('open discord, click gaming hub, then click delete channel'); r = app.handle('yes')
check(src.invoked[-1] == 'Delete channel', 'yes: it is clicked')

# 6. A click that changes nothing stops the task
pc, src, app = setup()
r = app.handle('open discord, click gaming hub, click inert button, then click general')
check(not r.ok and 'general (text channel)' not in src.invoked and 'nothing changed' in r.text.lower(), f'no visible change -> stop: {r.text!r}')

# 7. Limits and routing
pc, src, app = setup()
r = app.handle('open discord, click a, click b, click c, click d, click e')
check(not r.ok and '5' in r.text and not src.invoked and not [x for x in pc.log if x[0] == 'open'], f'more than 5 steps is refused before doing anything: {r.text!r}')
from jarvis3.engine.abilities.tasks import route
check(route('open notepad and open calculator') is None, 'two plain app opens stay the old quick command')
check(route('remind me to call mum, then open notepad') is None, 'no screen step: not a task')
check(route('open youtube and play the mix playlist') is not None, '"open youtube and play the mix playlist" is a task')
pc, src, app = setup()
r = app.handle('open discord, type hello there, then click gaming hub')
check(('ui_type', 'hello there') in pc.log, 'typing uses exactly his words')
ai = Model('{"action":"CLICK","n":1}'); pc, src, app = setup(ai); src.screens['home'].insert(0, Element('Search', 'EditControl', (0, -40, 300, -10)))
r = app.handle('open discord, then open my jazz playlist, then click the general channel')
check(not r.ok and src.invoked == [], f'a model "click" on a text box is a guess and is refused (real-model finding): {r.text!r}')
pc, src, app = setup()
r = app.handle('open discord, click gaming hub, then click inert button')
check(r.ok and src.invoked[-1] == 'Inert button' and 'no change' in r.text, f'the LAST click may change nothing: done, with a note: {r.text!r}')
print(f'{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
