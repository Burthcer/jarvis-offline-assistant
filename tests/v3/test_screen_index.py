"""V4 silent screen index: natural targets, 'which one?' and the answer. Fake screens only: no real window is read or clicked."""
import sys
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jarvis3.screen_index import ScreenIndex, Element
from jarvis3.engine.uia import Refused

passed = failed = 0
def check(ok, name):
    global passed, failed
    passed += bool(ok); failed += not ok
    print(('PASS ' if ok else 'FAIL ') + name)


def el(name, kind='HyperlinkControl', x=0, y=0, value=''):
    return Element(name, kind, (x, y, x + 200, y + 40), '', value)


class Source:
    def __init__(self, items, page=('w', 'Fake page')):
        self.items, self.page, self.invoked = list(items), page, []
    def scan(self):
        return self.page, list(self.items)
    def invoke(self, element):
        self.invoked.append(element.name); return True


class Overlay:
    def __init__(self): self.shown, self.closed = [], False
    def show(self, snapshot, selected=None): self.shown.append([i.title for i in snapshot.items])
    def close(self, wait=True): self.closed = True


def youtube():
    return Source([el('Home', 'ButtonControl', 0, 0), el('Mixes', 'ButtonControl', 300, 0),
                   el('Mix – Travis Scott', x=0, y=200, value='u1'), el('Mix – Travis Scott', x=0, y=420, value='u1'),   # thumbnail + title: one target
                   el('Mix – Chill Synthwave', x=300, y=200, value='u2'), el('Mix – Lofi Beats', x=600, y=200, value='u3'),
                   el('Download', 'ButtonControl', 0, 600), el('Download options', 'ButtonControl', 300, 600),
                   el('Gaming Hub', x=0, y=700), el('Delete account', 'ButtonControl', 0, 800),
                   el('Reply', 'ButtonControl', 0, 900), el('Reply', 'ButtonControl', 0, 960)])


# 1. One clear match is clicked at once
src = youtube(); s = ScreenIndex(src)
r = s.target('download button')
check(r['status'] == 'clicked' and src.invoked == ['Download'], 'exact "download button" clicks Download, not "Download options"')
src = youtube(); s = ScreenIndex(src)
check(s.target('gaming channel')['status'] == 'clicked' and src.invoked == ['Gaming Hub'], '"gaming channel" finds the Gaming Hub link')
src = youtube(); s = ScreenIndex(src)
check(s.target('downlod')['status'] == 'clicked' and src.invoked == ['Download'], 'a misheard word still finds Download')

# 2. Several matches: shortlist, badges, nothing clicked
src = youtube(); ov = Overlay(); s = ScreenIndex(src, overlay_factory=lambda: ov)
r = s.target('mix playlist')
check(r['status'] == 'ambiguous' and r['count'] == 3 and not src.invoked, '"mix playlist" asks which of 3 mixes (the Mixes chip and the duplicate thumbnail are left out)')
check(ov.shown and ov.shown[-1] == ['Mix – Travis Scott', 'Mix – Chill Synthwave', 'Mix – Lofi Beats'], 'badges are shown only over the 3 shortlisted mixes, in reading order')

# 3. Answer by position
for said, want in (('the second one', 'Mix – Chill Synthwave'), ('2nd', 'Mix – Chill Synthwave'), ('number 3', 'Mix – Lofi Beats'),
                   ('the last one', 'Mix – Lofi Beats'), ('first', 'Mix – Travis Scott'), ('the middle one', 'Mix – Chill Synthwave'), ('number two', 'Mix – Chill Synthwave')):
    src = youtube(); ov = Overlay(); s = ScreenIndex(src, overlay_factory=lambda: ov); s.target('mix playlist')
    check(s.resolve(said) is not None and s.pick(said)['status'] == 'clicked' and src.invoked == [want] and ov.closed, f'"{said}" clicks {want}')

# 4. Answer by words from the title
for said, want in (('the chill synthwave one', 'Mix – Chill Synthwave'), ('the one with Travis Scott', 'Mix – Travis Scott'), ('lofi', 'Mix – Lofi Beats'), ('synth wave', 'Mix – Chill Synthwave')):
    src = youtube(); s = ScreenIndex(src); s.target('mix playlist')
    check(s.pick(said)['status'] == 'clicked' and src.invoked == [want], f'"{said}" clicks {want}')

