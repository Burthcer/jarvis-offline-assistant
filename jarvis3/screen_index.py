"""V4 silent screen index (spec part 1): every visible, named control in the window in front, kept in memory only.
- target('download button'): one clear match is clicked at once; several close matches are shortlisted, numbered on screen, and asked about.
- resolve/pick('the second one' | 'the chill synthwave one'): the next sentence answers the shortlist before anything else hears it.
No pictures of the screen and no site-specific rules: names come from Windows accessibility (UI Automation), the same names a screen reader uses.
The rails stay in engine/uia.py: bank/login/password windows and Jarvis's own windows are refused there; risky labels (send, delete...) need a yes."""
import re
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .engine.uia import Refused, risky

EXPIRES_S = 30          # a shortlist older than this is forgotten
MARGIN = .1             # matches within this of the best one count as "the same quality": ask which
MIN_SCORE = .45
MAX_SHORTLIST = 9
GENERIC = {'button', 'link', 'icon', 'tab', 'option', 'menu', 'item', 'one', 'video', 'playlist', 'channel', 'page', 'result', 'entry',
           'thing', 'box', 'field', 'song', 'chat', 'contact', 'conversation', 'card', 'server'}
FILLER = {'the', 'a', 'an', 'on', 'that', 'this', 'called', 'named', 'labelled', 'labeled', 'says', 'with', 'please', 'sir', 'of', 'to'}
KIND_HINT = {'button': {'ButtonControl', 'SplitButtonControl'}, 'tab': {'TabItemControl'}, 'menu': {'MenuItemControl'},
             'link': {'HyperlinkControl'}, 'video': {'HyperlinkControl', 'ListItemControl'}, 'playlist': {'HyperlinkControl', 'ListItemControl'},
             'channel': {'HyperlinkControl', 'ListItemControl'}, 'chat': {'ListItemControl'}, 'contact': {'ListItemControl'}}
ORDINAL = {'first': 1, '1st': 1, 'one': 1, 'second': 2, '2nd': 2, 'two': 2, 'third': 3, '3rd': 3, 'three': 3, 'fourth': 4, '4th': 4, 'four': 4,
           'fifth': 5, '5th': 5, 'five': 5, 'sixth': 6, '6th': 6, 'six': 6, 'seventh': 7, '7th': 7, 'seven': 7, 'eighth': 8, '8th': 8, 'eight': 8,
           'ninth': 9, '9th': 9, 'nine': 9, 'top': 1, 'last': -1, 'bottom': -1, 'final': -1, 'middle': 0}
TENS = {'twenty': 20, 'thirty': 30, 'forty': 40}
TEENS = {'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
         'tenth': 10, 'eleventh': 11, 'twelfth': 12, 'thirteenth': 13, 'fifteenth': 15, 'twentieth': 20}
