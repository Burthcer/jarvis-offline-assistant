"""Operating other apps and reading the screen, through UI Automation (jarvis3.engine/uia.py, where the rails live). Nothing irreversible happens without a spoken yes:
sending a message, clicking a button called Send/Pay/Delete..., pressing Enter right after typing. The yes is the `confirmed` flag the app sets when he answers a question."""
import re
import time

from ..registry import Ask, Choice, Name, Result, Text, ability
from ..uia import KEYS, Refused, risky, parse_key
from .apps import pretty

CONFIRM = {"confirm": "yes"}          # a non-empty `pending` makes the app wait for his yes / no, then run the ability again with ctx.confirmed set
TYPED_WINDOW_S = 90                   # Enter within this long of typing something is "send"

ANSWER_RULES = ("You are Jarvis, a calm British butler. Answer the question using ONLY the screen text below. Two short sentences at most. Say 'sir' once. "
                "If the text does not contain the answer, say you can't see it on the screen. Never invent anything.")


@ability("screen_ask", "read or answer a question about what is on the screen (the window in front). question = what they asked",
         required={"question": Text()}, examples=[("what does this page say about the price", 'screen_ask(question="what does the page say about the price")')],
         phrases={p: {"question": "read me what is on the screen"} for p in ("read the screen", "read this", "read this page", "what is on my screen", "whats on my screen", "what is on the screen", "read the window")})
def screen_ask(args, ctx):
    try:
        text = ctx.os.ui_read()
    except Refused as e:
        return Result(False, str(e))
    if not text.strip():
        return Result(False, "I can't read anything in that window, sir. Some apps don't share their text.")
    if ctx.ai is None:
        return Result(False, "I need my thinking part to read that, sir.")
    msgs = [{"role": "system", "content": ANSWER_RULES}, {"role": "user", "content": f"SCREEN TEXT:\n{text[:3000]}\n\nQUESTION: {args['question']}"}]
    out = ctx.ai.complete(msgs, temperature=0.2, max_tokens=120).strip()
    return Result(True, out or "I can't see that on the screen, sir.", {"chars": len(text)}, exact=True)


@ability("ui_click", "click a button, link, tab or menu item by its label in the window in front (label = the words on it)", required={"label": Text()},
         examples=[("press the save button", 'ui_click(label="save")')])
def ui_click(args, ctx):
    label = args["label"].strip()
    if (risky(label) or risky(ctx.text)) and not ctx.confirmed:
        raise Ask(f"Shall I click '{label}', sir?", pending=CONFIRM)
    known = ctx.memory.alias_active(label.lower()) if ctx.memory else None      # Settings > corrections: a word he taught for a name
    also = ((known[0],) if known else ()) + VERB_WORDS.get(label.lower(), ())[1:]
    try:
        found = ctx.os.ui_target(label, also, ctx.confirmed)
    except Refused as e:
        return Result(False, str(e))
    return _screen_reply(found)


def short_name(label):
    """Say a short label ('Shorts', 'Subscriptions'); never read out a long video title (the owner, 8 Nov)."""
    label = " ".join(str(label or "").split())
    return label if len(label.split()) <= 4 and len(label) <= 32 else ""


def _screen_reply(found):
    """One shape for 'click X' and for the answer to 'which one?'."""
    from jarvis3.screen_index import speak_names
    status = found["status"]
    if status == "clicked":
        return Result(True, f"Clicked {short_name(found['label'])}, sir." if short_name(found["label"]) else "Done, sir.", {"label": found["label"]}, exact=True)
    if status == "risky":
        raise Ask(f"That is '{found['label']}', sir. Shall I click it?", pending=CONFIRM)
    if status == "ambiguous":
        raise Ask(f"I see {found['count']} matches for {found['label']}, sir: {speak_names(found['names'])}. Which one?", pending={"screen_choice": True})
    if status == "cancelled":
        return Result(True, "Very good, sir.", {"silent": False})
    return Result(False, "Please ask me again what to click, sir.")


