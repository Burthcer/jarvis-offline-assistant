"""V4, the owner's second live test (8 Nov): Nth item in a list, 'first mix, Josie Edwards', collapse/close panels, scrolling, short replies.
The fake screen copies the layout measured on a real YouTube playlist page (numbers in front of the titles, a Collapse button)."""
import os, sys
from datetime import datetime
from pathlib import Path
os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
from jarvis3.screen_index import ScreenIndex, Element
from jarvis3.engine.abilities.screen import route, nth_route
from jarvis3.engine import understand

passed = failed = 0
def check(ok, name):
    global passed, failed
    passed += bool(ok); failed += not ok
    print(('PASS ' if ok else 'FAIL ') + name)

def el(name, kind='HyperlinkControl', x=0, y=0, w=400, h=90, value=''):
    return Element(name, kind, (x, y, x + w, y + h), '', value)

def watch_page():
    playlist = [el('John Michael Howell - Missing Piece [OFFICIAL LYRIC VIDEO] JohnMichaelHowell', x=1571, y=448),
                el('2 Ian Asher - Take Me (To The Moon) (Official Audio) Ian Asher', x=1571, y=553),
                el('3 Ian Asher - Way Too Self Aware (Official Audio) Ian Asher', x=1571, y=658),
                el('4 With You | AMV | Anime Mix Jasi Amvs', x=1571, y=763),
                el('5 Self Aware LUM!X', x=1571, y=868),
                el('6 misery. - pupsies (Lyrics) i miss that kind of misery VibesOnly', x=1571, y=973),
                el('7 Ian Asher & Phantogram- Black Out Days (Official Audio) Ian Asher', x=1571, y=1078)]
    return [el('CBN27', x=1595, y=303, h=40), el('Collapse', 'ButtonControl', 2057, 308, 60, 60), el('Close', 'ButtonControl', 1980, 308, 60, 60),
            el('Loop playlist', 'ButtonControl', 1583, 376, 60, 60)] + playlist + [
            el('Mix – Josie Edwards - good girls (Official Music Video)', x=300, y=1300, value='https://y/watch?v=a&list=RDa'),
            el('Mix – John Michael Howell - Missing Piece', x=300, y=1400, value='https://y/watch?v=b&list=RDb'),
            el('Skip', 'ButtonControl', 900, 900, 80, 40)]

class Source:
    def __init__(self, items): self.items, self.invoked, self.scrolled = list(items), [], []
    def scan(self): return ('w', 'YouTube'), list(self.items)
    def invoke(self, e): self.invoked.append(e.name); return True
    def scroll(self, direction, amount='', area=None):
        self.scrolled.append((direction, amount, area is not None))
        self.items = [Element(e.name, e.kind, (e.bounds[0], e.bounds[1] - 300, e.bounds[2], e.bounds[3] - 300), e.automation_id, e.value) for e in self.items]
        return True

def setup():
    pc = Fake(); src = Source(watch_page()); pc.screen = ScreenIndex(src)
    return pc, src, App(pc, Store(':memory:'), None, natural=False, clock=lambda: datetime(2026, 11, 8, 15, 45))

# 1. the owner's exact sentences
pc, src, app = setup()
r = app.handle('Click the third video from this playlist')
check(src.invoked == ['3 Ian Asher - Way Too Self Aware (Official Audio) Ian Asher'], f'"third video from this playlist" = item 3 of the playlist: {src.invoked} / {r.text!r}')
check(r.text == 'Done, sir.', f'a long title is not read out: {r.text!r}')
r = app.handle('click the first video in the playlist')
check(src.invoked[-1].startswith('John Michael Howell'), 'the playing item (no number shown) is the first')
r = app.handle('play the last video in this playlist')
check(src.invoked[-1].startswith('7 Ian Asher'), 'the last one')
r = app.handle('click the second video by Ian Asher')
check(src.invoked[-1].startswith('3 Ian Asher'), f'"second video by Ian Asher" = the 2nd Ian Asher entry: {src.invoked[-1]}')
r = app.handle('Click on the first mix, Josie Edwards')
check(src.invoked[-1].startswith('Mix – Josie Edwards'), f'"first mix, Josie Edwards" clicks that mix: {r.text!r}')
for said in ('open mix josie edwards', 'start mix josie edwards', 'start the josie edwards mix', 'open the josie edwards mix'):
    n = len(src.invoked); r = app.handle(said)
    check(src.invoked[n:] and src.invoked[-1].startswith('Mix – Josie Edwards'), f'"{said}" clicks the Josie Edwards mix: {r.text!r}')
