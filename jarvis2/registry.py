"""The registry IS the allowlist (plan 13.4): an ability exists only if it is declared here with @ability.
Argument types check what the AI wrote (`check`) and turn the user's words into real values (`convert`)."""
import re
from dataclasses import dataclass, field
from typing import Callable


DROP = object()  # convert() returns this to say "leave this argument out"


class Ask(Exception):
    """Raised by convert(): the words aren't enough, so the user is asked. `question` is spoken."""

    def __init__(self, question, pending=None, heard=None):
        super().__init__(question)
        self.question, self.pending, self.heard = question, pending, heard     # heard: the name he said that could not be matched (a correction can teach it)


NUMW = {"one": 1, "a": 1, "an": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "half": 0.5}


def to_seconds(w):
    """Words -> seconds, exactly. None if there's no clear number and unit."""
    w = re.sub(r"(\d)\s*(secs?|mins?|hrs?)\b", r"\1 \2", str(w).lower().replace("-", " "))
    total = 0
    for n, unit in re.findall(r"(\d+(?:\.\d+)?|[a-z]+)\s+(sec|second|min|minute|hr|hour)s?\b", w):
        v = float(n) if n[0].isdigit() else NUMW.get(n)
        if v is None:
            return None
        total += v * {"s": 1, "m": 60, "h": 3600}[unit[0]]
    return round(total) or None


def number_said(v, env):
    """Did the user say the number in `v` (as digits or words)? The AI must not invent a length."""
    spoken = [t for t in re.findall(r"\d+|[a-z]+", str(v).lower()) if t not in ("minute", "minutes", "second", "seconds", "hour", "hours", "min", "mins", "sec", "secs", "an", "a")]
    low = env.text.lower()
    said = lambda t: t in low or any(w in low for w, n in NUMW.items() if str(n) == t)  # '1' may have been said as 'one'
    return env.followup or any(said(t) for t in spoken) or not spoken


class Type:
    hint = '"..."'

    def norm(self, v):
        return v

    def check(self, v):
        raise NotImplementedError

    def convert(self, v, env):
        return v


class Text(Type):
    def check(self, v):
        if not isinstance(v, str) or len(v) > 200:
            raise ValueError("text")


class Name(Type):
    """Something to open, close or focus. Matched by sound and spelling in names.py; the AI only copies the words."""

    def __init__(self, kinds=("app", "site", "bookmark", "folder", "file"), lenient=False):
        self.kinds, self.lenient = kinds, lenient          # lenient: a word that matches nothing is kept as said (a site Jarvis has never heard of: "search X on Patreon")

    check = Text.check

    def convert(self, v, env):
        try:
            return env.names.resolve(v, self.kinds, env)
        except Ask as a:
            if self.lenient and not a.pending:             # "I don't know that one": not a near miss, just unknown
                return v.strip().lower()
            raise


class Choice(Type):
    """evidence: {value: regex}. The chosen value needs one of its words in the sentence (unless it follows an earlier exchange),
    else the AI picked an action nobody asked for: the resolver treats it like a bad parse and retries."""

    def __init__(self, *values, evidence=None, aliases=None):
        self.values, self.hint, self.evidence, self.aliases = values, "|".join(map(str, values)), evidence or {}, aliases or {}

    def norm(self, v):
        return self.aliases.get(v, v)         # plain synonyms the ability declares ('quieter' = 'down'); nothing is guessed

    def check(self, v):
        if v not in self.values:
            raise ValueError("choice")

    def unsupported(self, v, env):
        return not env.followup and v in self.evidence and not re.search(self.evidence[v], env.text, re.I)


class Number(Type):
    hint = "number"

    def __init__(self, lo=0, hi=100):
        self.lo, self.hi = lo, hi

    def check(self, v):
        if isinstance(v, bool) or not isinstance(v, int) or not self.lo <= v <= self.hi:
            raise ValueError("number")


class Bool(Type):
    hint = "True|False"

    def check(self, v):
        if not isinstance(v, bool):
            raise ValueError("bool")


class Duration(Type):
    def check(self, v):
        if not isinstance(v, str):
            raise ValueError("duration")

    def convert(self, v, env):
        secs = to_seconds(v)
        if not secs or not number_said(v, env):
            raise Ask("How long, sir?")
        return secs


class Which(Duration):
    """Which timer: 'all', or its length in the user's words (-> seconds as text). No length at all: leave the argument out."""

    def convert(self, v, env):
        if str(v).lower() in ("all", "both", "every", "each", "everything"):
            return "all"
        if not number_said(v, env):
            return DROP  # the AI invented a length the user never said: act as if none was named
        secs = to_seconds(v) or to_seconds(f"{v} minute" if re.search(re.escape(str(v)) + r"\s*-?\s*min", env.text, re.I) else "")
        if not secs:
            raise Ask("Which timer, sir?")
        return str(secs)


class When(Type):
    def check(self, v):
        if not isinstance(v, str):
            raise ValueError("when")

    def convert(self, v, env):
        from jarvis.timeparse import parse_when
        _, due = parse_when(v, env.now)
        if due is None:
            raise Ask("When, sir?")
        return due


@dataclass
class Result:
    ok: bool
    plain: str                      # a true, complete sentence, always given
    facts: dict = field(default_factory=dict)
    details: str = ""
    undo: Callable | None = None
    exact: bool = False             # lists, goodbyes: speak plain as is


@dataclass
class Ability:
    name: str
    says: str | None                # None: not offered to the AI (instant route only)
    required: dict
    optional: dict
    risk: str
    examples: list
    phrases: dict
    verbs: tuple
    fn: Callable
    patterns: list = field(default_factory=list)   # [(regex, fn(match) -> args)]: whole-sentence shapes for the instant route that carry a free word (a routine's name)
    clean: Callable | None = None   # drops arguments that make no sense together, before anything else looks at them


ABILITIES: dict[str, Ability] = {}


def ability(name, says, required=None, optional=None, risk="safe", examples=(), phrases=None, verbs=(), clean=None, patterns=()):
    assert risk in ("safe", "confirm"), "anything 'never' simply has no ability"

    def wrap(fn):
        ABILITIES[name] = Ability(name, says, required or {}, optional or {}, risk, list(examples), phrases or {}, tuple(verbs), fn, list(patterns), clean)
        return fn
    return wrap


def signature(a):
    args = [f"{k}={t.hint}" for k, t in a.required.items()] + [f"[{k}={t.hint}]" for k, t in a.optional.items()]
    return f"{a.name}({', '.join(args)}): {a.says}"
