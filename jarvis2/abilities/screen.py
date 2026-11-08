"""Operating other apps and reading the screen, through UI Automation (jarvis2/uia.py, where the rails live). Nothing irreversible happens without a spoken yes:
sending a message, clicking a button called Send/Pay/Delete..., pressing Enter right after typing. The yes is the `confirmed` flag the app sets when he answers a question."""
import time

from ..registry import Ask, Choice, Name, Result, Text, ability
from ..uia import KEYS, Refused, risky
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
    try:
        done = ctx.os.ui_click(label)
    except Refused as e:
        return Result(False, str(e))
    return Result(True, f"Clicked {done}, sir.", {"label": done})


@ability("ui_type", "type words into the text box that has the cursor in the window in front. Does NOT press Enter", required={"text": Text()},
         examples=[("type hello there", 'ui_type(text="hello there")')])
def ui_type(args, ctx):
    try:
        ctx.os.ui_type(args["text"])
    except Refused as e:
        return Result(False, str(e))
    ctx.app.last_typed = time.time()
    return Result(True, "Typed, sir.", {"chars": len(args["text"])})


@ability("ui_press", "press one key in the window in front: enter, tab, escape, up, down, left, right, page down, page up, copy, paste, select all, find, new tab, refresh, back",
         required={"key": Choice(*KEYS)}, examples=[("hit escape", 'ui_press(key="escape")')])
def ui_press(args, ctx):
    key = args["key"]
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
