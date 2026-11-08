"""The resolver (plan 13.5): instant route -> AI -> strict parse -> guards. resolve(text, snapshot, ...) -> Plan."""
import ast
import logging
import re
from dataclasses import dataclass, field

from jarvis.actions import num

from . import awareness
from .registry import ABILITIES, DROP, Ask, signature

log = logging.getLogger("jarvis2")
MAX_TOKENS = 90


@dataclass
class Call:
    ability: str
    args: dict                      # converted
    spoken: dict = field(default_factory=dict)  # as the user said it


@dataclass
class Plan:
    kind: str                       # act | ask | chat | ignore
    calls: list = field(default_factory=list)
    say: str = ""
    source: str = ""                # phrase | shape | ai
    heard: str = ""
    raw_model: str = ""
    error: str = ""
    raw: list = field(default_factory=list)      # [(ability, raw args)] kept so a "yes" can finish a question
    pending: dict | None = None     # {heard word: suggested name}
    unmatched: str = ""             # a name he said that matched nothing (a correction can teach it)
    habit: str = ""                 # set when Jarvis is offering a habit: the answer is remembered


@dataclass
class Env:
    text: str
    names: object
    now: object
    followup: bool = False


# ---------- the prompt: fixed part from the registry, changing part last ----------
RULES = """You are the understanding part of Jarvis, a voice assistant on the user's Windows laptop. Speech recognition wrote the user's words, so they can be messy, cut off or misheard. Work out what the user MEANS. Answer in one of three ways, nothing else:

1. Function lines: one line per thing asked, each with its own ability, from this list only. [ ] means optional: leave it out unless the user said it.
{abilities}

2. ASK: <one short question> when you need to know more or can't tell what was meant.
3. CHAT: <one short reply, a calm British butler, "sir"> when no action is asked: greetings, complaints, swearing, things you can't do, or speech that isn't for you.

Rules:
- Copy names exactly as written, even if they look wrong (open prome -> open(target="prome")). Another part fixes names.
- Misheard verbs: clues, lewis, spills, claws, closed = close. opened = open.
- Ignore fillers before the request, like "at your service", "yes sure", "hey jarvis".
- If the sentence names something to act on, ACT. Don't ask for confirmation.
- Only use what is in the sentence or the situation in [ ]. Never make up a time, name or number.
- Nothing outside the abilities can be done (Bluetooth, changing settings, deleting files, shutting the laptop, reading the screen): CHAT, say so.
- If an ability can answer, use it. Never answer facts yourself.
- A fact he TELLS you to remember or keep in mind is note_save with the whole fact, never CHAT. A QUESTION about a saved fact (what is my...) is note_recall.
- Any question about which timers are running or how much is left is timer_control(action="status").
- A length with the word timer and no pause, cancel, resume or stop word STARTS a new timer (timer_set).
- count: twice = 2, three times = 3. which: all, both or every = "all"."""
SHOTS = [
    ("launch spotify and set a timer for 2 minutes", 'open(target="spotify")\ntimer_set(duration="2 minutes")'),
    ("a 2 minute and a 4 minute timer", 'timer_set(duration="2 minute")\ntimer_set(duration="4 minute")'),
    ("[Now: Saturday 31 October 2026, 10:00. Running: edge, chrome. Last app mentioned: notepad.\nLast exchange: User: open notepad | Jarvis: Opening Notepad, sir.]\nshut it", 'close(target="notepad")'),
    ("lower netflix a little", 'volume(action="down", app="netflix")'),
    ("how much is left on the clock", 'timer_control(action="status")'),
    ("five minutes for the pasta", 'timer_set(duration="five minutes")'),
    ("spills the calculator", 'close(target="calculator")'),
    ("a twenty minute timer", 'timer_set(duration="twenty minute")'),
    ("thirty minute timer", 'timer_set(duration="thirty minute")'),
    ("[Now: Saturday 31 October 2026, 10:00. Running: edge, chrome.\nLast exchange: User: set a timer | Jarvis: How long, sir?]\nfifteen minutes", 'timer_set(duration="fifteen minutes")'),
    ("[Now: Saturday 31 October 2026, 10:00. Running: edge, chrome.\nLast exchange: User: open | Jarvis: Open what, sir?]\nspotify", 'open(target="spotify")'),
    ("are any timers still going", 'timer_control(action="status")'),
    ("do I have a timer running", 'timer_control(action="status")'),
    ("pause both of them timers", 'timer_control(action="pause", which="all")'),
    ("open linkedin twice", 'open(target="linkedin", count=2)'),
    ("look up train times with chrome", 'search(query="train times", browser="chrome")'),
    ("what is my locker code", 'note_recall(query="locker code")'),
    ("what have I got on the list for tomorrow", 'reminder_list(day="tomorrow")'),
    ("a little louder", 'volume(action="up")'),
    ("[Now: Saturday 31 October 2026, 10:00. Running: edge, chrome. Timers: 5 minutes, 20 minutes.\nLast exchange: User: cancel the timer | Jarvis: Which timer, sir: the 5 minute or the 20 minute?]\nthe twenty minute one", 'timer_control(action="cancel", which="twenty minute")'),
    ("keep in mind that my dentist visit is on the fifth", 'note_save(text="my dentist visit is on the fifth")'),
    ("what time is my dentist visit", 'note_recall(query="dentist visit")'),
    ("open up", "ASK: Open what, sir?"),
    ("purple the window of", "ASK: I didn't catch that, sir. Could you say it again?"),
    ("I went to the market yesterday", "CHAT: How pleasant, sir."),
    ("this is so annoying", "CHAT: My apologies, sir. Tell me what went wrong and I'll put it right."),
    ("turn off bluetooth", "CHAT: I'm afraid I can't change that, sir."),
]