UNITS = {'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9}


def spoken_numbers(text):
    """'number twenty one' -> 'number 21', 'twelve' -> '12' (only 10-49; one..nine stay words for 'the second one')."""
    text = re.sub(r'\b(twenty|thirty|forty)(?: (one|two|three|four|five|six|seven|eight|nine))?\b',
                  lambda m: str(TENS[m[1]] + (UNITS[m[2]] if m[2] else 0)), text)
    return re.sub(r'\b(' + '|'.join(TEENS) + r')\b', lambda m: str(TEENS[m[1]]), text)


CANCEL = re.compile(r'(?:no|nope|none|neither|none of them|neither of them|cancel|cancel that|never mind|nevermind|forget it|stop|leave it)', re.I)


@dataclass(frozen=True)
class Element:
    name: str
    kind: str               # UI Automation control type name, e.g. 'ButtonControl'
    bounds: tuple           # screen pixels (left, top, right, bottom)
    automation_id: str = ''
    value: str = ''         # a link's address when the app shares it; two links to the same place are one target
    handle: object = field(default=None, compare=False, repr=False)   # the live control; never kept past one turn

    @property
    def identity(self):
        return (self.kind, self.name, self.automation_id, self.value)


def plain(text):
    """Fancy-font titles and accents become ordinary letters."""
    text = unicodedata.normalize('NFKD', unicodedata.normalize('NFKC', text or ''))
    return ''.join(c for c in text if not unicodedata.combining(c))


def words(text):
    return re.findall(r'[a-z0-9]+', plain(text).lower())


def _same(a, b):
    """1 for the same word, .7 for a near miss (plural, misheard), else 0."""
    if a == b:
        return 1.0
    if len(a) >= 3 and len(b) >= 3 and (b.startswith(a) or a.startswith(b)) and abs(len(a) - len(b)) <= 2:
        return .7
    if len(a) > 3 and SequenceMatcher(None, a, b).ratio() >= .8:
        return .7
    return 0.0


def query_words(text):
    """The words that must be found. Nouns like 'button' or 'playlist' only help, unless they are all he said."""
    said = [w for w in words(text) if w not in FILLER]
    core = [w for w in said if w not in GENERIC]
    return (core or said), [w for w in said if w in GENERIC]


def score(query, nouns, element):
    name = words(element.name)
    if not query or not name:
        return 0.0
    if query == name:
        base = 1.0
    else:
        weights = [max(_same(q, n) for n in name) for q in query]
        if all(weights) and max(weights) < 1 and len(name) > 3:
            return 0.0      # only near-miss words: fine for a short label ('shots' -> Shorts), never for a sentence (the owner's log, 8 Nov)
        if not all(weights):
            if len(name) > 3:
                return 0.0
            ratio = SequenceMatcher(None, ' '.join(query), ' '.join(name)).ratio()
            return round(.6 * ratio, 3) if ratio >= .8 else 0.0   # one misheard label ('downlod')
        quality = sum(weights) / len(weights)
        phrase = re.search(r'\b' + re.escape(' '.join(query)) + r'\b', ' '.join(name)) is not None
        # Shorter labels that are mostly his words rank higher ('Download' over 'Download options'), but beyond 4 words length says
        # nothing about what he meant: every long video title counts the same, so 'click lofi' asks which one (8 Nov, real YouTube).
        base = quality * (.6 + .3 * min(1.0, len(query) / min(len(name), 4)) + (.1 if phrase else 0))
    if any(element.kind in KIND_HINT.get(n, ()) for n in nouns):
        base += .03
    return round(min(base, 1.0), 3)


def reading_order(elements):
    rows = []
    for e in sorted(elements, key=lambda e: (e.bounds[1], e.bounds[0])):
        row = next((r for r in rows if abs(r[0].bounds[1] - e.bounds[1]) <= 8), None)
        (row.append(e) if row is not None else rows.append([e]))
    return [e for r in rows for e in sorted(r, key=lambda e: e.bounds[0])]


def is_playlist(column):
    """A list that is a playlist/queue: its entries show their numbers, or their links share one list address (any site)."""
    from urllib.parse import urlsplit, parse_qsl
    if sum(1 for e in column if re.match(r'\d{1,3}\s', e.name)) >= 2:
        return True
    shared = {}
    for e in column:
        for pair in set(parse_qsl(urlsplit(e.value).query)) if e.value.startswith('http') else ():
            shared[pair] = shared.get(pair, 0) + 1
    return any(n >= 3 and n >= len(column) - 1 for n in shared.values())


PREFER = {'HyperlinkControl': 3, 'ButtonControl': 3, 'SplitButtonControl': 3, 'MenuItemControl': 3, 'TabItemControl': 3, 'EditControl': 3,
          'CheckBoxControl': 2, 'RadioButtonControl': 2, 'ComboBoxControl': 2, 'TreeItemControl': 1, 'ListItemControl': 1}


def overlap(a, b):
    """Shared area as a share of the smaller box."""
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return w * h / small if small > 0 else 0.0


def dedupe(elements):
    """One thing on screen = one target. Web pages often expose the same entry twice: YouTube's menu has two identical 'History' links
    in the same place, a list row wraps its link, a thumbnail and a title link to the same video. Same name AND (same address OR
    mostly the same place) -> keep one, preferring the pressable kind."""
    out, by_name, by_link = [], {}, {}
    for e in elements:
        key = ' '.join(words(e.name))
        twins = by_name.setdefault(key, [])
        twin = next((i for i in twins if (e.value and out[i].value == e.value) or overlap(out[i].bounds, e.bounds) >= .6), None)
        link = e.value if e.value.startswith('http') and not e.value.endswith('#') else ''
        if twin is None and link in by_link:
            twin = by_link[link]                            # different words, same address: YouTube's channel picture 'Go to channel X' and the name 'X'
            keep = out[twin]
            if re.match(r'go to\b', keep.name, re.I) and not re.match(r'go to\b', e.name, re.I):
                out[twin] = e                               # keep the plain name a person would say
            continue
        if twin is None:
            twins.append(len(out)); out.append(e)
            if link:
                by_link[link] = len(out) - 1
        elif (PREFER.get(e.kind, 0), bool(e.value)) > (PREFER.get(out[twin].kind, 0), bool(out[twin].value)):
            out[twin] = e
    return out


LEARNABLE = {'ButtonControl', 'SplitButtonControl', 'TabItemControl', 'MenuItemControl', 'EditControl', 'ComboBoxControl',
             'CheckBoxControl', 'RadioButtonControl', 'HyperlinkControl'}


def learnable(element):
    """Fixed parts of a site or app (Search, Shorts, Settings, a tab). Not content (video titles, chats), which changes, and never risky buttons."""
    return element.kind in LEARNABLE and len(element.name) <= 40 and len(words(element.name)) <= 5 and not risky(element.name)


def intent_of(label):
    return ' '.join(query_words(label)[0])


class ScreenIndex:
    def __init__(self, source, overlay_factory=None, clock=time.monotonic, memory=None):
        self.source, self.overlay_factory, self.clock, self.memory = source, overlay_factory, clock, memory
        self.page, self.elements, self.site, self.stale = None, [], None, False
        self.shortlist, self.label, self.allow_risky, self.at, self.overlay = [], '', False, 0.0, None

    # ----- site memory (spec part 2) -----
    def _remembered(self, intent, allow_risky):
        """A click straight from memory after every anchor checked out, else None (and the reason is kept, so a later success counts as a repair)."""
        self.site, self.stale = None, False
        if self.memory is None or not hasattr(self.source, 'probe'):
            return None
        try:
            self.site = self.source.site()
        except Exception:
            return None
        saved = self.memory.get(self.site, intent) if self.site else None
        if not saved:
            return None
        try:
            element, _why = self.source.probe(saved)
        except Refused:
            raise
        except Exception:
            element = None
        if element is None:
            self.stale = True                                  # site updated, popup, scrolled: never click the old spot
            return None
        if risky(element.name) and not allow_risky:
            return {'status': 'risky', 'label': element.name}
        result = self._click(element)
        self.memory.used(self.site, intent)
        return {**result, 'from': 'memory'}

    def _learn(self, intent, element, result):
        if self.memory is None or not self.site or not intent or not learnable(element) or not hasattr(self.source, 'fingerprint'):
            return result
        try:
            self.memory.put(self.site, intent, self.source.fingerprint(element))
        except Exception:
            return result
        return {**result, 'learned': True, **({'healed': True} if self.stale else {})}

    # ----- the silent index -----
    def scan(self):
        self.page, found = self.source.scan()
        self.elements = reading_order(dedupe([e for e in found if e.name.strip()]))
        return self.elements

    def matches(self, labels, elements=None):
        best = {}
        for rank, label in enumerate(labels):
            query, nouns = query_words(label)
            for e in (self.elements if elements is None else elements):
                s = score(query, nouns, e) - .12 * rank          # his own word first, stand-ins after ('hide': Hide > Collapse > Close)
                if s >= MIN_SCORE and s > best.get(e, 0):
                    best[e] = s
        order = {e: i for i, e in enumerate(self.elements if elements is None else elements)}
        return sorted(((s, e) for e, s in best.items()), key=lambda p: (-p[0], order[p[1]]))

    # ----- 'click the download button' -----
    def target(self, label, aliases=(), allow_risky=False):
        self.forget()
        intent = intent_of(label)
        remembered = self._remembered(intent, allow_risky)
        if remembered:
            return remembered
        self.scan()
        hits = self.matches([label, *aliases])
        woke = False
        hits = self._patient(hits, [label, *aliases])
        woke = self._woke
        if hits and woke:
            time.sleep(1.0)                                 # a page that just woke up ignores presses for a moment (GitHub, 8 Nov)
        if not hits:
            raise Refused(f"I can't find '{label}' on the screen, sir.")
        top = hits[0][0]
        close = [e for s, e in hits if s >= top - MARGIN][:MAX_SHORTLIST]
        if not allow_risky and any(risky(e.name) for e in close):
            return {'status': 'risky', 'label': next(e.name for e in close if risky(e.name))}
        if len(close) > 1 and ' '.join(words(label)) in SAME_EFFECT and len({' '.join(words(e.name)) for e in close}) == 1:
            close = close[:1]               # a dialog's X and its 'Close' button do the same thing: no question (Bootstrap, 8 Nov)
        if len(close) == 1:
            return self._learn(intent, close[0], self._click(close[0]))
        self.shortlist, self.label, self.allow_risky, self.at = close, label, allow_risky, self.clock()
        self._show()
        return {'status': 'ambiguous', 'count': len(close), 'label': label, 'names': [e.name for e in close]}

    # ----- 'number the screen' (spec Tier 2, on request): badges on everything pressable, then 'click 12' -----
    def number_all(self, limit=40):
        """Number the pressable things on screen (reading order, at most `limit`, the page's own controls only) and wait for a number."""
        self.forget()
        self.scan()
        if len(self.elements) < self.ASLEEP:
            self._patient([], ['\0'])
        pick = [e for e in self.elements if e.kind != 'EditControl'][:limit]
        if not pick:
            raise Refused("I can't see anything to number on this screen, sir.")
        self.shortlist, self.label, self.allow_risky, self.at = pick, 'numbered screen', False, self.clock()
        self._show()
        return len(pick)

    # ----- 'the third video in this playlist', 'the first mix, Josie Edwards' (V4, the owner 8 Nov) -----
    def lists(self):
        """Columns of list entries on screen (a playlist panel, search results, a chat list), top to bottom, widest first."""
        entries = [e for e in self.elements if e.kind in ('HyperlinkControl', 'ListItemControl', 'TreeItemControl') and len(words(e.name)) >= 2]
        columns = []
        for e in sorted(entries, key=lambda e: (e.bounds[1], e.bounds[0])):
            col = next((c for c in columns if abs(c[0].bounds[0] - e.bounds[0]) <= 15), None)
            (col.append(e) if col is not None else columns.append([e]))
        return [c for c in columns if len(c) >= 3]

    def nth(self, n, label='', scope=''):
        """Pick the n-th entry (1-based; -1 = last). With words: the n-th of the entries that match them. With a scope like
        'playlist' / 'sidebar': the right-hand list; else the longest list. Entries that show their own number ('3 study with me')
        are counted by that number, so a scrolled playlist still means what he sees."""
        self.forget()
        self.scan()
        if label:
            hits = self._patient(self.matches([label]), [label])
            if not hits:
                raise Refused(f"I can't find '{label}' on the screen, sir.")
            pool = reading_order([e for s, e in hits])
        else:
            columns = self.lists()
            if not columns:
                self._patient([], ['\0'])
                columns = self.lists()
            if not columns:
                raise Refused("I can't see a list on the screen, sir.")
            side = re.search(r'playlist|queue|panel|side|right|up next', scope or '')
            if re.search(r'playlist|queue', scope or ''):
                columns = [c for c in columns if is_playlist(c)]
                if not columns:
                    raise Refused("I can't see a playlist on the screen, sir.")   # never 'the third recommended video' instead (8 Nov)
            pool = max(columns, key=lambda c: c[0].bounds[0]) if side else max(columns, key=len)
            numbered = {}
            for e in pool:
                m = re.match(r'(\d{1,3})\s', e.name)
                if m:
                    numbered[int(m[1])] = e
            if len(numbered) >= 2 and n > 0:
                if n in numbered:
                    return self._click(numbered[n], short=True)
                if n == min(numbered) - 1 and not re.match(r'\d', pool[0].name):
                    return self._click(pool[0], short=True)              # the playing item shows no number
                raise Refused(f"Number {n} isn't visible in that list, sir. Say 'scroll the {scope or 'list'} down' first.")
        if not -len(pool) <= n <= len(pool) or n == 0:
            raise Refused(f"I can only see {len(pool)} of those, sir.")
        return self._click(pool[n - 1] if n > 0 else pool[n], short=True)

    ASLEEP = 40             # fewer controls than this on a web page: it is probably still waking up

    def _patient(self, hits, labels):
        """Nothing matched: look again, up to about 3 s, while the page still looks asleep (Edge/Chrome describe a page fully only
        after the first request: 8 Nov, YouTube results 16 -> 54 items after ~2 s). A page that is awake gets one more look only."""
        self._woke = False
        base = getattr(self.source, 'settle', 0) or 0
        for wait in (base, base * 1.7, base * 2.3, base * 3):        # up to ~5 s (8 Nov: YouTube home woke after ~3 s)
            if hits or not wait or (self._woke and len(self.elements) >= self.ASLEEP):
                break
            time.sleep(wait)
            self.scan()
            hits = self.matches(labels)
            self._woke = True
        return hits

    def visible(self, label):
        """Is something called this on the screen right now? Used before 'open shots' goes anywhere else (no click here)."""
        self.scan()
        hits = self.matches([label])
        if not hits and len(self.elements) < self.ASLEEP:      # an awake page without it: answer at once, the sentence goes the usual way
            hits = self._patient(hits, [label])
        return bool(hits)

    def _click(self, element, short=False):
        if risky(element.name) and short:
            return {'status': 'risky', 'label': element.name}
        if not self.source.invoke(element):
            raise Refused(f"I pressed {element.name}, but nothing happened. The page may still be loading, sir.")
        return {'status': 'clicked', 'label': element.name}

    def scroll(self, direction, amount='', scope=''):
        """Scroll the page, or with a scope ('playlist', 'sidebar', 'list') the list he means. Checked: the screen must change."""
        if not hasattr(self.source, 'scroll'):
            raise Refused("I can't scroll here, sir.")
        self.forget()
        before = [(e.identity, e.bounds) for e in self.scan()]
        area = None
        if scope:
            columns = self.lists()
            if re.search(r'playlist|queue', scope):
                columns = [c for c in columns if is_playlist(c)]
            side = re.search(r'playlist|queue|panel|side|right|up next', scope)
            if not columns:                       # never scroll the whole page instead of the list he named (8 Nov)
                raise Refused(f"I can't see the {scope} on the screen, sir.")
            col = max(columns, key=lambda c: c[0].bounds[0]) if side else max(columns, key=len)
            area = (min(e.bounds[0] for e in col), min(e.bounds[1] for e in col), max(e.bounds[2] for e in col), max(e.bounds[3] for e in col))
        self.source.scroll(direction, amount, area)
        time.sleep(.35)
        return [(e.identity, e.bounds) for e in self.scan()] != before

    # ----- the answer to 'which one?' -----
    def active(self):
        if self.shortlist and self.clock() - self.at > EXPIRES_S:
            self.forget()
        return bool(self.shortlist)

    def resolve(self, said):
        """0-based shortlist positions the sentence points at, 'cancel', or None when it is not an answer at all."""
        if not self.active():
            return None
        text = spoken_numbers(' '.join(words(said)))
        if CANCEL.fullmatch(text) or re.match(r'(?:never ?mind|forget it|cancel|leave it|none of (?:them|those))\b', text):
            return 'cancel'
        m = re.fullmatch(r'(?:(?:the|that|this|number|option|choice|go with|pick|choose|select|click|open|play|press|tap|on)\s+)*(\w+)(?:\s+(?:one|option|choice|video|link|result|mix|playlist|item))?', text)
        if m and (m[1] in ORDINAL or m[1].isdigit()):
            n = int(m[1]) if m[1].isdigit() else ORDINAL[m[1]]
            count = len(self.shortlist)
            if n == 0:
                return [count // 2] if count % 2 else None   # 'the middle one' of an even list is not one item
            index = n - 1 if n > 0 else count + n
            return [index] if 0 <= index < count else None
        return self._by_words(said)

    def _by_words(self, said):
        query = [w for w in words(said) if w not in FILLER and w not in GENERIC and w not in ('which', 'about', 'i', 'mean', 'want', 'it', 'is')]
        if not query:
            return None
        names = [words(e.name) for e in self.shortlist]
        common = set(names[0]).intersection(*names[1:])
        useful = [q for q in query if not any(_same(q, c) for c in common)] or query
        joined = ' '.join(useful)
        scores = []
        for name in names:
            hits = sum(max(_same(q, n) for n in name) for q in useful)
            glued = SequenceMatcher(None, joined.replace(' ', ''), ''.join(name)).find_longest_match().size   # 'synth wave' = 'synthwave'
            scores.append(max(hits, 1.0 if glued >= 6 else 0.0))
        best = max(scores)
        if best < max(.7, len(useful) * .5):
            return None
        return [i for i, s in enumerate(scores) if s == best]

    def pick(self, said):
        choice = self.resolve(said)
        if choice is None or choice == 'cancel':
            self.forget()
            return {'status': 'cancelled' if choice == 'cancel' else 'not_answer'}
        if len(choice) > 1:
            self.shortlist = [self.shortlist[i] for i in choice]
            self.at = self.clock()
            self._show()
            return {'status': 'ambiguous', 'count': len(self.shortlist), 'label': self.label, 'names': [e.name for e in self.shortlist]}
        wanted, allow, intent = self.shortlist[choice[0]], self.allow_risky, intent_of(self.label)
        self.forget()
        self.scan()                                        # the screen now, not the one he was asked about
        fresh = [e for e in self.elements if e.identity == wanted.identity]
        fresh.sort(key=lambda e: abs(e.bounds[0] - wanted.bounds[0]) + abs(e.bounds[1] - wanted.bounds[1]))
        if not fresh or (len(fresh) > 1 and fresh[0].bounds != wanted.bounds):
            raise Refused('The screen changed, sir. Nothing was clicked. Please ask me again.')
        if risky(fresh[0].name) and not allow:
            raise Refused(f"'{fresh[0].name}' needs a yes first. Say 'click {fresh[0].name}', sir.")
        return self._learn(intent, fresh[0], self._click(fresh[0]))

    def forget(self):
        self.shortlist, self.label = [], ''
        if self.overlay is not None:
            try:
                self.overlay.close(wait=False)
            except Exception:
                pass
            self.overlay = None

    def _show(self):
        """Numbered badges over the shortlisted items only. A failed overlay never blocks the question."""
        if self.overlay_factory is None:
            return
        from .choices import Item, Snapshot
        snap = Snapshot('screen', tuple(self.page or ()), 'screen', self.clock(),
                        tuple(Item(str(i + 1), e.name, e.bounds) for i, e in enumerate(self.shortlist)))
        try:
            if self.overlay is None:
                self.overlay = self.overlay_factory()
            self.overlay.show(snap)
        except Exception:
            self.overlay = None


def speak_names(names, limit=4):
    """'Travis Scott Mix, Chill Synthwave and Lofi Beats': the first few words of each, so the question stays short."""
    short = [' '.join(plain(n).split()[:6]) for n in names[:limit]]
    if len(names) > limit:
        short.append(f'{len(names) - limit} more')
    return short[0] if len(short) == 1 else ', '.join(short[:-1]) + ' or ' + short[-1]


CAPTION = {'minimize', 'minimise', 'maximize', 'maximise', 'restore', 'close', 'system'}
SAME_EFFECT = {'close', 'dismiss', 'collapse', 'expand', 'hide', 'skip', 'cancel', 'got it', 'ok', 'no thanks', 'not now',
               'play all', 'shuffle', 'see all', 'view all', 'show more', 'show less', 'more', 'less', 'next', 'previous', 'back', 'home'}
BROWSER_KEEP = {'back', 'forward', 'refresh', 'reload', 'home'}


def _grab(bounds):
    """The control's own rectangle, for its 64-bit picture hash. The pixels are dropped at once; only the hash is kept."""
    from PIL import ImageGrab
    return ImageGrab.grab(bbox=tuple(bounds), all_screens=True)


class UiaSource:
    """The real screen: one cached UI Automation query over the window in front (one round trip, not one per control).
    Must be used on the thread that asked; controls never cross threads."""
    PROPS = {'name': 30005, 'type': 30003, 'rect': 30001, 'offscreen': 30022, 'enabled': 30010, 'password': 30019, 'aid': 30011, 'value': 30045}
    TYPES = {50000: 'ButtonControl', 50002: 'CheckBoxControl', 50003: 'ComboBoxControl', 50004: 'EditControl', 50005: 'HyperlinkControl',
             50007: 'ListItemControl', 50011: 'MenuItemControl', 50013: 'RadioButtonControl', 50019: 'TabItemControl', 50024: 'TreeItemControl',
             50031: 'SplitButtonControl'}
    LIMIT = 800

    BROWSERS = ('msedge.exe', 'chrome.exe', 'brave.exe', 'opera.exe', 'vivaldi.exe')
    settle = .6             # one more look after this long when nothing matched

    def __init__(self, window=None, grab=None):
        self.window = window                        # tests only: one owned window by handle instead of the window in front
        self.grab = grab                            # tests may hash their own window instead of the screen

    def _top(self):
        from .engine import uia
        if self.window is None:
            return uia.front_window()               # rails: refuses bank/login/password windows and Jarvis itself
        import uiautomation as auto
        top = auto.ControlFromHandle(self.window)
        if uia.DENY_WINDOW.search(top.Name or ''):
            raise Refused("That window looks like a bank, payment or login page. I don't read or operate those, sir.")
        return top

    # ----- site memory support -----
    def site(self):
        """'youtube.com' for a web page (read from the address bar), else the program name ('whatsapp')."""
        import ctypes
        from urllib.parse import urlsplit
        top = self._top()
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(top.NativeWindowHandle, ctypes.byref(pid))
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid.value)
        buf, size = ctypes.create_unicode_buffer(520), ctypes.c_ulong(520)
        exe = buf.value.rsplit('\\', 1)[-1].lower() if h and k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else ''
        if h:
            k.CloseHandle(h)
        self._window_rect = top.BoundingRectangle
        if exe in self.BROWSERS:
            from uiautomation import uiautomation as impl
            from .engine import uia
            uia.bound_client()
            auto = impl._AutomationClient.instance().IUIAutomation
            cache = auto.CreateCacheRequest(); cache.AddProperty(self.PROPS['value'])
            cond = auto.CreateAndCondition(auto.CreatePropertyCondition(self.PROPS['type'], 50004), auto.CreatePropertyCondition(self.PROPS['name'], 'Address and search bar'))
            bar = top.Element.FindFirstBuildCache(4, cond, cache)
            text = str(bar.GetCachedPropertyValue(self.PROPS['value']) or '') if bar else ''
            host = urlsplit(text if '://' in text else 'https://' + text).hostname if text and ' ' not in text else None
            return host[4:] if host and host.startswith('www.') else host or exe[:-4]
        return exe[:-4] if exe.endswith('.exe') else exe or None

    def fingerprint(self, element):
        import hashlib
        import uiautomation as auto
        from .site_memory import dhash
        r = getattr(self, '_window_rect', None) or self._top().BoundingRectangle
        W, H = max(1, r.right - r.left), max(1, r.bottom - r.top)
        l, t, rr, b = element.bounds
        ctrl = auto.Control.CreateControlFromElement(element.handle)
        struct = ''
        try:
            parent = ctrl.GetParentControl()
            kids = parent.GetChildren() if parent else []
            if len(kids) <= 60:
                names = [k.Name or '' for k in kids]
                i = next((n for n, k in enumerate(kids) if k.Name == element.name and k.ControlTypeName == element.kind), -1)
                struct = f'{len(kids)}|' + (names[i - 1] if i > 0 else '') + '|' + (names[i + 1] if 0 <= i < len(names) - 1 else '')
            else:
                struct = f'{len(kids)}+'
            struct = hashlib.sha1(struct.encode('utf-8')).hexdigest()[:12]
        except Exception:
            struct = ''
        try:
            look = dhash((self.grab or _grab)(element.bounds))
        except Exception:
            look = None
        try:
            cls = ctrl.ClassName or ''
        except Exception:
            cls = ''
        return {'kind': element.kind, 'name': element.name, 'aid': element.automation_id, 'cls': cls,
                'rel': [round((l - r.left) / W, 4), round((t - r.top) / H, 4), round((rr - l) / W, 4), round((b - t) / H, 4)],
                'struct': struct, 'dhash': look}

    def probe(self, saved):
        """Look ONLY at the remembered spot: the control there, checked against every anchor. (element, '') or (None, why)."""
        import uiautomation as auto
        from .site_memory import verify
        top = self._top()
        r = top.BoundingRectangle
        self._window_rect = r
        W, H = r.right - r.left, r.bottom - r.top
        x, y, w, h = saved['rel']
        ctrl = auto.ControlFromPoint(round(r.left + (x + w / 2) * W), round(r.top + (y + h / 2) * H))
        for _ in range(4):                                   # the point may land on the label inside the button
            if ctrl is None or (ctrl.ControlTypeName == saved['kind'] and (ctrl.Name or '') == saved['name']):
                break
            ctrl = ctrl.GetParentControl()
        if ctrl is None or ctrl.ControlTypeName != saved['kind']:
            return None, 'nothing like it there now'
        if ctrl.GetTopLevelControl().NativeWindowHandle != top.NativeWindowHandle or getattr(ctrl, 'IsPassword', False):
            return None, 'a different window is in the way'
        b = ctrl.BoundingRectangle
        element = Element(' '.join((ctrl.Name or '').split()), ctrl.ControlTypeName, (b.left, b.top, b.right, b.bottom), ctrl.AutomationId or '', '', ctrl.Element)
        ok, why = verify(saved, self.fingerprint(element))
        return (element, '') if ok else (None, why)

    def scan(self):
        from .engine import uia
        top = self._top()
        self._window_rect = top.BoundingRectangle
        uia.bound_client()
        from uiautomation import uiautomation as impl
        client = impl._AutomationClient.instance()
        auto = client.IUIAutomation
        cache = auto.CreateCacheRequest()
        for pid in self.PROPS.values():
            cache.AddProperty(pid)
        condition = None
        for type_id in self.TYPES:
            c = auto.CreatePropertyCondition(self.PROPS['type'], type_id)
            condition = c if condition is None else auto.CreateOrCondition(condition, c)
        # Only what is on screen: a long web page holds thousands of controls below the fold (Wikipedia 'India': 5,704 found
        # in 1.6 s without this, 179 visible in 0.6 s with it), and the old 2,400-item cut-off could miss visible ones.
        condition = auto.CreateAndCondition(condition, auto.CreatePropertyCondition(self.PROPS['offscreen'], False))
        for attempt in range(3):
            try:
                found = top.Element.FindAllBuildCache(4, condition, cache)     # 4 = all descendants
                break
            except Exception:                                      # a page in the middle of changing can refuse the question (8 Nov, Wikipedia)
                if attempt == 2:
                    raise Refused("The page is still changing, sir. Please ask me again in a moment.")
                time.sleep(.3)
        wl, wt, wr, wb = (top.BoundingRectangle.left, top.BoundingRectangle.top, top.BoundingRectangle.right, top.BoundingRectangle.bottom)
        out = []
        for i in range(found.Length):
            e = found.GetElement(i)
            try:
                if e.CachedIsOffscreen or not e.CachedIsEnabled or e.CachedIsPassword:
                    continue
                r = e.CachedBoundingRectangle
                box = (r.left, r.top, r.right, r.bottom)
                name = ' '.join((e.CachedName or '').split())
            except Exception:
                continue
            if not name or len(name) > 300 or box[2] <= box[0] or box[3] <= box[1]:
                continue
            if min(box[2], wr) <= max(box[0], wl) or min(box[3], wb) <= max(box[1], wt):
                continue                                                     # scrolled out of the window
            try:
                value = str(e.GetCachedPropertyValue(self.PROPS['value']) or '') if e.CachedControlType == 50005 else ''
            except Exception:
                value = ''
            out.append(Element(name, self.TYPES.get(e.CachedControlType, 'Control'), box, e.CachedAutomationId or '', value[:500], e))
            if len(out) >= self.LIMIT:
                break
        self._top_ctrl, self._browser = top, self._exe(top) in self.BROWSERS
        # NEVER the window's own Minimize / Maximize / Restore / Close (the owner, 8 Nov: 'press close' on a video closed Edge itself).
        out = [e for e in out if not (e.name.lower() in CAPTION and e.bounds[1] - wt < 70 and wr - e.bounds[2] < 260)]
        self._pages = []
        if self._browser:
            # The browser's OWN controls (tab strip, 'Close tab', 'Settings and more', window buttons) are labelled 'view_<n>' inside
            # Edge/Chrome; page controls never are. Dropped ALWAYS, even before the page is found (8 Nov: 'press close' hit 'Close tab').
            out = [e for e in out if not (e.automation_id.startswith('view_') and e.name.lower() not in BROWSER_KEEP)]
            out = [e for e in out if not re.match(r'close tab|new tab|search tabs|tab actions|close (?:other|all) tabs', e.name, re.I)]
            # In a browser only the PAGE is his to operate, plus Back/Forward/Refresh/Home and bookmarks. The browser's tab strip
            # ('lofi hip hop mix - YouTube'), 'Close tab', 'Settings and more' etc. are never page targets (8 Nov).
            try:
                docs = top.Element.FindAllBuildCache(4, auto.CreateAndCondition(auto.CreatePropertyCondition(self.PROPS['type'], 50030),
                                                     auto.CreatePropertyCondition(self.PROPS['offscreen'], False)), cache)
                self._pages = [docs.GetElement(i).CachedBoundingRectangle for i in range(docs.Length)]
            except Exception:
                self._pages = []
            inside = lambda b: any(p.left <= (b[0] + b[2]) / 2 <= p.right and p.top <= (b[1] + b[3]) / 2 <= p.bottom for p in self._pages)
            if self._pages:
                out = [e for e in out if inside(e.bounds) or e.name.lower() in BROWSER_KEEP or (e.kind == 'HyperlinkControl' and e.bounds[1] - wt < 200)]
        return (top.NativeWindowHandle, top.Name or ''), out

    # ----- scrolling (V4, the owner 8 Nov: 'scroll down a bit', 'scroll the playlist') -----
    def scroll(self, direction, amount='', area=None):
        """direction 'down'|'up'|'top'|'bottom'. area: the box of a list to scroll (a playlist panel), else the page / window.
        The page uses the app's own scrolling; a panel gets the mouse wheel over it, and the pointer is put back where it was."""
        import ctypes
        top = self._top()
        r = top.BoundingRectangle
        if area is None:
            try:
                from uiautomation import uiautomation as impl
                auto = impl._AutomationClient.instance().IUIAutomation
                cache = auto.CreateCacheRequest(); cache.AddProperty(self.PROPS['rect'])
                cond = auto.CreateAndCondition(auto.CreatePropertyCondition(30034, True), auto.CreatePropertyCondition(self.PROPS['offscreen'], False))
                found = top.Element.FindAllBuildCache(4, cond, cache)
                boxes = [(found.GetElement(i), found.GetElement(i).CachedBoundingRectangle) for i in range(found.Length)]
                boxes = [(e, b) for e, b in boxes if (b.right - b.left) * (b.bottom - b.top) > 0.3 * (r.right - r.left) * (r.bottom - r.top)]
                if boxes:
                    import uiautomation as ua
                    target = ua.Control.CreateControlFromElement(max(boxes, key=lambda p: (p[1].right - p[1].left) * (p[1].bottom - p[1].top))[0])
                    pattern = target.GetScrollPattern()
                    if direction in ('top', 'bottom'):
                        pattern.SetScrollPercent(-1, 0 if direction == 'top' else 100, waitTime=0)
                    else:
                        step = {'down': 3, 'up': 0} if amount != 'bit' else {'down': 4, 'up': 1}     # Large/Small Increment/Decrement
                        for _ in range(3 if amount == 'lot' else 1):
                            pattern.Scroll(2, step[direction], waitTime=0)
                    return True
            except Exception:
                pass
            area = (r.left, r.top + 150, r.right, r.bottom)
        u = ctypes.windll.user32
        class P(ctypes.Structure):
            _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]
        was = P(); u.GetCursorPos(ctypes.byref(was))
        u.SetCursorPos(int((area[0] + area[2]) / 2), int((area[1] + area[3]) / 2))
        notches = {'bit': 2, 'lot': 15}.get(amount, 5) if direction in ('down', 'up') else 60
        delta = -120 if direction in ('down', 'bottom') else 120
        for _ in range(notches):
            u.mouse_event(0x0800, 0, 0, delta, 0)
        time.sleep(.05)
        u.SetCursorPos(was.x, was.y)
        return True

    @staticmethod
    def _exe(top):
        import ctypes
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(top.NativeWindowHandle, ctypes.byref(pid))
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid.value)
        buf, size = ctypes.create_unicode_buffer(520), ctypes.c_ulong(520)
        exe = buf.value.rsplit('\\', 1)[-1].lower() if h and k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else ''
        if h:
            k.CloseHandle(h)
        return exe

    def _address(self):
        try:
            from uiautomation import uiautomation as impl
            auto = impl._AutomationClient.instance().IUIAutomation
            cache = auto.CreateCacheRequest(); cache.AddProperty(self.PROPS['value'])
            cond = auto.CreateAndCondition(auto.CreatePropertyCondition(self.PROPS['type'], 50004), auto.CreatePropertyCondition(self.PROPS['name'], 'Address and search bar'))
            bar = self._top_ctrl.Element.FindFirstBuildCache(4, cond, cache)
            return str(bar.GetCachedPropertyValue(self.PROPS['value']) or '') if bar else ''
        except Exception:
            return ''

    def _moved(self, before, wait):
        end = time.monotonic() + wait
        while time.monotonic() < end:
            if self._address() != before:
                return True
            time.sleep(.15)
        return False

    def invoke(self, element):
        """Press it the way a screen reader would; the real mouse moves only when the app offers no other way.
        A web link is checked: the address must change. A page still starting up can ignore a press (GitHub, 8 Nov),
        so it gets ONE more press another way; if the page still has not moved, report failure instead of 'clicked'."""
        import uiautomation as auto
        from .native_action import request
        ctrl = auto.Control.CreateControlFromElement(element.handle)
        if ctrl is None:
            return False
        link = getattr(self, '_browser', False) and element.kind == 'HyperlinkControl' and element.value.startswith('http')
        before = self._address() if link else ''
        if link and (not before or before.split('#')[0] == element.value.split('#')[0] or '#' in element.value):
            link = False                      # same page or an in-page jump: nothing to watch
        if request(ctrl):                     # V3's fast native default action (UIA Invoke alone can block ~2 s); one attempt only
            if link and not self._moved(before, 2.0):
                try:
                    ctrl.GetInvokePattern().Invoke(waitTime=0)
                except Exception:
                    pass
                return self._moved(before, 2.5)
            return True
        for getter, act in (('GetSelectionItemPattern', 'Select'), ('GetTogglePattern', 'Toggle')):
            try:
                p = getattr(ctrl, getter)()
                if p is not None:
                    getattr(p, act)(waitTime=0)
                    return True
            except Exception:
                continue
        try:
            ctrl.Click(simulateMove=False, waitTime=0)
            return True
        except Exception:
            return False
