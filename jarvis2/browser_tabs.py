"""Snapshot tab identities before acting; never identify tabs by title alone."""
import re
import time

ORDINALS = dict(zip('first second third fourth fifth sixth seventh eighth ninth tenth'.split(),range(1,11)))

def resolve(selector, tabs):
    selector = selector.lower().strip()
    if selector=='all':return tabs
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
            if not adapter.select(target['id']):
                raise ValueError('Could not verify the selected tab.')
            if action == 'close':
                if not adapter.close(target['id']):
                    raise ValueError('Could not verify that the tab closed.')
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
            except ValueError:raise
            except Exception:
                if attempt==3:raise
                time.sleep(.03)  # UIA providers can be transiently busy during layout

    def _list_tabs_once(self):
        if not self.u.IsWindow(self.ctypes.c_void_p(self.hwnd)): return []
        root = self.auto.ControlFromHandle(self.hwnd)
        queue, groups, seen = [(root,0)], [], 0
        while queue and seen < 600:
            node, depth = queue.pop(0); seen += 1
            if depth > 8 or node.ControlTypeName in ('DocumentControl','EditControl'): continue
            children = node.GetChildren()
            tabs = [c for c in children if c.ControlTypeName == 'TabItemControl']
            if tabs:
                groups.append(tabs)
            else:
                queue.extend((c,depth+1) for c in children)
        if len(groups) != 1: raise ValueError('I cannot identify one reliable browser tab strip.')
        result, controls = [], {}
        for control in groups[0]:
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