def system_prompt():
    ab = [a for a in ABILITIES.values() if a.says]
    return RULES.format(abilities="\n".join(signature(a) for a in ab))


def shots():
    out = []
    for a in ABILITIES.values():
        out += a.examples[:2]
    return out + SHOTS


def messages(text, snap):
    msgs = [{"role": "system", "content": system_prompt()}]
    for u, a in shots():
        msgs += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
    sit = awareness.short(snap, text)
    if snap["last"]:
        said, reply = snap["last"][-1]["said"], snap["last"][-1]["reply"]
        sit += f"\nLast exchange: User: {said} | Jarvis: {reply}"
    return msgs + [{"role": "user", "content": f"[{sit}]\n{text[:400]}"}]


# ---------- strict parse (no guessing from broken output) ----------
def parse(out):
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S)
    lines = [x.strip() for x in out.strip().splitlines() if x.strip()]
    if not lines:
        raise ValueError("empty")
    head = lines[0]
    if head[:4].upper() == "ASK:":
        return "ask", head[4:].strip()
    if head[:5].upper() == "CHAT:":
        return "chat", head[5:].strip()
    if "(" not in head:  # plain words with no prefix: the model is chatting
        return "chat", head
    calls = []
    for ln in lines[:5]:
        e = ast.parse(ln, mode="eval").body
        if not isinstance(e, ast.Call) or not isinstance(e.func, ast.Name) or e.args:
            raise ValueError("bad call " + ln[:40])
        ab = ABILITIES.get(e.func.id)
        if ab is None or not ab.says:
            raise ValueError("unknown ability " + ln[:40])
        spec, args = {**ab.required, **ab.optional}, {}
        for kw in e.keywords:
            t = spec.get(kw.arg)
            if t is None:
                raise ValueError("unknown argument " + ln[:40])
            v = kw.value.id if isinstance(kw.value, ast.Name) and kw.value.id not in ("True", "False", "None") else ast.literal_eval(kw.value)   # which=all (no quotes) is unambiguous
            if v in ("", None):
                continue
            v = t.norm(v)
            t.check(v)
            args[kw.arg] = v
        if ab.clean:
            args = ab.clean(args)
        if not set(ab.required) <= set(args):
            raise ValueError("missing argument " + ln[:40])
        if (ab.name, args) not in calls:
            calls.append((ab.name, args))
    return "act", calls