# 5. Not an answer, cancel, out of range, changed screen
src = youtube(); s = ScreenIndex(src); s.target('mix playlist')
check(s.resolve('open notepad') is None, 'an unrelated command is not taken as an answer')
check(s.resolve('never mind') == 'cancel', '"never mind" cancels')
check(s.resolve('the fifth one') is None, 'a position that is not on the shortlist is not an answer')
src = youtube(); s = ScreenIndex(src); s.target('mix playlist'); src.items = [i for i in src.items if 'Chill' not in i.name]
try:
    s.pick('the second one'); ok = False
except Refused:
    ok = not src.invoked
check(ok, 'if the chosen item has gone from the screen, nothing is clicked')

# 6. Safety: risky labels are never clicked without a yes; two identical buttons ask
src = youtube(); s = ScreenIndex(src)
check(s.target('delete account')['status'] == 'risky' and not src.invoked, '"delete account" needs a yes first')
check(s.target('delete account', allow_risky=True)['status'] == 'clicked' and src.invoked == ['Delete account'], 'after the yes it is clicked')
src = youtube(); s = ScreenIndex(src)
check(s.target('reply')['status'] == 'risky' and not src.invoked, 'two Reply buttons: risky label, nothing clicked without a yes')
r = s.target('reply', allow_risky=True)
check(r['status'] == 'ambiguous' and r['count'] == 2 and not src.invoked, 'after the yes, two identical Reply buttons still ask which one')
src = youtube(); s = ScreenIndex(src)
try:
    s.target('subscribe now'); ok = False
except Refused:
    ok = not src.invoked
check(ok, 'something not on the screen is refused, nothing clicked')

# 7. Routing and the engine: "click X", then "the second one" goes to the shortlist before anything else
from jarvis3.engine.app import App
from jarvis3.engine.osapi import Fake
from jarvis3.legacy.store import Store
os_ = Fake(); src = youtube(); os_.screen = ScreenIndex(src)
app = App(os_, Store(':memory:'), None, natural=False, clock=lambda: datetime(2026, 11, 8, 12, 0))
r = app.handle('play the mix playlist')
check(r.plan.kind == 'ask' and 'Which one' in r.text and not src.invoked, f'"play the mix playlist" asks which one: {r.text!r}')
r = app.handle('the chill synthwave one')
check(r.ok and src.invoked == ['Mix – Chill Synthwave'], f'the answer clicks it: {r.text!r}')
r = app.handle('click the download button')
check(r.ok and src.invoked[-1] == 'Download', f'"click the download button" clicks at once: {r.text!r}')
r = app.handle('press the download button')
check(r.ok and src.invoked[-1] == 'Download', '"press the download button" is a click, not an unknown key')
n = len(src.invoked); r = app.handle('press enter')
check(len(src.invoked) == n and ('ui_press', 'enter') in os_.log, '"press enter" is still a key press')
n = len(os_.log); r = app.handle('click the second one')
check(len(src.invoked) == len(src.invoked) and not any(x[0] == 'ui_target' for x in os_.log[n:]), '"click the second one" with no shortlist is left to numbered choices')
app.handle('click mix'); r = app.handle('open notepad')
check(('open', 'notepad', 'app') in os_.log or any(x[:2] == ('open', 'notepad') for x in os_.log), 'a new command after "which one?" runs as a new command')
r = app.handle('click on delete account')
check(r.plan.kind == 'ask' and src.invoked[-1] != 'Delete account', 'risky click asks first')
r = app.handle('yes')
check(src.invoked[-1] == 'Delete account', 'yes clicks it')
# 8. the owner's first real test (8 Nov, YouTube): the menu exposes each entry twice in the same spot; a misheard word hit a sentence in another page
src = Source([el('History', x=125, y=522), el('History', x=125, y=522, value='https://www.youtube.com/feed/history'),
              el('Playlists', 'ListItemControl', 125, 600), el('Playlists', x=130, y=602), el('Watch later', x=125, y=700)])
