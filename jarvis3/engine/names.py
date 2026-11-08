"""Names by sound + spelling + usage, no first-letter rule (plan 13.2 decision 9). Started from the stage 1 experiments (git history, tag v2-stage1)."""
import difflib
from datetime import datetime
import math
import os
import re

from .registry import Ask

from jarvis3.paths import RUNTIME, PROJECT, ASSETS
ROOT = str(RUNTIME)
CANON = {"yt": "youtube", "you tube": "youtube", "google chrome": "chrome", "microsoft edge": "edge", "whatsapp - shortcut": "whatsapp", "chat gpt": "chatgpt", "gpt": "chatgpt", "gbt": "chatgpt", "chat gbt": "chatgpt", "explorer": "file explorer", "files": "file explorer",
         "whisper flow": "wispr flow", "whisper no pro": "wisperno pro", "wisperno": "wisperno pro", "anti gravity": "antigravity", "quickshare": "quick share", "armory crate": "armoury crate",
         "antigravity ide": "antigravity", "claude code": "claude"}
SURE, MAYBE, GAP = 0.8, 0.6, 0.08


def sound(s):
    """A rough sound key: same letters for what sounds alike, Indian-English v/w included. Vowels only matter at the start."""
    s = re.sub(r"[^a-z]", "", s.lower())
    for a, b in (("tch", "c"), ("sch", "s"), ("ch(?=[rl])", "k"), ("ch", "c"), ("sh", "s"), ("ph", "f"), ("wh", "w"), ("ck", "k"), ("qu", "k"), ("q", "k"), ("x", "ks"),
                 ("g(?=[eiy])", "j"), ("c(?=[eiy])", "s"), ("gh", ""), ("dg", "j"), ("v", "w"), ("z", "s"), ("d", "t"), ("c(?=.)", "k"), ("y(?=$)", "")):
        s = re.sub(a, b, s)
    head, rest = s[:1], s[1:]
    rest = re.sub(r"[aeiouy]", "", rest)
    if head in "aeiouy":
        head = ""
    return re.sub(r"(.)\1+", r"\1", head + rest)


def clean(s):
    s = re.sub(r"[^a-z0-9. ]", " ", s.lower().replace("'", ""))
    s = re.sub(r"^(the|my|up|a|an)\s+", "", s.strip())
    return re.sub(r"\s+(app|application|tab|tabs|browser|folder|window|website|site|sir|please)$", "", s).strip()


def requested_kinds(heard,kinds,text=''):
    """An explicit folder/app/site qualifier narrows, never widens the target."""
    value=heard.strip(' .!?').lower()
    suffix=re.search(r'\b(folder|file|app|application|website|site|browser)\s*$',value)
    if not suffix and value:
        suffix=re.search(r'(?<!\w)'+re.escape(value)+r'\s+(folder|file|app|application|website|site|browser)\b',text,re.I)
    if not suffix:return kinds
    allowed={'folder':('folder',),'file':('file',),'app':('app',),'application':('app',),
             'browser':('app',),'website':('site','bookmark'),'site':('site','bookmark')}[suffix[1].lower()]
    return tuple(k for k in kinds if k in allowed)


def spoken_span(span, text):
    """Did the user really say something like this name? Stops the AI inventing or swapping one."""
    a, b = clean(span).replace(" ", ""), re.sub(r"[^a-z0-9]", "", text.lower())
    if not a or a in b:
        return bool(a)
    sa, sb = sound(a), sound(b)
    return bool(sa) and (sa in sb or difflib.SequenceMatcher(None, a, b).find_longest_match().size >= max(3, len(a) * 0.5) or difflib.SequenceMatcher(None, sa, sb).find_longest_match().size >= max(2, len(sa) * 0.6))


def log_usage():
    """How often the owner has named each thing, read from V1's log. ponytail: Phase 6 replaces this with the usage table."""
    p = os.path.join(ROOT, "logs", "conversation.log")
    lines = [x.lower() for x in open(p, encoding="utf-8", errors="replace") if " You" in x[:16]] if os.path.exists(p) else []
    return lambda n: sum(n in x for x in lines)


