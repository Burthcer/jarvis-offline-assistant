"""V4 draft -> confirm -> send (spec part 4). 'Reply to Rahul that I'm out, keep it short':
1. find Rahul on the screen (the V4 screen index; two Rahuls -> 'which one?'), click the chat, put the cursor in the message box;
2. write the message (the local model, in his own meaning; without the model, his own words), type it, and STOP. Enter is never pressed here.
3. His next sentence decides: 'send' presses Enter; 'cancel' wipes the box; 'make it shorter' / 'change it to ...' rewrites and waits again.
Rails: the draft cannot contain a newline or a key code; before sending or wiping, the same window must be in front and the cursor still in a text box."""
import re
import time
from dataclasses import dataclass

from ..registry import Ask, Result, Text, ability
from ..uia import Refused

SETTLE_S = .35            # the chat opens after the click
WAITING = {"draft": True}
STYLE = re.compile(r"\s*[,.;]?\s*(?:and\s+)?(?:keep it|make it|be)\s+(short|brief|polite|formal|casual|friendly|sweet|simple)\s*[.!]?\s*$", re.I)
VERBS = (r"(?:reply|respond|write back) to (?P<c>.+?) (?:that|saying|and say|to say|with) (?P<w>.+)",
         r"(?:message|text|ping|dm|whatsapp) (?P<c>.+?) (?:that|saying|and say|to say) (?P<w>.+)",
         r"(?:send|write) (?:a )?(?:message|text|reply) to (?P<c>.+?) (?:that|saying|and say|to say) (?P<w>.+)",
         r"(?:send|write) (?P<c>.+?) a (?:message|text) (?:that|saying|to say) (?P<w>.+)",
         r"tell (?!me\b|us\b|you\b)(?P<c>.+?) that (?P<w>.+)")


@dataclass
class Draft:
    contact: str
    what: str
    style: str = ""
    text: str = ""
    window: object = None
    stage: str = "contact"     # contact -> confirm


def route(text):
    t = re.sub(r"^(?:jarvis[,.]?\s+)?(?:please\s+)?", "", (text or "").strip(), flags=re.I).rstrip()
    style = STYLE.search(t)
    if style:
        t = t[:style.start()]
    for rx in VERBS:
        m = re.fullmatch(rx, t.rstrip(" .!?"), re.I)
        if m:
            contact, app = m["c"].strip(), None
            on = re.fullmatch(r"(.+?) (?:on|in|over) (whatsapp|discord|telegram|instagram|slack|teams|signal|messenger)", contact, re.I)
            if on:
                contact, app = on[1].strip(), on[2].lower()
            contact = re.sub(r"^(?:my|the)\s+", "", contact, flags=re.I)
            contact = re.sub(r"\s+(?:guy|person|chat)$", "", contact, flags=re.I)
            what = re.sub(r"\s+(?:on|in) (?:whatsapp|discord|telegram|slack|teams)$", "", m["w"].strip(), flags=re.I)
            args = {"contact": contact, "what": what}
            if style:
                args["style"] = style[1].lower()
            if app:
                args["app"] = app
            return [("message_draft", args)]
    return None


def safe(text):
    """One line of plain text: a newline would be Enter (= send), braces are key codes for the typing helper."""
    t = re.sub(r"[\r\n\t]+", " ", str(text or "")).replace("{", "(").replace("}", ")")
    t = re.sub(r"\s+", " ", t).strip().strip('"â€œâ€\'').strip()
    return t[:400]


def own_words(what):
    t = re.sub(r"^(?:that|saying|to say)\s+", "", what.strip().rstrip(" ,"), flags=re.I)
    t = t[:1].upper() + t[1:]
    return t if re.search(r"[.!?]$", t) else t + "."


RULES = ("You write one chat message that the user will send from their own phone or computer. Write it in the first person, as the user. "
         "Keep exactly their meaning; add nothing they did not say. One or two short sentences, plain text, no quotes, no emojis, no greeting or sign-off "
         "unless asked, never start with Yes or No unless they said it, never mention an assistant. Reply with the message only.")


def _model(ctx, user):
    if ctx.ai is None:
        return ""
    try:
        return safe(ctx.ai.complete([{"role": "system", "content": RULES}, {"role": "user", "content": user}], temperature=0.3, max_tokens=90))
    except Exception:
        return ""


def write(ctx, d):
    asked = f"To: {d.contact}\nWhat I want to say: {d.what}\nStyle: {d.style or 'natural'}"
    return _model(ctx, asked) or safe(own_words(d.what))


def compose(ctx):
    """The chat is open: cursor into the message box, type the draft, hold."""
    d = ctx.app.draft
    time.sleep(SETTLE_S)
    try:
        if not ctx.os.ui_focus_field():
            ctx.app.draft = None
            return Result(False, f"I opened {d.contact}, but I can't find the message box, sir.")
        d.text = write(ctx, d)
        _typed(ctx, d.text)
        d.window, d.stage = ctx.os.ui_window_id(), "confirm"
    except Refused as e:
        ctx.app.draft = None
        return Result(False, str(e))
    ctx.app.last_typed = time.time()
    raise Ask(f'I\'ve written to {d.contact}: "{d.text}" Shall I send it, sir?', pending=WAITING)


