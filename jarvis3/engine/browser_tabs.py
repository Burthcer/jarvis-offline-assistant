"""Snapshot tab identities before acting; never identify tabs by title alone."""
import re
import time

ORDINALS = dict(zip('first second third fourth fifth sixth seventh eighth ninth tenth'.split(),range(1,11)))

class TabTreePending(ValueError):pass

def discover_tab_controls(root):
    """Native tab-container descendants, including Edge's deeper vertical layout.
    Never traverse page documents or the contents of a tab item. Separate tab
    bars stay separate; pinned/grouped descendants of one bar retain UIA order.
    """
    from collections import deque
    queue=deque([(root,0,None)]);groups={};seen=0
    while queue and seen<1200:
        node,depth,bar=queue.popleft();seen+=1
        kind=node.ControlTypeName
        if kind in ('DocumentControl','EditControl'):continue
        if depth>24:
            if bar is not None:raise ValueError('The browser tab tree is too deep to read completely.')
            continue
        if kind=='TabControl' and bar is None:
            bar=tuple(node.GetRuntimeId())
            if not bar or bar in groups:raise ValueError('The browser did not provide unique tab-container identities.')
            groups[bar]=[]
        if kind=='TabItemControl':
            if bar is not None:groups[bar].append(node)
            continue
        queue.extend((c,depth+1,bar) for c in node.GetChildren())
    if queue:raise ValueError('The browser tab tree is too large to read completely.')
    populated=[items for items in groups.values() if items]
    if not populated:raise TabTreePending('The browser has not exposed its tab strip yet.')
    if len(populated)!=1:raise ValueError(f'The browser exposed {len(populated)} separate tab strips; please choose one window.')
    return populated[0]

def keep_tabs(spec, tabs):
    """The tabs he wants to KEEP: 'this', positions ('the first'), or a site/title ('youtube', 'my website')."""
    spec = re.sub(r'^(?:the|my|this)\s+', '', spec.strip().lower()) if spec.strip().lower() != 'this' else 'this'
    spec = re.sub(r'\s+(?:one|ones|tab|tabs)$', '', spec)
    try:
        return resolve(spec, tabs)
    except ValueError:
        pass
    from jarvis3.legacy.actions import TAB
    pattern = TAB.get(spec) or TAB.get(spec.replace(' ', '')) or r'\b' + re.escape(spec) + r'\b'
    return [t for t in tabs if re.search(pattern, t['title'], re.I)]


def resolve(selector, tabs):
    selector = selector.lower().strip()
    if selector=='all':return tabs
    m = re.fullmatch(r'all except (.+)', selector)
    if m:                                             # V4: 'close all tabs except YouTube' / 'close all the other tabs'
        kept = keep_tabs(m[1], tabs)
        if not kept:
            raise ValueError(f"I can't find a {m[1]} tab to keep, so I closed nothing, sir.")
        ids = {t['id'] for t in kept}
        return [t for t in tabs if t['id'] not in ids]
    if selector=='this':
        selected=[t for t in tabs if t.get('selected')]
        if len(selected)!=1:raise ValueError('I could not identify the current tab.')
        return selected
    words = re.split(r'\s*(?:,|\band\b)\s*', selector)
    tokens = re.findall(r'\w+',selector)
    if tokens and all(t in ORDINALS or t in ('last','and','the') or re.fullmatch(r'\d+(?:st|nd|rd|th)?',t) for t in tokens):
        words = [t for t in tokens if t not in ('and','the')]
    targets = []
    for word in words:
        word = re.sub(r'^(?:the|tab)\s+', '', word).strip()
        index = ORDINALS.get(word)
        if word == 'last': index = len(tabs)
        if re.fullmatch(r'\d+(?:st|nd|rd|th)?',word): index = int(re.sub(r'\D','',word))
        if index is not None:
            if not 1 <= index <= len(tabs):
                raise ValueError(f'Tab {word} does not exist.')
            target = tabs[index-1]
        else:
            matches = [t for t in tabs if word and word in t['title'].lower()]
            if len(matches) != 1:
                raise ValueError('Please specify one tab title or its position.')
            target = matches[0]
        if target['id'] not in [t['id'] for t in targets]: targets.append(target)
    return targets