s = ScreenIndex(src); r = s.target('history')
check(r['status'] == 'clicked' and src.invoked == ['History'], f'two identical History links in one place are ONE target: {r}')
r = s.target('playlists')
check(r['status'] == 'clicked' and src.invoked[-1] == 'Playlists', 'a list row and the link inside it are ONE target')
src = Source([el('Say “Jarvis, click Shorts”. Shorts should open.', 'ListItemControl', 0, 0), el('Home', x=0, y=100)])
s = ScreenIndex(src)
try:
    s.target('shots'); ok = False
except Refused:
    ok = not src.invoked
check(ok, 'a misheard word never clicks a long sentence that only sounds alike ("shots" vs a line mentioning Shorts)')
src = Source([el('Shorts', x=0, y=0)]); s = ScreenIndex(src)
check(s.target('shots')['status'] == 'clicked', 'a misheard word still finds a short label ("shots" -> Shorts)')
src = youtube(); s = ScreenIndex(src); s.target('mix playlist')
check(s.resolve('never mind Jarvis, let it be') == 'cancel', '"never mind Jarvis, let it be" cancels the question')
class Lazy(Source):
    """Edge's first answer is nearly empty until its page description switches on."""
    def __init__(self, items): super().__init__(items); self.calls = 0; self.settle = 0.01
    def scan(self):
        self.calls += 1; return self.page, (list(self.items) if self.calls > 1 else [])
src = Lazy([el('Shorts')]); s = ScreenIndex(src)
check(s.target('shorts')['status'] == 'clicked', 'a page that is still waking up gets one more look before "can\'t find"')

# 9. the owner, 8 Nov: 'open shots' / 'start shorts' should use what is on screen when it is not an app he has
os2 = Fake(); src2 = Source([el('Home', x=0, y=0), el('Shorts', x=0, y=60), el('Subscriptions', x=0, y=120)]); os2.screen = ScreenIndex(src2)
app2 = App(os2, Store(':memory:'), None, natural=False, clock=lambda: datetime(2026, 11, 8, 12, 0))
for said, want in (('open shots', 'Shorts'), ('start shorts', 'Shorts'), ('Open Shorts', 'Shorts'), ('go to subscriptions', 'Subscriptions'),
                   ('open up the shorts', 'Shorts'), ('Jarvis, start shots', 'Shorts')):
    n = len(src2.invoked); r = app2.handle(said)
    check(r.ok and src2.invoked[n:] == [want], f'"{said}" clicks {want} on screen: {r.text!r}')
n = len(src2.invoked); r = app2.handle('open notepad')
check(src2.invoked[n:] == [] and any(x[:2] == ('open', 'notepad') for x in os2.log), '"open notepad" still opens the app')
n = len(src2.invoked); r = app2.handle('open youtube')
check(src2.invoked[n:] == [] and any(x[:2] == ('open', 'youtube') for x in os2.log), '"open youtube" still opens the site')
app2.set_catalog({**app2.catalog, 'whatsapp': 'app'})          # like the owner's PC: WhatsApp is installed
src2.items += [el('WhatsApp', x=0, y=200), el('Two YouTube tabs', x=0, y=260), el('What', x=0, y=320), el('Command Prompt', x=0, y=380)]
for said in ('bring up WhatsApp', 'open two YouTube tabs', 'open what?', 'open command prompt'):
    n = len(src2.invoked); app2.handle(said)
    check(src2.invoked[n:] == [], f'"{said}" never clicks a lookalike on screen (gold sentences from his logs)')
n, m = len(src2.invoked), len(os2.log); r = app2.handle('open the moon base')
check(src2.invoked[n:] == [] and os2.log[m:] == [] and r.plan.source == 'ai', f'something neither known nor on screen goes the usual way, nothing clicked: {r.text!r}')

from jarvis3.engine.abilities.screen import route
for said in ('click screenshot', 'click screenshot of the current screen', 'play the previous song', 'play the next video', 'press enter', 'tap escape', 'select all', 'click the third link'):
    check(route(said) is None, f'"{said}" keeps its old route')
print(f'{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