r = app.handle('click the ninth video in this playlist')
check(not r.ok and 'scroll' in r.text.lower(), f'a number not visible says to scroll first: {r.text!r}')

pc = Fake(); src = Source([e for e in watch_page() if not e.name[:1].isdigit() and 'Missing Piece [OFFICIAL' not in e.name] +
                          [el(f'Recommended video number {w} with a long title', x=1571, y=400 + 100 * i) for i, w in enumerate(('one', 'two', 'three', 'four'))])
pc.screen = ScreenIndex(src); app = App(pc, Store(':memory:'), None, natural=False)
r = app.handle('click the third video in this playlist')
check(not r.ok and src.invoked == [] and 'playlist' in r.text, f'no playlist on screen: refuses, never clicks a recommendation instead: {r.text!r}')

# 2. Panels: collapse / close / skip — the page's buttons, never the window
for said, want in (('collapse the playlist', 'Collapse'), ('close the playlist', 'Close'), ('skip the ad', 'Skip'), ('hide the playlist', 'Collapse')):
    pc, src, app = setup(); r = app.handle(said)
    check(src.invoked == [want], f'"{said}" presses {want}: {src.invoked} / {r.text!r}')

# 3. Scrolling
for said, want in (('scroll down a bit', ('down', 'bit', False)), ('scroll down', ('down', '', False)), ('scroll up', ('up', '', False)),
                   ('scroll the playlist down', ('down', '', True)), ('scroll down in the playlist', ('down', '', True)), ('scroll to the top', ('top', '', False)),
                   ('Scroll down a little bit', ('down', 'bit', False)), ('scroll down a lot', ('down', 'lot', False))):
    pc, src, app = setup(); r = app.handle(said)
    check(src.scrolled == [want] and r.ok, f'"{said}" scrolls {want}: {src.scrolled} / {r.text!r}')
pc, src, app = setup()
r = app.handle('scroll down, then click the second mix')
check(src.scrolled and src.invoked, f'"scroll down, then click the second mix" works as a task: {src.invoked} / {r.text!r}')

# 3b. 'number the screen' (spec Tier 2 on request), then a number
class Overlay:
    def __init__(self): self.shown = []
    def show(self, snapshot, selected=None): self.shown.append(len(snapshot.items))
    def close(self, wait=True): pass
for answer, want_index in (('click 12', 11), ('twelve', 11), ('number 3', 2), ('the first one', 0)):
    pc, src, app = setup(); ov = Overlay(); pc.screen.overlay_factory = lambda: ov
    r = app.handle('number the screen')
    numbered = list(pc.screen.shortlist)
    check(r.plan.kind == 'ask' and ov.shown and ov.shown[0] == len(numbered) and len(numbered) >= 12, f'"number the screen" shows {len(numbered)} numbers and asks: {r.text!r}')
    r = app.handle(answer)
    check(src.invoked == [numbered[want_index].name], f'"{answer}" presses number {want_index + 1}: {src.invoked}')

# 4. Routing never steals old commands
names = app.names
for said in ('click the first mix', 'click the second one', 'press enter', 'close whatsapp', 'close the window', 'close this tab', 'next video',
             'play the previous song', 'open notepad'):
    hit = understand.instant(said, names)
    check(not hit or not any(a in ('ui_nth', 'ui_click', 'scroll') for a, _ in hit[1]), f'"{said}" keeps its old route: {hit and hit[1]}')
check(nth_route('click the first mix') is None, 'bare "click the first mix" stays with V3 numbered choices')
print(f'{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
