"""REAL websites, REAL clicks, in an OWNED Edge (fresh signed-out profile, muted, deleted afterwards). Needs the internet.
Every command goes through the V4 screen index exactly as a spoken 'click X' would; the address bar is read afterwards to prove where it went.
Only the owned window is read or clicked (by handle). Run: py -3.12 tests\\v3\\check_screen_web.py"""
import os, sys, time
from pathlib import Path
os.environ['JARVIS_SILENT'] = '1'
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent))
from owned_edge import owned_edge, title
from jarvis3.screen_index import ScreenIndex, UiaSource
from jarvis3.engine.uia import Refused
import uiautomation as auto

results = []
def url(hwnd):
    try:
        return auto.ControlFromHandle(hwnd).EditControl(Name='Address and search bar', searchDepth=12).GetValuePattern().Value
    except Exception:
        return ''

def wait_url(hwnd, want, timeout=8):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if want in url(hwnd):
            return True
        time.sleep(.3)
    return False

def say(hwnd, label, want=None, expect='clicked', then_pick=None):
    s = ScreenIndex(UiaSource(window=hwnd))
    t = time.perf_counter()
    try:
        r = s.target(label)
    except Refused as e:
        r = {'status': 'refused', 'why': str(e)}
    ms = (time.perf_counter() - t) * 1000
    note = r.get('label') or r.get('names') or r.get('why')
    if r['status'] == 'ambiguous' and then_pick:
        r = s.pick(then_pick); note = f"asked {note!r:.80}, answered '{then_pick}' -> {r.get('label')}"
    ok = r['status'] == expect and (want is None or wait_url(hwnd, want))
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {ms:5.0f} ms  'click {label}' -> {r['status']}: {str(note)[:110]}" + (f"  | url now {url(hwnd)[:70]}" if want else ''), flush=True)
    return r

def back(hwnd, want):
    s = ScreenIndex(UiaSource(window=hwnd)); s.target('back'); wait_url(hwnd, want); time.sleep(1.5)

print('--- YouTube (signed out)')
with owned_edge('https://www.youtube.com/') as hwnd:
    say(hwnd, 'shorts', '/shorts'); back(hwnd, 'youtube.com/')
    say(hwnd, 'subscriptions', '/feed/subscriptions'); back(hwnd, 'youtube.com/')
    say(hwnd, 'history', '/feed/history'); back(hwnd, 'youtube.com/')
    say(hwnd, 'shots', '/shorts')                                   # the owner's misheard word
print("--- 'open / start / go to X' uses the screen when X is not an app (the owner, 8 Nov)")
from jarvis3.engine.abilities.screen import open_target
from jarvis3.engine.osapi import Real
with owned_edge('https://www.youtube.com/') as hwnd:
    pc = object.__new__(Real); pc.screen = ScreenIndex(UiaSource(window=hwnd))
    for said, want in (('open shots', '/shorts'), ('start shorts', '/shorts'), ('go to subscriptions', '/feed/subscriptions'), ('open the moon base', None)):
        label = open_target(said); t = time.perf_counter(); seen = pc.ui_visible(label)
        if want is None:
            ok = not seen; note = 'not on screen -> left to the usual understanding'
        else:
            r = pc.ui_target(label) if seen else {'status': 'not seen'}; ok = r['status'] == 'clicked' and wait_url(hwnd, want); note = f"{r['status']} {r.get('label', '')}"
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {(time.perf_counter() - t) * 1000:5.0f} ms  '{said}' -> {note}" + (f' | url now {url(hwnd)[:60]}' if want else ''), flush=True)
        if want:
            back(hwnd, 'youtube.com/')
print('--- YouTube search results: several mixes -> which one -> the second one')
with owned_edge('https://www.youtube.com/results?search_query=lofi+hip+hop+mix') as hwnd:
    ScreenIndex(UiaSource(window=hwnd)).scan(); time.sleep(4)          # browser already in use and results loaded, as when he speaks
    say(hwnd, 'lofi mix', 'list=', expect='clicked', then_pick='the second one')
print('--- Wikipedia')
with owned_edge('https://en.wikipedia.org/wiki/India') as hwnd:
    say(hwnd, 'talk', 'Talk:India'); say(hwnd, 'article', '/wiki/India')
    say(hwnd, 'view history', 'action=history'); back(hwnd, '/wiki/India')
    say(hwnd, 'history', '#History')                                # the section, not 'View history'
    say(hwnd, 'something that is not here', expect='refused')
print('--- python.org (GitHub was down with 504 on 8 Nov, so a different site)')
with owned_edge('https://www.python.org/') as hwnd:
    # Very first command in a brand-new browser: the page has to wake up and may ignore the press. Allowed: clicked, or an HONEST refusal.
    s = ScreenIndex(UiaSource(window=hwnd))
    try:
        r = s.target('downloads'); honest = wait_url(hwnd, '/downloads')
    except Refused as e:
        honest = 'nothing happened' in str(e) and '/downloads' not in url(hwnd)
    results.append(honest); print(f"{'PASS' if honest else 'FAIL'} first command in a new browser: clicked, or honestly said nothing happened")
with owned_edge('https://www.python.org/') as hwnd:
    ScreenIndex(UiaSource(window=hwnd)).scan(); time.sleep(4)          # the browser has been used once already, as in daily use
    say(hwnd, 'downloads', '/downloads')
print('--- Number badges really drawn over a shortlist (YouTube results)')
from jarvis3.overlay import TargetOverlay
with owned_edge('https://www.youtube.com/results?search_query=lofi+hip+hop') as hwnd:
    ScreenIndex(UiaSource(window=hwnd)).scan(); time.sleep(4)
    made = []
    s = ScreenIndex(UiaSource(window=hwnd), overlay_factory=lambda: made.append(TargetOverlay(name='Screen', expires=30)) or made[-1])
    r = s.target('lofi')
    time.sleep(.5)
    drawn = r['status'] == 'ambiguous' and made and made[0].frames > 0 and made[0].error is None
    results.append(bool(drawn)); print(f"{'PASS' if drawn else 'FAIL'} 'click lofi' -> {r['status']} {r.get('count')} choices, badges drawn: {made[0].frames if made else 0} frame(s)")
    s.forget()
print('--- A multi-step task on a real site')
from types import SimpleNamespace
from jarvis3.engine.osapi import Real
from jarvis3.engine.abilities import tasks
with owned_edge('https://www.youtube.com/') as hwnd:
    pc = object.__new__(Real); pc.screen = ScreenIndex(UiaSource(window=hwnd))
    ctx = SimpleNamespace(os=pc, app=SimpleNamespace(task=None, names=None), ai=None)
    t = time.perf_counter(); r = tasks.task_run({'goal': 'click subscriptions, then click history'}, ctx); ms = (time.perf_counter() - t) * 1000
    ok = r.ok and wait_url(hwnd, '/feed/history'); results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {ms:5.0f} ms  task 'click subscriptions, then click history' -> {r.plain} | url now {url(hwnd)[:60]}")
print('--- DuckDuckGo results')
with owned_edge('https://duckduckgo.com/?q=python+tutorial') as hwnd:
    say(hwnd, 'images', 'ia=images')
print(f'REAL WEB: {sum(results)}/{len(results)} passed')
sys.exit(0 if all(results) else 1)