@ability("ui_nth", None, required={"n": Text()}, optional={"label": Text(), "scope": Text()})
def ui_nth(args, ctx):
    """'click the third video in this playlist' / 'the first mix, Josie Edwards' (route: nth_route)."""
    screen = ctx.os.ui_screen()
    if screen is None:
        return Result(False, "I can't see the screen here, sir.")
    try:
        found = screen.nth(int(args["n"]), args.get("label", ""), args.get("scope", ""))
    except Refused as e:
        return Result(False, str(e))
    if found["status"] == "risky" and not ctx.confirmed:
        raise Ask(f"That is '{found['label']}', sir. Shall I click it?", pending=CONFIRM)
    if found["status"] == "risky":
        found = screen.target(found["label"], (), True)
    return _screen_reply(found)


SCROLL_WHERE = r"playlist|list|queue|panel|sidebar|side bar|side panel|chat|comments|results|up next"


def _scroll_args(m):
    words = m[0]
    direction = "top" if re.search(r"\btop\b", words) else "bottom" if re.search(r"\b(?:bottom|end)\b", words) else "up" if re.search(r"\bup\b", words) else "down"
    amount = "bit" if re.search(r"\b(?:bit|little|slightly|tiny)\b", words) else "lot" if re.search(r"\b(?:lot|way|much)\b", words) else ""
    where = re.search(SCROLL_WHERE, words)
    return {"direction": direction, "amount": amount, "where": where[0] if where else ""}


@ability("scroll", None, required={"direction": Text()}, optional={"amount": Text(), "where": Text()},
         patterns=[(rf"(?:scroll|go|move)(?: (?:the|this) (?:{SCROLL_WHERE}))? (?:down|up)(?: (?:a bit|a little(?: bit)?|slightly|a lot|a tiny bit|way down|way up|more|again))*(?: (?:in|on) (?:the|this) (?:{SCROLL_WHERE}|page))?", _scroll_args),
                   (rf"scroll (?:a bit|a little(?: bit)?|slightly|a lot)(?: (?:down|up))?(?: (?:in|on) (?:the|this) (?:{SCROLL_WHERE}|page))?", _scroll_args),
                   (rf"(?:scroll|go|jump) to the (?:top|bottom|end)(?: of (?:the|this) (?:{SCROLL_WHERE}|page))?", _scroll_args),
                   (rf"scroll (?:the|this) (?:{SCROLL_WHERE}|page)(?: (?:down|up))?", _scroll_args)])
def scroll(args, ctx):
    screen = ctx.os.ui_screen()
    if screen is None:
        ctx.os.ui_press("page up" if args["direction"] in ("up", "top") else "page down")
        return Result(True, "", {"silent": True})
    try:
        moved = screen.scroll(args["direction"], args.get("amount", ""), args.get("where", ""))
    except Refused as e:
        return Result(False, str(e))
    return Result(True, "", {"silent": True}) if moved else Result(False, "I tried, but it didn't move, sir. It may already be at the end.", exact=True)


@ability("screen_numbers", None, phrases={p: {} for p in ("number the screen", "number everything", "number everything on the screen", "number the page",
                                                           "show numbers", "show the numbers", "number the buttons", "number the links", "label the screen",
                                                           "put numbers on the screen", "number everything on screen", "number this page", "number this screen")})
def screen_numbers(args, ctx):
    """Spec Tier 2 on request: numbers over the pressable things on screen; his next 'click 12' / 'twelve' presses that one."""
    screen = ctx.os.ui_screen()
    if screen is None:
        return Result(False, "I can't see the screen here, sir.")
    try:
        count = screen.number_all()
    except Refused as e:
        return Result(False, str(e))
    raise Ask(f"I've numbered {count} things, sir. Which number?", pending={"screen_choice": True})


@ability("ui_pick", None, required={"said": Text()})
def ui_pick(args, ctx):
    """His answer to 'which one?': 'the second one', 'the chill synthwave one'. Reached only from that question (app._answer_pending)."""
    try:
        found = ctx.os.screen.pick(args["said"])
    except Refused as e:
        ctx.app.draft = None
        return Result(False, str(e))
    task = getattr(ctx.app, "task", None)
    if task is not None:
        if found["status"] == "clicked":
            from .tasks import step_done
            return step_done(ctx)                    # the multi-step task carries on
        if found["status"] != "ambiguous":
            ctx.app.task = None
    draft = getattr(ctx.app, "draft", None)
    if draft is not None and draft.stage == "contact":
        if found["status"] == "clicked":
            from .drafts import compose
            return compose(ctx)                      # he picked the contact: now write the message
        if found["status"] != "ambiguous":
            ctx.app.draft = None
    return _screen_reply(found)


