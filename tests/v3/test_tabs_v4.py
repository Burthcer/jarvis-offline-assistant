"""V4, the owner's log 8 Nov: 'Close Agent Focus Claude' closed Claude; 'Close the 2nd, 3rd and 4th Tap', 'Close the Tab 2 and 3',
'close all the tabs other than YouTube' failed. Fake tab strip only: no real browser."""
import json, os, sys
from pathlib import Path
from types import SimpleNamespace
os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from jarvis3.engine import understand
from jarvis3.engine.names import Names
from jarvis3.engine.browser_tabs import resolve, operate

passed = failed = 0
def check(ok, name):
    global passed, failed
    passed += bool(ok); failed += not ok
    print(('PASS ' if ok else 'FAIL ') + name)

names = Names({**json.loads((ROOT / 'data/gold/catalog.json').read_text(encoding='utf-8')), 'claude': 'app'})
calls = lambda s: (understand.instant(s, names) or (None, []))[1]

# 1. Two commands without 'and'
for said, want in (('Close Edge, focus Claude', [('close', {'target': 'edge'}), ('focus', {'target': 'claude'})]),
                   ('close edge focus claude', [('close', {'target': 'edge'}), ('focus', {'target': 'claude'})]),
                   ('Close Edge and focus Claude', [('close', {'target': 'edge'}), ('focus', {'target': 'claude'})]),
                   ('open notepad, close chrome', [('open', {'target': 'notepad'}), ('close', {'target': 'chrome'})])):
    got = calls(said)
    check(got == want, f'"{said}" -> {got}')

# 2. The model may never pair 'close' with what he said 'focus' to
env = lambda text: understand.Env(text, names, None, False)
for text, raw, ok in (('Close Agent Focus Claude', [('close', {'target': 'claude'})], False),
                      ('Close Agent Focus Claude', [('focus', {'target': 'claude'})], True),
                      ('close claude and focus edge', [('close', {'target': 'claude'}), ('focus', {'target': 'edge'})], True),
                      ('focus claude and close edge', [('close', {'target': 'claude'})], False),
                      ('open chrome then close it', [('open', {'target': 'chrome'})], True)):
    try:
        understand.verb_owner(raw, env(text)); result = True
    except ValueError:
        result = False
    check(result == ok, f'"{text}" with {raw}: {"allowed" if ok else "refused"}')

# 3. Tab sentences exactly as speech wrote them
for said, want in (('Closes 2nd, 3rd, 4th and 5th Tap', ('close', '2nd 3rd 4th and 5th')),
                   ('Close the 2nd, 3rd and 4th Tap', ('close', '2nd 3rd and 4th')),
                   ('Close the Tab 2 and 3', ('close', '2 and 3')),
                   ('close the second and third tabs', ('close', 'second and third')),
                   ('closed all the other tabs other than Youtube', ('close', 'all except youtube')),
                   ('Close all the tabs other than Youtube.', ('close', 'all except youtube')),
                   ('close all tabs except youtube', ('close', 'all except youtube')),
                   ('close every tab except the first one', ('close', 'all except first')),
                   ('close all the other tabs', ('close', 'all except this')),
                   ('close all tabs but this one', ('close', 'all except this'))):
    got = calls(said)
    sel = got[0][1] if got and got[0][0] == 'browser_tabs' else None
    check(sel and (sel['action'], ' '.join(sel['selector'].replace(',', ' ').split())) == want, f'"{said}" -> {got}')
check(calls('tap on shorts') and calls('tap on shorts')[0][0] == 'ui_click', '"tap on shorts" is still a click, not a tab')

# 4. What actually closes (fake tab strip)
tabs = [{'id': i, 'title': t, 'selected': i == 2} for i, t in enumerate(
    ['Claude', 'YouTube', 'lofi mix - YouTube', 'GitHub', 'India - Wikipedia'], start=1)]
titles = lambda sel: [t['title'] for t in resolve(sel, tabs)]
check(titles('all except youtube') == ['Claude', 'GitHub', 'India - Wikipedia'], 'all except YouTube keeps BOTH YouTube tabs')
check(titles('all except this') == ['Claude', 'lofi mix - YouTube', 'GitHub', 'India - Wikipedia'], 'all the other tabs keeps the one in front')
check(titles('all except first') == ['YouTube', 'lofi mix - YouTube', 'GitHub', 'India - Wikipedia'], 'all except the first')
try:
    resolve('all except netflix', tabs); ok = False
except ValueError as e:
    ok = 'closed nothing' in str(e)
check(ok, 'nothing to keep found -> closes NOTHING (never "close everything")')
check(titles('2 and 3') == ['YouTube', 'lofi mix - YouTube'] and titles('2nd 3rd 4th and 5th') == ['YouTube', 'lofi mix - YouTube', 'GitHub', 'India - Wikipedia'], 'numbered lists')

class Strip:
    def __init__(self): self.tabs = [dict(t) for t in tabs]
    def list_tabs(self): return [dict(t) for t in self.tabs]
    def select(self, i): return True
    def close_target(self, i): self.tabs = [t for t in self.tabs if t['id'] != i]; return True
s = Strip(); r = operate(s, 'close', 'all except youtube')
check(r['ok'] and [t['title'] for t in s.tabs] == ['YouTube', 'lofi mix - YouTube'], f'operate: only the YouTube tabs remain: {r}')
s = Strip(); r = operate(s, 'close', '2 and 3')
check(r['ok'] and [t['title'] for t in s.tabs] == ['Claude', 'GitHub', 'India - Wikipedia'], 'operate: original tabs 2 and 3 closed (not shifted positions)')
print(f'{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
