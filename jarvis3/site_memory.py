"""V4 self-healing site and app memory (spec part 2): learn where a fixed control is once, check it is still the same before reusing it.
Saved per site (web domain) or app (program name) and spoken intent ('search'), in data/.../site_memory.json, local only.
A fingerprint has several anchors; ALL must still agree before a remembered control is pressed:
  - what Windows says it is: control type, exact name, automation id, class name;
  - where it sits as a share of the window (so resizing the window does not matter);
  - its neighbourhood: how many siblings it has and the names beside it;
  - how it looks: a 64-bit picture hash (dHash) of the control's own rectangle. Only the number is kept, never the picture.
Any mismatch means 'the site changed': the remembered click is abandoned and the normal screen search runs, then the memory is overwritten."""
import json
import os
import threading
import time
from pathlib import Path

MAX_SITES, MAX_INTENTS = 200, 60
LOOK_TOLERANCE = 10          # differing bits out of 64: hover shading and anti-aliasing are fine, a different icon or a popup is not
PLACE_TOLERANCE = .03        # share of the window the centre may drift
SIZE_TOLERANCE = .25


def dhash(image):
    """64-bit difference hash of a PIL image: is each pixel brighter than its right-hand neighbour, on a 9x8 grey thumbnail."""
    small = image.convert('L').resize((9, 8))
    px = list(small.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    return bits


def hamming(a, b):
    return bin(int(a) ^ int(b)).count('1')


def verify(saved, live):
    """(True, '') when the live control is the remembered one, else (False, the reason in plain words)."""
    if live is None:
        return False, 'nothing there now'
    for key, what in (('kind', 'type'), ('name', 'name'), ('aid', 'id'), ('cls', 'class')):
        if (saved.get(key) or '') != (live.get(key) or ''):
            return False, f'its {what} changed'
    (sx, sy, sw, sh), (lx, ly, lw, lh) = saved['rel'], live['rel']
    if abs((sx + sw / 2) - (lx + lw / 2)) > PLACE_TOLERANCE or abs((sy + sh / 2) - (ly + lh / 2)) > PLACE_TOLERANCE:
        return False, 'it moved'
    if sw and sh and (abs(lw - sw) / sw > SIZE_TOLERANCE or abs(lh - sh) / sh > SIZE_TOLERANCE):
        return False, 'its size changed'
    if saved.get('struct') and live.get('struct') and saved['struct'] != live['struct']:
        return False, 'the controls around it changed'
    if saved.get('dhash') is not None and live.get('dhash') is not None and hamming(saved['dhash'], live['dhash']) > LOOK_TOLERANCE:
        return False, 'it looks different'
    return True, ''


class SiteMemory:
    def __init__(self, path):
        self.path, self.lock = Path(path), threading.Lock()
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            self.data = data if isinstance(data, dict) else {}
        except Exception:
            self.data = {}                                  # missing or damaged: start empty, never crash

    def get(self, site, intent):
        entry = self.data.get(site, {}).get(intent)
        return dict(entry) if isinstance(entry, dict) and isinstance(entry.get('rel'), list) and len(entry['rel']) == 4 else None

    def put(self, site, intent, fingerprint):
        with self.lock:
            sites = self.data.setdefault(site, {})
            sites[intent] = {**fingerprint, 'learned': time.strftime('%Y-%m-%d %H:%M'), 'uses': sites.get(intent, {}).get('uses', 0)}
            if len(sites) > MAX_INTENTS:
                del sites[min(sites, key=lambda k: (sites[k].get('uses', 0), sites[k].get('learned', '')))]
            if len(self.data) > MAX_SITES:
                del self.data[min(self.data, key=lambda s: max((v.get('learned', '') for v in self.data[s].values()), default=''))]
            self._save()

    def used(self, site, intent):
        with self.lock:
            entry = self.data.get(site, {}).get(intent)
            if entry:
                entry['uses'] = entry.get('uses', 0) + 1
                self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, indent=1), encoding='utf-8')
        os.replace(tmp, self.path)                          # never a half-written file