def operate(adapter, action, selector, pattern=None):
    done = []
    try:
        tabs = adapter.list_tabs()
        scope=[t for t in tabs if pattern is None or re.search(pattern,t['title'],re.I)]
        if selector=='front':selector='this' if any(t.get('selected') for t in scope) else 'first'
        targets = resolve(selector, scope)
        if not targets:raise ValueError('No matching tabs were found.')
        if action == 'focus' and len(targets) != 1:
            raise ValueError('Choose one tab to focus.')
        expected = [t['id'] for t in tabs]
        # Stable identities preserve the original requested positions.
        ordered = sorted(targets,key=lambda t:expected.index(t['id']),reverse=True) if action=='close' else targets
        for target in ordered:
            if [t['id'] for t in adapter.list_tabs()] != expected:
                raise ValueError('The tabs changed. Please repeat the remaining request.')
            if action=='close' and hasattr(adapter,'close_target'):
                if not adapter.close_target(target['id']):
                    raise ValueError('Could not verify that the tab closed.')
                expected.remove(target['id'])
            else:
                if not adapter.select(target['id']):raise ValueError('Could not verify the selected tab.')
                if action=='close':
                    if not adapter.close(target['id']):raise ValueError('Could not verify that the tab closed.')
                    expected.remove(target['id'])
            done.append(target['title'])
        return {'ok':True,'done':done,'message':''}
    except Exception as error:
        return {'ok':False,'done':done,'message':str(error) or 'Browser tabs are not accessible.'}

class WindowsTabs:
    def __init__(self, backend, browser=None):
        import ctypes
        from . import uia
        self.b, self.auto, self.ctypes = backend, uia._auto(), ctypes
        self.u = ctypes.windll.user32
        self.u.GetForegroundWindow.restype = ctypes.c_void_p
        windows = backend._browsers()
        if browser:
            windows=[hwnd for hwnd in windows if re.search('microsoft edge' if browser=='edge' else 'google chrome',backend._title(ctypes.c_void_p(hwnd)),re.I)]
        front = self.u.GetForegroundWindow()
        self.hwnd = front if front in windows else windows[0] if len(windows)==1 else None
        if self.hwnd is None: raise ValueError('Please bring the intended browser window to the front.')
        title = backend._title(ctypes.c_void_p(self.hwnd))
        if uia.DENY_WINDOW.search(title): raise ValueError('I do not operate banking or login windows, sir.')
        self.controls = {}

    def list_tabs(self):
        for attempt in range(4):
            try:return self._list_tabs_once()
            except TabTreePending:
                if attempt==3:raise
                time.sleep(.03)
            except ValueError:raise
            except Exception:
                if attempt==3:raise
                time.sleep(.03)  # UIA providers can be transiently busy during layout

    def _list_tabs_once(self):
        if not self.u.IsWindow(self.ctypes.c_void_p(self.hwnd)): return []
        from . import uia
        if uia.DENY_WINDOW.search(self.b._title(self.ctypes.c_void_p(self.hwnd))):raise ValueError('I do not operate banking or login windows, sir.')
        root = self.auto.ControlFromHandle(self.hwnd)
        tabs=discover_tab_controls(root)
        result, controls = [], {}
        for control in tabs:
            identity = tuple(control.GetRuntimeId())
            if identity in controls: raise ValueError('The browser did not provide unique tab identities.')
            controls[identity] = control
            result.append({'id':identity,'title':control.Name or 'Untitled tab','selected':bool(control.GetSelectionItemPattern().IsSelected)})
        self.controls = controls
        return result

    def select(self, identity):
        self.list_tabs()
        control = self.controls.get(identity)
        if control is None:return False
        if not self.b._front(self.hwnd):raise ValueError('Windows refused to bring that browser to the front. Please focus it and try again.')
        try:control.GetSelectionItemPattern().Select()
        except Exception:
            # Some providers report an event-delivery HRESULT even though
            # selection happened. Trust only the state readback below.
            pass
        end = time.monotonic()+.6
        while time.monotonic()<end:
            try:
                self.list_tabs()
                fresh=self.controls.get(identity)
                if fresh and fresh.GetSelectionItemPattern().IsSelected:return True
            except Exception:pass
            time.sleep(.02)
        return False

    def close(self, identity):
        self.list_tabs()
        control = self.controls.get(identity)
        if control is None or not control.GetSelectionItemPattern().IsSelected: return False
        if not self.b._chord(self.hwnd,0x57): return False
        end = time.monotonic()+1
        while time.monotonic()<end:
            if identity not in [t['id'] for t in self.list_tabs()]: return True
            time.sleep(.02)
        return False

    def close_target(self,identity):
        """Invoke the close control belonging to this exact native tab, no keys.
        If Invoke reports an error, read back only; never retry another close.
        """
        if identity not in self.controls:self.list_tabs()
        control=self.controls.get(identity)
        if control is None:return False
        from . import uia
        if uia.DENY_WINDOW.search(control.Name or ''):raise ValueError('I do not operate banking or login tabs, sir.')
        buttons=[c for c in control.GetChildren() if c.ControlTypeName=='ButtonControl' and (c.Name or '').lower() in ('close tab','close')]
        if len(buttons)!=1:return self.select(identity) and self.close(identity)
        from jarvis3.native_action import request
        if not request(buttons[0]):return self.select(identity) and self.close(identity)
        end=time.monotonic()+1
        while time.monotonic()<end:
            if identity not in [t['id'] for t in self.list_tabs()]:return True
            time.sleep(.02)
        return False