SCREEN_NOUNS = r"playlist|channel|video|mix|link|button|result|chat|conversation|song|option|icon|item|card|server"
MEDIA_WORD = r"(?:next|previous|prev|same|current|new|random|this|that)\b"     # 'play the previous song' is the media player's job
ORDINAL_WORD = r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d{1,2}(?:st|nd|rd|th)?)"


OPEN_VERBS = r"(?:open|open up|start|launch|go to|switch to|bring up|take me to|pull up)"


def open_target(text):
    """'open shots', 'start shorts', 'go to subscriptions' -> 'shots' / 'shorts' / 'subscriptions': the words to look for ON SCREEN.
    Asked only when the sentence names no app, site or folder Jarvis knows (app.handle), and acted on only when it is visible."""
    from ..understand import norm
    m = re.fullmatch(rf"{OPEN_VERBS} (?:the |my |that |this )?(.{{1,60}}?)(?: (?:on|from) (?:the )?(?:screen|page))?", norm(text))
    if not m:
        return None
    label = m[1].strip()
    if re.match(ORDINAL_WORD + r"\b", label) or re.match(MEDIA_WORD, label) or re.search(r"\b(?:and|then)\b", label):
        return None
    if re.search(r"\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|tabs?|windows?)\b", label):
        return None                                              # 'open two YouTube tabs' is the open ability's job
    if label in ("what", "you", "it", "this", "that", "me", "him", "her", "them", "something", "anything"):
        return None
    from jarvis3.legacy.actions import NEVER_OPEN
    if NEVER_OPEN.search(label):
        return None                                              # terminal, registry, narrator...: refused as before, never via a click
    return label


ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "last": -1}
LIST_NOUN = r"video|videos|song|songs|mix|mixes|playlist|playlists|result|results|link|links|item|items|one|option|options|choice|choices|channel|card|entry|row|chat|message|email|file|track|search result"
SCOPE = r"(?:in|on|from|of|inside) (?:this|the|my|that) (playlist|list|queue|panel|sidebar|side bar|side panel|page|results|search results|screen|up next)"


def nth_route(t):
    """'click the third video in this playlist', 'click on the first mix josie edwards', 'play the second video by ian asher'.
    Bare 'click the first mix' (no words, no list named) stays with V3's numbered choices."""
    t = re.sub(r"\s+on (?:the )?(?:screen|page)$", "", t)    # 'on screen' names no list: V3's numbered choices
    scope = re.search(SCOPE + r"$", t)
    body = t[:scope.start()].strip() if scope else t
    m = re.fullmatch(rf"(?:click|tap|select|open|play|start|choose|pick|press)(?: on)?(?: the| that)? (first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d{{1,2}}(?:st|nd|rd|th)?|number \d{{1,2}})(?: ({LIST_NOUN}))?(?:(?: (?:by|from|of|called|named|titled|with|that says|about))? (.+?))?", body)
    if not m or not (scope or m[3]):
        return None
    if m[3] and re.match(MEDIA_WORD, m[3]):
        return None                                           # 'play the second next song' = skip two songs (V3 media)
    if m[3] and not scope and all(re.fullmatch(LIST_NOUN + r"|here", w) for w in m[3].split()):
        return None                                           # 'pick the second mix playlist' names no title: V3's numbered choices
    word = m[1].replace("number ", "")
    n = ORDINALS.get(word) or int(re.sub(r"\D", "", word))
    noun = m[2] or ""
    label = (m[3] or "").strip()
    if label and noun and noun.rstrip("es").rstrip("s") in ("mix", "playlist", "channel"):
        label = f"{label} {noun.rstrip('es') if noun.endswith('mixes') else noun.rstrip('s')}"   # 'the first mix, Josie Edwards' must be a mix
    return [("ui_nth", {"n": str(n), "label": label, "scope": scope[1] if scope else ""})]


PANEL = r"playlist|panel|sidebar|side bar|side panel|menu|popup|pop up|dialog|video|player|chat|comments|description|ad|ads|banner|notification|list|queue|box"
VERB_WORDS = {"close": ("close", "dismiss", "close dialog", "close panel"), "collapse": ("collapse", "hide", "show less"),
              "expand": ("expand", "show more"), "hide": ("hide", "collapse", "close"), "minimize": ("minimize", "collapse"), "skip": ("skip", "skip ad", "skip ads")}


