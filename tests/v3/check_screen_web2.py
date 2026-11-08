"""REAL sites, deeper (the owner's second live test, 8 Nov): window safety, a real playlist (Nth item, collapse, scroll the panel),
page scrolling, pop-up close buttons. OWNED muted signed-out Edge only. Needs the internet. Run: py -3.12 tests\\v3\\check_screen_web2.py"""
import ctypes, os, sys, time
from pathlib import Path
from types import SimpleNamespace
os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from owned_edge import owned_edge
from jarvis3.screen_index import ScreenIndex, UiaSource
from jarvis3.engine.uia import Refused
from jarvis3.engine.osapi import Real
from jarvis3.engine.abilities import screen as S
import uiautomation as auto

results = []
def url(hwnd):
    try: return auto.ControlFromHandle(hwnd).EditControl(Name='Address and search bar', searchDepth=12).GetValuePattern().Value
    except Exception: return ''
def wait(cond, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond(): return True
        time.sleep(.3)
    return False
def report(ok, ms, said, note):
    results.append(bool(ok)); print(f"{'PASS' if ok else 'FAIL'} {ms:5.0f} ms  '{said}' -> {note}", flush=True)
def alive(hwnd): return bool(ctypes.windll.user32.IsWindow(hwnd)) and ctypes.windll.user32.IsWindowVisible(hwnd)

def run(hwnd, said):
    """The sentence through the real router and abilities, on the owned window (no Jarvis UI, no voice)."""
    from jarvis3.engine import understand
    pc = object.__new__(Real); pc.screen = ScreenIndex(UiaSource(window=hwnd))
    ctx = SimpleNamespace(os=pc, app=SimpleNamespace(task=None, draft=None, names=None, memory=None), memory=None, confirmed=False, text=said, ai=None)
    hit = S.route(understand.norm(said)) or next(([(a.name, fn(m))] for a in [__import__('jarvis3.engine.registry', fromlist=['ABILITIES']).ABILITIES['scroll']]
                                                    for rx, fn in a.patterns for m in [__import__('re').fullmatch(rx, understand.norm(said))] if m), None)
    if not hit:
        return None, 'not routed'
    name, args = hit[0]
    fn = {'ui_click': S.ui_click, 'ui_nth': S.ui_nth, 'scroll': S.scroll}[name]
    t = time.perf_counter()
    try:
        r = fn(args, ctx); text = r.plain; ok = r.ok
    except Exception as e:
        text, ok = f'{type(e).__name__}: {e}', False
    return (time.perf_counter() - t) * 1000, (ok, text, pc.screen)

print('--- Window safety: "close" / "minimize" must never touch the browser window')
with owned_edge('https://www.youtube.com/') as hwnd:
    for said in ('press close', 'click close', 'click minimize', 'click maximize'):
        ms, (ok, text, _) = run(hwnd, said); time.sleep(1)
        report(alive(hwnd) and not ok, ms, said, f'{text!r}; window still open: {alive(hwnd)}')

print('--- A real public playlist')
with owned_edge('https://www.youtube.com/watch?v=jfKfPfyJRdk') as hwnd:     # a video page with NO playlist panel
    s = ScreenIndex(UiaSource(window=hwnd)); s.scan(); time.sleep(5)
    ms, (ok, text, sc) = run(hwnd, 'click the third video in this playlist')
    report(not ok and 'playlist' in text and 'jfKfPfyJRdk' in url(hwnd), ms, 'third video in this playlist (no playlist shown)', f'{text!r}: nothing clicked')
with owned_edge('https://www.youtube.com/playlist?list=PLe0XBeaAl1KElgUjwGuNtut0AdjryI4DD') as hwnd:   # a fixed public Lofi Girl playlist
    s = ScreenIndex(UiaSource(window=hwnd)); s.scan(); time.sleep(5)
    ms, (ok, text, sc) = run(hwnd, 'click play all')
    report(ok and wait(lambda: 'list=PLe0XBeaAl1KElgUjwGuNtut0AdjryI4DD' in url(hwnd) and 'watch' in url(hwnd)), ms, 'click play all', f'{text!r} | url ...{url(hwnd)[-40:]}')
    time.sleep(6)
    ms, (ok, text, sc) = run(hwnd, 'click the third video in this playlist')
    report(ok and wait(lambda: 'index=3' in url(hwnd)), ms, 'click the third video in this playlist', f'{text!r} | url ...{url(hwnd)[-30:]}')
    time.sleep(4)
    import re
    def panel_numbers():
        from jarvis3.screen_index import is_playlist
        sc = ScreenIndex(UiaSource(window=hwnd)); sc.scan(); cols = [c for c in sc.lists() if is_playlist(c)]
        col = max(cols, key=lambda c: c[0].bounds[0]) if cols else []
        return [int(m[1]) for e in col for m in [re.match(r'(\d{1,3}) ', e.name)] if m]
    before = panel_numbers()
    ms, (ok, text, sc) = run(hwnd, 'scroll the playlist down'); time.sleep(1)
    after = panel_numbers()
    collapse_still_visible = any(e.name == 'Collapse' for e in ScreenIndex(UiaSource(window=hwnd)).scan())
    report(ok and max(after or [0]) > max(before or [0]) and collapse_still_visible, ms, 'scroll the playlist down',
           f'{text!r} | playlist numbers {before} -> {after}; the page itself stayed put: {collapse_still_visible}')
    n = max(after or [0])
    if n >= 8:
        ms, (ok, text, sc) = run(hwnd, f'click the {["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth"][min(n, 10)]} video in the playlist')
        report(ok and wait(lambda: f'index={min(n, 10)}' in url(hwnd)), ms, f'click the item {min(n, 10)} after scrolling', f'{text!r} | url ...{url(hwnd)[-30:]}')
        time.sleep(3)
    ms, (ok, text, sc) = run(hwnd, 'collapse the playlist')
    collapsed = wait(lambda: 'Expand' in [e.name for e in ScreenIndex(UiaSource(window=hwnd)).scan()], 6)
    report(ok and collapsed, ms, 'collapse the playlist', f'{text!r} | collapsed (Expand button shown, entries gone): {collapsed}')
    ms, (ok, text, sc) = run(hwnd, 'expand the playlist')
    back = wait(lambda: bool(panel_numbers()), 6)
    report(ok and back, ms, 'expand the playlist', f'{text!r} | entries back: {back}')
    ms, (ok, text, sc) = run(hwnd, 'scroll down a bit'); report(ok, ms, 'scroll down a bit', repr(text))
    ms, (ok, text, sc) = run(hwnd, 'scroll down'); report(ok, ms, 'scroll down', repr(text))
    ms, (ok, text, sc) = run(hwnd, 'scroll to the top'); report(ok, ms, 'scroll to the top', repr(text))

print("--- Pop-ups: the owner's own site 'Watch the tour' then close it; a standard dialog")
with owned_edge('https://devbhamaria.com/') as hwnd:
    s = ScreenIndex(UiaSource(window=hwnd)); s.scan(); time.sleep(3)
    tour = [e for e in s.scan() if 'tour' in e.name.lower()]
    if not tour:
        for _ in range(6):
            run(hwnd, 'scroll down'); time.sleep(.6)
            tour = [e for e in ScreenIndex(UiaSource(window=hwnd)).scan() if 'tour' in e.name.lower()]
            if tour: break
    if tour:
        ms, (ok, text, sc) = run(hwnd, 'click on watch the tour'); time.sleep(2.5)
        report(ok, ms, 'click on watch the tour', repr(text))
        ms, (ok, text, sc) = run(hwnd, 'press close'); time.sleep(1.5)
        gone = not any('close' == e.name.lower() for e in ScreenIndex(UiaSource(window=hwnd)).scan())
        report(ok and alive(hwnd), ms, 'press close', f'{text!r}; browser still open: {alive(hwnd)}; pop-up closed: {gone}')
    else:
        print('SKIP no "tour" link found on devbhamaria.com home page')
with owned_edge('https://getbootstrap.com/docs/5.3/components/modal/') as hwnd:
    s = ScreenIndex(UiaSource(window=hwnd)); s.scan(); time.sleep(3)
    for _ in range(4):
        if any(e.name == 'Launch demo modal' for e in s.scan()): break
        run(hwnd, 'scroll down'); time.sleep(.6)
    ms, (ok, text, sc) = run(hwnd, 'click launch demo modal'); time.sleep(1.5)
    report(ok, ms, 'click launch demo modal', repr(text))
    ms, (ok, text, sc) = run(hwnd, 'close the popup'); time.sleep(1.5)
    report(ok and alive(hwnd), ms, 'close the popup', f'{text!r}; browser still open: {alive(hwnd)}')
print("--- 'number the screen', then a number (real badges)")
from jarvis3.overlay import TargetOverlay
with owned_edge('https://en.wikipedia.org/wiki/India') as hwnd:
    made = []
    s = ScreenIndex(UiaSource(window=hwnd), overlay_factory=lambda: made.append(TargetOverlay(name='Screen', expires=30)) or made[-1])
    t = time.perf_counter(); n = s.number_all(); ms = (time.perf_counter() - t) * 1000; time.sleep(.6)
    drawn = bool(made) and made[0].frames > 0 and made[0].error is None
    report(n >= 10 and drawn, ms, 'number the screen', f'{n} numbers, badges drawn: {drawn}')
    talk = next((i for i, e in enumerate(s.shortlist) if e.name == 'Talk'), None)
    if talk is not None:
        said = f'click {talk + 1}'
        t = time.perf_counter(); r = s.pick(said); ms = (time.perf_counter() - t) * 1000
        report(r['status'] == 'clicked' and wait(lambda: 'Talk:India' in url(hwnd)), ms, said, f"{r} | url ...{url(hwnd)[-25:]}")
print(f'REAL WEB 2: {sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
