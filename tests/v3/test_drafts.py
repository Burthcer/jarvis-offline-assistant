"""V4 draft -> confirm -> send. A fake chat app only: nothing real is typed or sent. Enter is NEVER pressed without his 'send'."""
import os, sys
from datetime import datetime
from pathlib import Path
os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.screen_index import ScreenIndex, Element
from jarvis3.engine.abilities import drafts
drafts.SETTLE_S = 0

passed = failed = 0
def check(ok, name):
    global passed, failed
    passed += bool(ok); failed += not ok
    print(('PASS ' if ok else 'FAIL ') + name)

class Source:
    def __init__(self, names): self.items = [Element(n, 'ListItemControl', (0, 60 * i, 300, 60 * i + 50)) for i, n in enumerate(names)]; self.invoked = []
    def scan(self): return ('w', 'WhatsApp'), list(self.items)
    def invoke(self, e): self.invoked.append(e.name); return True

class AI:
    """Stands in for the local model: records what it was asked, answers with a fixed short message."""
    def __init__(self, reply): self.reply, self.asked = reply, []
    def complete(self, msgs, **kw): self.asked.append(msgs); return self.reply

def setup(names=('Rahul Sharma', 'Mum', 'College group'), ai=None):
    pc = Fake(); src = Source(names); pc.screen = ScreenIndex(src)
    app = App(pc, Store(':memory:'), None, natural=False, clock=lambda: datetime(2026, 11, 8, 12, 0), chat_ai=ai)
    return pc, src, app
typed = lambda pc: [x[1] for x in pc.log if x[0] == 'ui_type']
keys = lambda pc: [x[1] for x in pc.log if x[0] == 'ui_press']

# 1. Draft and hold: contact clicked, box focused, text typed, Enter NOT pressed
pc, src, app = setup(ai=AI("I'm out right now and can't reply. Talk later."))
r = app.handle("Reply to Rahul that I'm out and cannot reply, keep it short")
check(src.invoked == ['Rahul Sharma'] and ('ui_focus_field',) in pc.log, 'the contact is clicked and the message box focused')
check(typed(pc) == ["I'm out right now and can't reply. Talk later."], f'the model wrote the draft and it was typed: {typed(pc)}')
check('enter' not in keys(pc) and r.plan.kind == 'ask' and 'send' in r.text.lower(), f'Enter not pressed, he is asked: {r.text!r}')
prompt = app.chat_ai.asked[0][-1]['content']
check("I'm out and cannot reply" in prompt and 'short' in prompt.lower() and 'Rahul' in prompt, 'the model got his words, the contact and "short"')

# 2. Send
r = app.handle('send it')
check(keys(pc) == ['enter'] and r.ok and 'Sent' in r.text, f'"send it" presses Enter once: {r.text!r}')
r = app.handle('send it')
check(keys(pc) == ['enter'], 'a second "send it" later does not send again')

# 3. Cancel wipes the box
pc, src, app = setup(ai=AI('On my way.'))
app.handle('message mum that I am on my way')
r = app.handle('cancel')
check(keys(pc) == ['select all', 'backspace'] and 'enter' not in keys(pc), f'"cancel" clears the box with Ctrl+A, Backspace: {keys(pc)}')

# 4. Make it shorter / change it to: clear, rewrite, still waiting
pc, src, app = setup(ai=AI('I am on my way home now, will reach in about twenty minutes, see you soon.'))
app.handle('text mum saying I am on my way home')
app.chat_ai.reply = 'On my way home.'
r = app.handle('make it shorter')
check(keys(pc) == ['select all', 'backspace'] and typed(pc)[-1] == 'On my way home.' and r.plan.kind == 'ask', f'"make it shorter" rewrites and waits: {r.text!r}')
r = app.handle('change it to reaching in 10 minutes')
check(typed(pc)[-1] == 'Reaching in 10 minutes.' and 'enter' not in keys(pc), f'"change it to ..." types his words: {typed(pc)[-1]!r}')
r = app.handle('yes')
check(keys(pc)[-1] == 'enter', '"yes" sends')

# 5. Safety
pc, src, app = setup(ai=AI('Hello {Enter} there\nsecond line'))
app.handle('message mum that hello')
check(typed(pc) == ['Hello (Enter) there second line'], f'no newline or key code can sneak an Enter in: {typed(pc)}')
pc.ui_window = 'File Explorer'
r = app.handle('send')
check('enter' not in keys(pc) and not r.ok, f'if the window changed, nothing is sent: {r.text!r}')
pc, src, app = setup(ai=AI('Coming.'))
app.handle('message mum that coming'); pc.fail.add('draft_focus')
r = app.handle('cancel')
check(keys(pc) == [] , 'if the cursor left the message box, the box is not wiped (Ctrl+A could select other things)')
pc, src, app = setup(ai=AI('Coming.'))
app.handle('message mum that coming'); r = app.handle('open notepad')
check('enter' not in keys(pc) and any(x[:2] == ('open', 'notepad') for x in pc.log), 'another command runs as itself, the draft is left unsent')
r = app.handle('send it')
check('enter' not in keys(pc), 'after that, "send it" no longer sends the old draft')

# 6. Two similar contacts -> which one, then the draft continues
pc, src, app = setup(names=('Rahul Sharma', 'Rahul Verma', 'Mum'), ai=AI('Busy now.'))
r = app.handle('reply to rahul that I am busy')
check(r.plan.kind == 'ask' and 'Which one' in r.text and not typed(pc), f'two Rahuls: asks which: {r.text!r}')
r = app.handle('verma')
check(src.invoked == ['Rahul Verma'] and typed(pc) == ['Busy now.'] and 'send' in r.text.lower(), f'the answer picks him and the draft continues: {r.text!r}')
r = app.handle('send')
check(keys(pc) == ['enter'], 'then "send" sends')

# 7. Not on screen; no model; routes
pc, src, app = setup(ai=None)
r = app.handle('message Priya that I will call later')
check(not r.ok and 'Priya' in r.text and not typed(pc), f'a contact not on screen: nothing typed: {r.text!r}')
r = app.handle('message mum that I will call later')
check(typed(pc) == ['I will call later.'], f'without the model his own words are typed: {typed(pc)}')
from jarvis3.engine.abilities.drafts import route
check(route('tell me a joke') is None and route('tell me that you are fine') is None, '"tell me ..." is not a message')
check(route("tell Rahul that I'm late")[0][1]['contact'] == 'Rahul', '"tell Rahul that ..." is a message')
check(route('message mum on whatsapp that hi')[0][1].get('app') == 'whatsapp', '"on whatsapp" names the app')
print(f'{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