def route(t):
    """'click the download button', 'tap on Gaming Hub', 'press the save button', 'play the mix playlist', 'open the gaming channel' -> ui_click.
    Left alone: real keys ('press enter'), ordinals ('click the second one' = numbered choices), tabs, folders and files (they have their own abilities)."""
    if re.search(r"\bscreen ?shot\b", t):                     # 'click screenshot' = take one (the owner's own words)
        return None
    nth = nth_route(t)
    if nth:
        return nth
    m = re.fullmatch(rf"(collapse|expand|hide|minimi[sz]e|close|dismiss|skip) (?:the |this |that )?((?:\w+ ){{0,2}}(?:{PANEL}))", t)
    if m:                                                     # 'collapse the playlist', 'close the video popup', 'skip the ad': the page's own button
        verb = {"minimise": "minimize", "dismiss": "close"}.get(m[1], m[1])
        return [("ui_click", {"label": verb})]                 # the page's button; the window's own Close is never a target
    m = re.fullmatch(r"(click|tap|press|hit|select|choose)(?: on)?(?: the| that| this)? (.{1,80})", t)
    if m:
        label = m[2].strip()
        if re.match(ORDINAL_WORD + r"\b", label) or label in ("all", "everything") or re.match(MEDIA_WORD, label):
            return None
        if m[1] in ("press", "hit", "tap") and (parse_key(label) or parse_key(re.sub(r" (?:key|button)$", "", label))) and not label.endswith(" button"):
            return None
        return [("ui_click", {"label": label})]
    m = re.fullmatch(rf"(?:play|open|start|go to) (?:the|that|this) ((?!{ORDINAL_WORD}\b|{MEDIA_WORD}).{{1,70}} (?:{SCREEN_NOUNS}))", t)
    if m:
        return [("ui_click", {"label": m[1]})]
    return None


@ability("ui_type", "type words into the text box that has the cursor in the window in front. Does NOT press Enter", required={"text": Text()},
         examples=[("type hello there", 'ui_type(text="hello there")')])
def ui_type(args, ctx):
    try:
        ctx.os.ui_type(args["text"])
    except Refused as e:
        return Result(False, str(e))
    ctx.app.last_typed = time.time()
    return Result(True, "Typed, sir.", {"chars": len(args["text"])})


@ability("ui_press", "press one key or shortcut in the window in front: a letter, a number, f1-f12, enter, tab, escape, arrows, page down/up, or control/alt/shift plus a key (press f, press control s)",
         required={"key": Text()}, examples=[("hit escape", 'ui_press(key="escape")'), ("press f", 'ui_press(key="f")')],
         patterns=[(r"(?:press|hit|push|tap|type) (?!(?:the |this |that |on the )?(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d{1,2}(?:st|nd|rd|th)?)\b)(?:the )?([a-z0-9+ ]{1,24}?)(?: key| button)?", lambda m: {"key": m[1].strip()}),   # 'tap the third link' is a choice, not a key
                   (r"(?:ctrl|control|alt|shift|win|windows)(?: plus|\+)? [a-z0-9]{1,10}", lambda m: {"key": m[0]})],   # 'alt left' said bare
         phrases={**{p: {"key": "back"} for p in ("go back", "back", "page back", "go back a page", "previous page", "click back", "click the back arrow", "press back")},
                  **{p: {"key": "forward"} for p in ("go forward", "forward", "page forward", "next page", "click forward")}})   # no model needed
def ui_press(args, ctx):
    key = args["key"].strip().lower()
    if parse_key(key) is None:
        return Result(False, f"I don't know a key called '{key}', sir. Try a letter, a number, enter, escape, the arrows, or control or alt with a key.")
    if key == "enter" and time.time() - getattr(ctx.app, "last_typed", 0) < TYPED_WINDOW_S and not ctx.confirmed:
        raise Ask("Shall I press Enter, sir? That may send what I typed.", pending=CONFIRM)
    try:
        ctx.os.ui_press(key)
    except Refused as e:
        return Result(False, str(e))
    return Result(True, f"Pressed {key}, sir.", {"key": key})


POLL_S, MAX_WAIT_S = 1.5, 40          # after sending, look at the window every POLL_S until the new text stops changing, for at most MAX_WAIT_S