class Names:
    """catalog: {name: kind}. usage(name) -> how many times used. running: names of running apps (win close calls)."""

    def __init__(self, catalog, usage=None, running=(), memory=None):
        """memory: what he has taught it (aliases) and how he uses things (usage by hour). usage(name) is the older count from V1's log, added to it."""
        self.catalog, self.running, self.memory, self._old = dict(catalog), set(running), memory, usage or (lambda n: 0)
        self._ns = {n: sound(n) for n in self.catalog}            # computed once: matching runs several times a sentence over ~500 names

    def usage(self, n):
        return self._old(n) + (self.memory.usage_total(n) if self.memory else 0)

    def prior(self, k):
        """Things he uses (up to +0.2) and things running now (+0.1) win close calls."""
        use = min(1.0, math.log1p(self.usage(k)) / math.log1p(30))
        around_now = 0.05 if self.memory and self.memory.usage_at(k, datetime.now().hour) >= 3 else 0     # he usually uses it at this hour
        return 0.2 * use + around_now + (0.1 if k in self.running else 0)

    def match(self, heard, kinds):
        """-> (best name, score, runner-up score)."""
        out = self.scores(heard, kinds)
        best = sorted(out.items(), key=lambda x: -x[1])[:2]
        if not best:
            return None, 0, 0
        return best[0][0], best[0][1], best[1][1] if len(best) > 1 else 0

    def scores(self, heard, kinds):
        """{name: score} for every name of these kinds."""
        h = clean(heard)
        names = [n for n, k in self.catalog.items() if k in kinds]
        if not h:
            return {}
        if h in CANON and CANON[h] in names:
            return {CANON[h]: 1}
        al = self.memory.alias_active(h) if self.memory else None      # a word he taught it (one correction) or that kept working (three times)
        if al and al[0] in names:
            return {al[0]: 1}
        if h in names:
            return {h:1}
        hs, hc = sound(h), h.replace(" ", "")
        out, raw = {}, {}
        for n in names:
            c = n.replace(" ", "")
            sp = difflib.SequenceMatcher(None, hc, c).ratio()
            ns = self._ns[n]
            ph = difflib.SequenceMatcher(None, hs, ns).ratio() if len(hs) >= 2 and len(ns) >= 2 else 0
            score = max(sp, ph * 0.97)
            if c.startswith(hc) and len(hc) >= 3:
                score = max(score, 0.8)
            k = CANON.get(n, n)
            raw[k] = max(raw.get(k, 0), score - (0.05 if self.catalog.get(n) == 'file' else 0))      # a file name must fit a little better than an app's
        top = max(raw.values(), default=0)
        # use and running apps only break ties between names that fit about equally well (they once pushed 'whisper' to WhatsApp)
        return {k: s + self.prior(k) if s >= 0.5 and s >= top - 0.15 else s for k, s in raw.items()}

    def hint(self, n=30, limit=260):
        """What Whisper is told to expect: the name, then the things he uses most (his log), then the rest. Short: a long hint makes it invent words."""
        pool = [x for x, k in self.catalog.items() if k in ("app", "site") and 3 <= len(x) <= 18 and re.fullmatch(r"[a-z0-9 .]+", x)]
        pool.sort(key=lambda x: (-self.usage(x), x))
        out = "Jarvis"
        for x in pool[:n]:
            if len(out) + len(x) + 2 > limit:
                break
            out += ", " + x.title() if not x.isupper() else ", " + x
        return out + "."

    def explained(self, name, kinds, text):
        """Is this name what the user's words sound like? Any 1 to 3 word stretch of the sentence must score it, else the AI swapped or invented it.
        Returns (True, None) or (False, the name the words sound most like, or None)."""
        w = clean(text).split()
        best, top = None, 0
        for i in range(len(w)):
            for j in range(i + 1, min(i + 4, len(w)) + 1):
                sc = self.scores(" ".join(w[i:j]), kinds)
                if sc.get(name, 0) >= 0.75:
                    return True, None
                for n, s in sc.items():
                    if s > top:
                        best, top = n, s
        return (False, best if top >= 0.6 else None)

    def decide(self, heard, kinds):
        n, s, r = self.match(heard, kinds)
        if s >= SURE and s - r >= GAP / 2:
            return "ok", n, s
        if s >= MAYBE and s - r >= GAP:
            return "ok", n, s
        return ("ask" if s >= MAYBE else "none"), n, s

    def resolve(self, heard, kinds, env):
        """The Name type's convert(): a real catalog name, or Ask."""
        from jarvis3.legacy.actions import NEVER_OPEN
        said = clean(heard)
        if said not in self.catalog and NEVER_OPEN.search(said):   # 'open terminal': say why, never guess a near name
            raise Ask(f"I don't open {said}, sir. Terminals, command windows and system tools stay off my list.", heard=heard)
        verdict, name, score = self.decide(heard, kinds)
        if verdict == "ok" and not env.followup:
            ok, near = self.explained(name, kinds, env.text)
            if not ok and not spoken_span(heard, env.text):
                raise Ask(f"Do you mean {near}, sir?", pending={heard: near}) if near else Ask("Which one, sir?")
            if not ok and near and near != name:
                raise Ask(f"Do you mean {near}, sir?", pending={heard: near})
        if verdict == "ok":
            return name
        if verdict == "ask":
            raise Ask(f"Do you mean {name}, sir?", pending={heard: name}, heard=heard)
        raise Ask(f"I heard {heard}, sir, but I don't know that one." + (f" The nearest is {name}." if name and score >= 0.4 else ""), heard=heard)
