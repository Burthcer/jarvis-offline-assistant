"""REAL tab closing in an OWNED Edge (fresh muted signed-out profile, deleted after): the owner's sentences through V4's route + real tab engine.
Only the owned window's tabs are touched (the engine is pointed at that window's handle)."""
import os, sys, time
from pathlib import Path
os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from owned_edge import owned_edge
from jarvis3.engine.browser_tabs import WindowsTabs, operate
from jarvis3.engine.abilities.web import tab_route
from jarvis3.legacy.actions import Real

URLS = ['https://www.youtube.com/', 'https://en.wikipedia.org/wiki/India', 'https://www.python.org/', 'https://www.youtube.com/results?search_query=lofi', 'https://duckduckgo.com/']
backend = Real()
results = []
for said, expect in (('Close the Tab 2 and 3', lambda t: len(t) == 3 and not any('Wikipedia' in x or 'Python' in x for x in t)),
                     ('Closes 2nd, 3rd and 4th Tap', lambda t: len(t) == 2),
                     ('close all the tabs other than YouTube', lambda t: len(t) == 2 and all('YouTube' in x for x in t)),
                     ('close all the other tabs', lambda t: len(t) == 1),
                     ('close all tabs except netflix', lambda t: len(t) == 5)):
    with owned_edge(*URLS) as hwnd:
        time.sleep(3)
        tabs = WindowsTabs.__new__(WindowsTabs)
        import ctypes
        from jarvis3.engine import uia
        tabs.b, tabs.auto, tabs.ctypes, tabs.u, tabs.hwnd, tabs.controls = backend, uia._auto(), ctypes, ctypes.windll.user32, hwnd, {}
        before = [t['title'] for t in tabs.list_tabs()]
        call = tab_route(said)
        t0 = time.perf_counter()
        report = operate(tabs, call[0][1]['action'], call[0][1]['selector']) if call else {'ok': False, 'message': 'not routed'}
        ms = (time.perf_counter() - t0) * 1000
        time.sleep(.8)
        after = [t['title'] for t in tabs.list_tabs()]
        ok = expect(after)
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {ms:5.0f} ms  '{said}' -> {call and call[0][1]} | {report.get('message') or 'ok'}\n        before {[b[:18] for b in before]}\n        after  {[a[:18] for a in after]}", flush=True)
print(f'REAL TABS: {sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