@ability("message_draft", None, required={"contact": Text(), "what": Text()}, optional={"style": Text(), "app": Text()})
def message_draft(args, ctx):
    from .screen import _screen_reply
    app = args.get("app")
    if app:
        if app not in ctx.catalog or not ctx.os.focus(app, ctx.kind(app)):
            return Result(False, f"I couldn't bring {app.title()} to the front, sir. Is it open?")
    ctx.app.draft = Draft(args["contact"], args["what"], args.get("style", ""))
    known = ctx.memory.alias_active(args["contact"].lower()) if ctx.memory else None
    try:
        found = ctx.os.ui_target(args["contact"], (known[0],) if known else (), False)
    except Refused as e:
        ctx.app.draft = None
        said = str(e)
        return Result(False, f"I can't see {args['contact']} on the screen, sir. Open the chat list and ask me again." if "can't find" in said else said)
    if found["status"] != "clicked":
        if found["status"] != "ambiguous":
            ctx.app.draft = None
        return _screen_reply(found)                      # 'Which one?' -> ui_pick continues the draft
    return compose(ctx)


SEND = re.compile(r"(?:(?:yes|yeah|yep|ok|okay|sure)\s*)?(?:(?:send|click send|press send|hit send)(?:\s+(?:it|that|the message|now))?|go ahead|do it)?", re.I)
CANCEL = re.compile(r"(?:no|nope|cancel(?: it| that)?|delete it|clear(?: it| that| the box)?|don'?t send(?: it)?|do not send(?: it)?|discard(?: it)?|scrap it|never mind|nevermind|forget it)", re.I)
REWRITE = re.compile(r"make it (shorter|longer|more polite|politer|more formal|more casual|friendlier|more friendly|nicer|simpler)", re.I)
REPLACE = re.compile(r"(?:change (?:it|that|the message) to|make it say|instead say|say) (.+?)(?:\s+instead)?", re.I)
READ = re.compile(r"(?:read it(?: back)?|what did you (?:write|type)|what does it say)", re.I)


def answer_kind(said):
    """('send'|'cancel'|'rewrite'|'replace'|'read', detail) for his answer to 'shall I send it?', or None when it is a new command."""
    t = re.sub(r"[^\w' ]", " ", said or "").strip()
    t = re.sub(r"\s+", " ", re.sub(r"\b(?:please|sir|jarvis)\b", "", t, flags=re.I)).strip()
    if not t:
        return None
    if SEND.fullmatch(t):
        return "send", ""
    if CANCEL.fullmatch(t):
        return "cancel", ""
    if READ.fullmatch(t):
        return "read", ""
    m = REWRITE.fullmatch(t)
    if m:
        return "rewrite", m[1].lower()
    m = REPLACE.fullmatch((said or "").strip().rstrip(" .!?"))
    if m:
        return "replace", m[1]
    return None


def _clear(ctx):
    if not ctx.os.ui_clear_field():
        raise Refused("I couldn't empty the message box, sir. Please clear it yourself. Nothing was sent.")


def _typed(ctx, text):
    """Type it, then read the box back when the app shares it: never ask 'shall I send it?' about text that is not there."""
    ctx.os.ui_type(text)
    now = ctx.os.ui_field_text()
    if now is not None and text not in now:
        raise Refused("I typed it, but the message box doesn't show it, sir. Please check the box. Nothing was sent.")


@ability("draft_answer", None, required={"said": Text()})
def draft_answer(args, ctx):
    """Reached only from 'shall I send it?' (app._answer_pending)."""
    d, (kind, detail) = ctx.app.draft, answer_kind(args["said"])
    try:
        if not ctx.os.ui_draft_ok(d.window):
            ctx.app.draft = None
            return Result(False, "The window or the cursor moved, sir, so I left the message as it is. Nothing was sent.")
        if kind == "send":
            ctx.app.draft = None
            ctx.os.ui_press("enter")
            return Result(True, "Sent, sir.", {"sent": True})
        if kind == "cancel":
            ctx.app.draft = None
            _clear(ctx)
            return Result(True, "Cleared, sir. Nothing was sent.")
        if kind == "read":
            raise Ask(f'It says: "{d.text}" Shall I send it, sir?', pending=WAITING)
        new = safe(own_words(detail)) if kind == "replace" else _model(ctx, f"Rewrite this message {detail}, same meaning: {d.text}")
        if not new:
            raise Ask(f"I need my thinking part to rewrite it, sir. It still says: \"{d.text}\". Shall I send it?", pending=WAITING)
        _clear(ctx)
        _typed(ctx, new)
        d.text = new
    except Refused as e:
        ctx.app.draft = None
        return Result(False, str(e))
    raise Ask(f'Now it says: "{d.text}" Shall I send it, sir?', pending=WAITING)