def unsupported(raw, env):
    if re.search(r'\b(?:minimi[sz]e|maximi[sz]e|restore)\b', env.text, re.I) and any(a in ('close','tab_close','shut_down') for a, _ in raw):
        raise ValueError('window state request must never close anything')
    for name, args in raw:
        if name=='browser_tabs' and not env.followup:
            wanted='close|closed|shut' if args.get('action')=='close' else 'focus|switch|select|go'
            if not re.search(r'\b(?:'+wanted+r')\b',env.text,re.I):raise ValueError('Tab action was not requested')
            plain=lambda s:' '.join(re.findall(r'[a-z0-9]+',s.lower()))
            if plain(args.get('selector','')) not in plain(env.text):raise ValueError('Tab selector was not requested')
        if name=='window_state':
            action=args.get('action','')
            pattern={'minimize':r'minimi[sz]e','maximize':r'maximi[sz]e','restore':'restore'}.get(action,r'(?!)')
            if not re.search(r'\b'+pattern+r'\b',env.text,re.I):raise ValueError('Window action was not requested')
        ab = ABILITIES[name]
        for k, v in args.items():
            t = {**ab.required, **ab.optional}[k]
            if getattr(t, "unsupported", None) and t.unsupported(v, env):
                raise ValueError(f"{name}.{k}={v} was never asked for")


# ---------- the instant route ----------
FILLERS = re.compile(r"^(hey |hi |ok |okay )?(jarvis)?[,. ]*", re.I)
NOT_A_NAME = re.compile(r"\b(twice|thrice|times?|thing|something|stuff|it|that|this|search|set|play|remind|tabs?|first|second|third|last|all|both|one|two|three|four|five|\d+)\b")


def norm(text):
    t = re.sub(r"[^a-z0-9 ]", " ", FILLERS.sub("", text).lower())
    t = re.sub(r"\s+", " ", re.sub(r"\b(please|sir)\b", "", t)).strip()
    return re.sub(r"^(?:(?:yeah|yes|sure|ok|okay|so|well|alright|right|now|and|um|uh)\s+)+(?=\S)", "", t)       # "Yeah, sure. Shut down"