def _new_lines(before, after, sent):
    """Lines that were not in the window before (and are not the message we sent): the reply."""
    old = {l.strip() for l in before.splitlines()}
    echo = sent.strip().lower()
    return "\n".join(l.strip() for l in after.splitlines() if l.strip() and l.strip() not in old and echo not in l.lower())


def _wait_for_answer(ctx, before, sent):
    """The new text once it is the same on two looks in a row (the app has stopped writing), else ''. Uses ui_read only: same rails as everything else."""
    last = ""
    for _ in range(int(MAX_WAIT_S / 1.5)):            # about MAX_WAIT_S seconds at the normal POLL_S
        time.sleep(POLL_S)
        try:
            now = _new_lines(before, ctx.os.ui_read(), sent)
        except Refused:
            return ""
        if now and now == last:
            return now
        last = now
    return ""


def _summarise(ctx, text, rule):
    if ctx.ai is None:
        return ""
    msgs = [{"role": "system", "content": "You are Jarvis, a calm British butler. " + rule + " Use ONLY the text below. Plain words, no lists. Never invent anything."},
            {"role": "user", "content": f"TEXT:\n{text[-3000:]}"}]
    try:
        return ctx.ai.complete(msgs, temperature=0.2, max_tokens=150).strip()
    except Exception:
        return ""


@ability("app_said", None, optional={"app": Name(kinds=("app", "site"))},
         patterns=[(r"(?:what|what did|what has|what does) (claude|chatgpt) (?:say|said|answer|answered|reply|replied|write|wrote)(?: back)?", lambda m: {"app": m[1]}),
                   (r"(?:read|tell me|give me|read out) (claude|chatgpt)(?: s)? (?:answer|reply|response)(?: back)?", lambda m: {"app": m[1]})])
def app_said(args, ctx):
    app = args.get("app") or "claude"
    if app not in ctx.catalog:
        return Result(False, f"I don't know {pretty(app)} on this computer, sir.")
    if not ctx.os.focus(app, ctx.kind(app)):
        return Result(False, f"I couldn't bring {pretty(app)} to the front, sir. Is it open?")
    try:
        text = ctx.os.ui_read()
    except Refused as e:
        return Result(False, str(e))
    if not text.strip():
        return Result(False, f"I can't read anything in {pretty(app)}, sir. Some apps don't share their text.")
    said = _summarise(ctx, text[-3000:], "This is the window of a chat app. Say in at most three short sentences what the most recent reply from the assistant (the lowest one) says. If there is no reply, say so.")
    return Result(bool(said), f"{pretty(app)} says: {said}" if said else "I need my thinking part to read that, sir.", {"app": app}, exact=True)


@ability("send_to_app", "write a message to someone or something in another app, for example ask Claude something or message in WhatsApp. app = where, text = exactly what to write",
         required={"app": Name(kinds=("app", "site")), "text": Text()}, examples=[("ask claude to summarise my notes", 'send_to_app(app="claude", text="summarise my notes")')])
def send_to_app(args, ctx):
    app = args["app"]
    if ctx.confirmed:                                                  # he said yes to "shall I send it": only the sending is left
        try:
            before = ctx.os.ui_read()
            ctx.os.ui_press("enter")
        except Refused as e:
            return Result(False, str(e))
        sent = f"Sent to {pretty(app)}, sir."
        new = _wait_for_answer(ctx, before, args["text"])
        if not new:
            return Result(True, f"{sent} It is still answering. Ask me what {pretty(app)} said, sir.", {"app": app}, exact=True)
        said = _summarise(ctx, new, "Say in at most three short sentences what the NEW text says (it is the reply that just arrived).")
        return Result(True, f"{sent} {pretty(app)} says: {said}" if said else f"{sent} It has answered. Ask me what {pretty(app)} said, sir.", {"app": app, "answered": bool(said)}, exact=True)
    if not ctx.os.focus(app, ctx.kind(app)):
        return Result(False, f"I couldn't bring {pretty(app)} to the front, sir. Is it open?")
    try:
        if not ctx.os.ui_focus_field():
            return Result(False, f"I can't find a text box in {pretty(app)}, sir.")
        ctx.os.ui_type(args["text"])
    except Refused as e:
        return Result(False, str(e))
    ctx.app.last_typed = time.time()
    raise Ask(f"I've typed it into {pretty(app)}. Shall I send it, sir?", pending=CONFIRM)
