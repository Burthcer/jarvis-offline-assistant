"""V4 self-healing site memory: learn a fixed button once, check it is still the same before reusing it, re-find and overwrite when the site changed.
Fake screens only; no real window, no screen pixels."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT))
from jarvis3.screen_index import ScreenIndex, Element
from jarvis3.site_memory import SiteMemory, verify, dhash, hamming

passed = failed = 0
def check(ok, name):
    global passed, failed
    passed += bool(ok); failed += not ok
    print(('PASS ' if ok else 'FAIL ') + name)

W = (0, 0, 1000, 1000)
class Source:
    """A pretend app window. `look` stands in for the pixels of each control (its 64-bit picture hash)."""
    def __init__(self, items, site='youtube.com'):
        self.items, self.site_name, self.look, self.invoked, self.scans, self.probes = list(items), site, {}, [], 0, 0
    def site(self): return self.site_name
    def scan(self):
        self.scans += 1; return ('w', self.site_name), list(self.items)
    def invoke(self, e): self.invoked.append(e.name); return True
    def fingerprint(self, e):
        l, t, r, b = e.bounds
        return {'kind': e.kind, 'name': e.name, 'aid': e.automation_id, 'cls': '', 'rel': [l / 1000, t / 1000, (r - l) / 1000, (b - t) / 1000],
                'struct': 'toolbar:5', 'dhash': self.look.get(e.name, 0x0F0F0F0F0F0F0F0F)}
    def probe(self, fp):
        self.probes += 1
        x, y = (fp['rel'][0] + fp['rel'][2] / 2) * 1000, (fp['rel'][1] + fp['rel'][3] / 2) * 1000
        at = [e for e in self.items if e.bounds[0] <= x <= e.bounds[2] and e.bounds[1] <= y <= e.bounds[3]]
        if not at: return None, 'nothing there now'
        ok, why = verify(fp, self.fingerprint(at[0]))
        return (at[0], '') if ok else (None, why)

def el(name, kind='ButtonControl', x=0, y=0, w=120):
    return Element(name, kind, (x, y, x + w, y + 40))

def screen():
    return [el('Search', x=400, y=10), el('Search with your voice', x=530, y=10, w=40), el('Shorts', 'HyperlinkControl', 10, 200),
            el('Mix – Travis Scott and friends, the long video title', 'HyperlinkControl', 300, 300, 400), el('Send', x=10, y=900)]

tmp = Path(tempfile.mkdtemp(prefix='v4-site-')); path = tmp / 'site_memory.json'

# 1. First visit: found by the full scan and learned
src = Source(screen()); mem = SiteMemory(path); s = ScreenIndex(src, memory=mem)
r = s.target('search')
check(r['status'] == 'clicked' and src.invoked == ['Search'] and r.get('learned') and src.scans == 1, 'first time: full scan, click, learned')
check(mem.get('youtube.com', 'search') and json.loads(path.read_text())['youtube.com']['search']['name'] == 'Search', 'saved to site_memory.json')

# 2. Repeat visit: checked and clicked straight from memory, no full scan
src = Source(screen()); s = ScreenIndex(src, memory=SiteMemory(path))
r = s.target('the search button')
check(r['status'] == 'clicked' and r.get('from') == 'memory' and src.scans == 0 and src.invoked == ['Search'], 'second time: from memory, no full scan')

# 3. Site updated: button renamed / moved / looks different -> cached click aborted, re-found, memory overwritten
for change, label in (('moved', 'Search moved to the right'), ('restyled', 'Search looks different'), ('replaced', 'Something else now sits where Search was')):
    items = screen()
    if change == 'moved':
        items[0] = el('Search', x=700, y=10)
    if change == 'replaced':
        items[0] = el('Sign up free', x=400, y=10); items.append(el('Search', x=100, y=60))
    src = Source(items)
    if change == 'restyled':
        src.look['Search'] = 0xF0F0F0F0F0F0F0F0
    s = ScreenIndex(src, memory=SiteMemory(path))
    r = s.target('search')
    fixed = SiteMemory(path).get('youtube.com', 'search')
    want = [e for e in items if e.name == 'Search'][0]
    check(r['status'] == 'clicked' and src.invoked == ['Search'] and src.scans == 1 and r.get('healed') and fixed['rel'][0] == want.bounds[0] / 1000,
          f'{label}: cached click aborted, re-found by scan, memory overwritten')
    if change == 'replaced':
        check('Sign up free' not in src.invoked, 'the thing now in the old spot was never clicked')
    src = Source(items); src.look = dict(src.look)
    if change == 'restyled':
        src.look['Search'] = 0xF0F0F0F0F0F0F0F0
    s = ScreenIndex(src, memory=SiteMemory(path))
    check(s.target('search').get('from') == 'memory' and src.scans == 0, f'{label}: next time the healed memory is used')
    path.write_text(json.dumps({}))
    ScreenIndex(Source(screen()), memory=SiteMemory(path)).target('search')     # back to the original layout for the next case

# 4. What is never learned or reused blindly
src = Source(screen()); mem = SiteMemory(path); s = ScreenIndex(src, memory=mem)
s.target('travis scott')
check(mem.get('youtube.com', 'travis scott') is None, 'a video (long content title) is not learned: content changes')
r = s.target('send', allow_risky=True)
check(r['status'] == 'clicked' and mem.get('youtube.com', 'send') is None, 'a risky button (Send) is never learned')
s.target('shorts')
check(mem.get('youtube.com', 'shorts') is not None, 'a short navigation link (Shorts) is learned')
src = Source(screen(), site='discord.com'); s = ScreenIndex(src, memory=SiteMemory(path))
r = s.target('search')
check(r.get('from') != 'memory' and src.scans == 1, 'memory is per site: discord.com does not reuse youtube.com')

# 5. Learning his choice: two close matches, he picks one, next time no question
items = [el('Search', x=400, y=10), el('Search', 'ButtonControl', 400, 500)]
src = Source(items, site='example.app'); mem = SiteMemory(path); s = ScreenIndex(src, memory=mem)
r = s.target('search')
check(r['status'] == 'ambiguous', 'two Search buttons: asks which one')
r = s.pick('the second one')
check(r['status'] == 'clicked' and r.get('learned'), 'his answer is learned')
src = Source(items, site='example.app'); s = ScreenIndex(src, memory=SiteMemory(path))
r = s.target('search')
check(r['status'] == 'clicked' and r.get('from') == 'memory', 'next time it goes straight to the one he chose')

# 6. Pieces
check(hamming(0b1011, 0b0010) == 2 and dhash is not None, 'hamming distance')
fp = Source(screen()).fingerprint(screen()[0])
check(verify(fp, dict(fp))[0] and not verify(fp, {**fp, 'name': 'Other'})[0] and not verify(fp, {**fp, 'struct': 'x'})[0]
      and not verify(fp, {**fp, 'dhash': fp['dhash'] ^ 0xFFFF})[0] and verify(fp, {**fp, 'dhash': fp['dhash'] ^ 0b111})[0], 'verify: name/structure/look checks, small pixel noise allowed')
path.write_text('{broken')
check(SiteMemory(path).get('youtube.com', 'search') is None, 'a damaged memory file is ignored, never crashes')
print(f'{passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