def instant(text, names, extra=None, compound=True):
    """phrases -> number shape -> name shape. (source, [(ability, args)]), or None when the AI must decide."""
    text = FILLERS.sub('', text).strip()
    text = re.sub(r'^(?:(?:can|could|would|will) you(?: please)?|please)\s+', '', text, flags=re.I)
    t = norm(text)
    if compound and re.match(r'^(?:open|close|focus|minimi[sz]e|maximi[sz]e|restore)\b',text,re.I):
        parts = re.split(r'\s+(?:and then|then|and)\s+(?=(?:open|close|focus|minimi[sz]e|maximi[sz]e|restore)\b)',text,flags=re.I)
        if 1 < len(parts) <= 8:
            hits = [instant(part,names,extra,compound=False) for part in parts]
            if all(hits):
                calls, spoken = [], []
                for hit in hits:
                    calls.extend(hit[1])
                    spoken.extend(hit[2] if hit[2] else [dict(args) for _,args in hit[1]])
                return 'phrase',calls,spoken
    from .abilities.web import tab_route
    tab_calls = tab_route(text)
    if tab_calls:
        return 'phrase', tab_calls, None
    from .abilities.windows import route as window_route
    window_calls = window_route(text)
    if window_calls:
        return 'phrase', window_calls, None
    from .abilities.sound import query_route
    volume_query=query_route(text)
    if volume_query is not None:return 'phrase',[('volume_read',volume_query)],None
    search = re.fullmatch(r'(?:search(?: up| for)?|look up|google)\s+(?:(?:on|with|using) (edge|chrome)\s+)?(.+)', text.strip(' .!?'), re.I)
    if search and not re.search(r'\b(?:on|with|using)\s+', search[2], re.I):
        return 'phrase', [('search', {'query': search[2], **({'browser': search[1].lower()} if search[1] else {})})], None
    for a in ABILITIES.values():
        if t in a.phrases:
            return "phrase", [(a.name, dict(a.phrases[t]))], None
    if extra and t in extra:
        return "phrase", [extra[t]], None
    from .organizer import route
    organized = route(text)
    if organized:
        return "phrase", [organized], None
    m = re.fullmatch(r'(?:edit|change|update) my (.+?)(?:\s*[,;:]\s*(?:it is\s+)?|\s+(?:to|is|it is|that is)\s+)(.+)', text.strip().rstrip('.!?'), re.I)
    if m:
        return 'phrase', [('note_save', {'text': 'my ' + m[1].strip() + ' is ' + m[2].strip()})], None
    m = re.fullmatch(r'my (.+?) (?:is|are) (.+)', text.strip().rstrip('.!?'), re.I)
    if m:
        return 'phrase', [('note_save', {'text': text.strip().rstrip('.!?')})], None
    if re.fullmatch(r'copy (?:that|it|this|the last answer)(?: to (?:the )?clipboard)?', text.strip(' .!?'), re.I):
        return 'phrase', [('note_copy', {})], None
    m = re.fullmatch(r'copy (?:my )?(.+?)(?: to (?:the )?clipboard)?', text.strip(' .!?'), re.I)
    if m:
        return 'phrase', [('note_copy', {'query': m[1]})], None
    # Match the original words: normalising would destroy email punctuation.
    m = re.fullmatch(r"(?:please )?(?:(?:do )?remember(?: that)?|make a note(?: that)?)\s+(.+)", text.strip().rstrip('.!?'), re.I)
    if m and not re.match(r"(?:me\b|to\b|this\b|that\b|it\b|when\b)", m[1], re.I):
        return "phrase", [("note_save", {"text": m[1]})], None
    m = re.fullmatch(r"(?:what is|what's|what was|tell me|recall) my (.+?)[.?!]*", text.strip(), re.I)
    if m:
        return "phrase", [("note_recall", {"query": m[1]})], None
    m = re.fullmatch(r"(?:i am|i'm) (.+?)[.!]*", text.strip(), re.I)
    if m and re.search(r"\b(student|studying|cs|degree)\b", m[1], re.I):
        return "phrase", [("note_save", {"text": "I am " + m[1]})], None
    for a in ABILITIES.values():
        for rx, fn in a.patterns:
            m = re.fullmatch(rx, t)
            if m:
                return "phrase", [(a.name, fn(m))], None
    m = re.fullmatch(r"(?:set )?(?:the )?volume (?:to )?([a-z0-9 ]{1,20})", t)
    n = num(m[1]) if m else None
    if n is not None and "volume" in ABILITIES and n <= 100:
        return "phrase", [("volume", {"action": "set", "level": int(n)})], None
    out = shape(text, names)
    return ("shape", [(a, ar) for a, ar, _ in out], [{"target": said} for _, _, said in out]) if out else None      # said = the words he used, kept so a correction can learn them


def shape(text, names):
    """<verb> <known name>[, <name> and <name>]: every name must match well and clear of the runner-up, else the AI decides."""
    verbs = {v: a for a in ABILITIES.values() for v in a.verbs if len(a.required) == 1 and "target" in a.required}
    lead = re.compile(r"^(.*?[.,?!]\s+)?(?=(?:" + "|".join(verbs) + r")\b)", re.I)
    t = lead.sub("", FILLERS.sub("", text).strip()).strip(" .,!?").lower()
    t = re.sub(r"^(open|close|focus|switch to)[,.]\s*", r"\1 ", t)
    other = re.compile(r"\b(" + "|".join(map(re.escape, verbs)) + r")\b")
    for v in sorted(verbs, key=len, reverse=True):
        if t.startswith(v + " "):
            rest = re.sub(r"\s+(both|all)$", "", t[len(v):].strip())
            parts = [x for x in re.split(r"\s*,\s*|\s+and\s+", rest) if x]
            if not parts or len(parts) > 4 or NOT_A_NAME.search(rest) or other.search(rest):
                return None
            out = []
            for x in parts:
                kinds = verbs[v].required["target"].kinds
                n, sc, r = names.match(x, kinds)
                if sc < 0.8 or sc - r < 0.04:
                    return None
                out.append((verbs[v].name, {"target": n}, x))
            return out
    return None


# ---------- guards: types convert, names match ----------
def convert(raw, env):
    """[(ability, raw args)] -> [Call]. Raises Ask."""
    calls = []
    for name, args in raw:
        ab = ABILITIES[name]
        spec, out = {**ab.required, **ab.optional}, {}
        for k, v in args.items():
            c = spec[k].convert(v, env)
            if c is not DROP:
                out[k] = c
        calls.append(Call(name, out, dict(args)))
    return calls


CLAIM = re.compile(r"\b(i've|i have|i will|i'll|i am going to|i'm going to|done|copied|clipboard|opened|closed|started|stopped|paused|muted|cancelled|now (?:opening|closing))\b", re.I)


def request_echo(request, answer):
    """A model repeating a command as a question is not a clarification.
    Keep real questions such as 'Open what?' or 'Which timer?' intact.
    """
    if not re.search(r'\b(open|close|closed|focus|switch|search|google|copy|stop|shut|play|pause|set|remind)\b', request, re.I):
        return False
    fillers = set('can could would will you i like want please kindly just sir did do mean to yes yeah the a an on'.split())
    words = lambda s: set(re.findall(r'[a-z0-9]+', s.lower())) - fillers
    a, b = words(request), words(answer)
    return len(a) >= 2 and len(a & b) >= .8 * max(len(a), len(b))


def resolve(text, snap, names, ai, now, followup=False, extra=None, hit=None, checked=False):
    env = Env(text, names, now, followup)
    plan = Plan("ignore", heard=text)
    try:
        if not checked:
            hit = instant(text, names, extra)
        if hit:
            plan.source, plan.raw, said = hit
            plan.kind, plan.calls = "act", [Call(a, args, said[i] if said else dict(args)) for i, (a, args) in enumerate(plan.raw)]
            return plan
        plan.source = "ai"
        if ai is None:
            plan.kind, plan.say, plan.error = "ask", "I need my thinking part for that, sir.", "no ai"
            return plan
        msgs, last = messages(text, snap), None
        for temp in (0.0, 0.3):
            plan.raw_model = ai.complete(msgs, temperature=temp, max_tokens=MAX_TOKENS)
            try:
                kind, body = parse(plan.raw_model)
                if kind == "act":
                    unsupported(body, env)
                elif request_echo(text, body) or (snap.get('last') and re.fullmatch(r'yes[.! ]*', text, re.I) and request_echo(snap['last'][-1]['said'], body)):
                    msgs = msgs + [{'role':'assistant', 'content':plan.raw_model}, {'role':'user', 'content':'You repeated the request without doing it. Return the requested allowlisted function calls. If a necessary detail is missing, ask ONLY for that detail.'}]
                    raise ValueError('request repeated instead of executed')
                break
            except (ValueError, SyntaxError) as e:
                last = e
                log.warning("parse failed (%s): %r", e, plan.raw_model[:120])
        else:
            plan.kind, plan.say, plan.error = "ask", "Sorry, sir, I didn't follow that. Could you say it again?", f"parse: {last}"
            return plan
        if kind != "act":
            plan.kind, plan.say = kind, body
            if kind == "chat" and CLAIM.search(body):
                plan.say = "I haven't done anything yet, sir. What would you like me to do?"
            return plan
        plan.kind, plan.raw = "act", body
        plan.calls = convert(body, env)
    except Ask as a:
        plan.kind, plan.say, plan.pending, plan.calls, plan.unmatched = "ask", a.question, a.pending, [], a.heard or ""
    return plan
