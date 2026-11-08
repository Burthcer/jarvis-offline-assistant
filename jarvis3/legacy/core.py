"""The single command entry point: handle(text, store) -> reply. Everything (voice, UI, later brains) calls this."""
import re
from datetime import datetime, timedelta

from .actions import act
from .store import tokens
from .timeparse import fmt, parse_when

I = re.I
YES = ("yes", "yes sir", "yeah", "yep", "confirm", "do it", "go ahead", "yes please", "sure")
NO = ("no", "no sir", "nope", "cancel", "stop", "never mind", "nevermind", "don't")
# "remind me ..." with the polite / spoken ways of saying it in front
REMIND = (r"(?:(?:(?:can|could|would|will) you (?:please )?|i need you to |i want you to |you should )?"
          r"(?:remind me|add (?:a )?reminder|set (?:a )?reminder)|don't let me forget)[,:]?(?: to| about| that| of| for)?[,:]?\s+(.+)")


CHAT = [
    (r"(?:(?:hey |ok |okay )?jarvis,? )?(?:can|could) you (?:hear|understand) me(?: (?:now|clearly))?", "Loud and clear, sir."),
    (r"(?:are you (?:there|awake|listening|working)|you there|jarvis you there)", "Always, sir."),
    (r"(?:hello|hi|hey|hey there|good (?:morning|afternoon|evening))(?: jarvis)?", "Hello, sir. How may I help?"),
    (r"(?:how are you|how are you doing|how's it going|how do you do)(?: today)?", "Very well, sir, thank you for asking."),
    (r"(?:thanks|thank you|thank you (?:so much|very much)|cheers|nice one|well done|good job)", "My pleasure, sir."),
    (r"(?:who are you|what are you|what's your name|what is your name|introduce yourself)", "I'm Jarvis, sir. I run entirely on this laptop, and nothing leaves it."),
    (r"(?:good night|goodnight|goodbye|bye|see you(?: later)?)", "Good night, sir." ),
    (r"(?:never ?mind|forget it|cancel that|ignore that)", "Of course, sir."),
]


def _lines(rows, now):
    return "\n".join(f"  #{r['id']} {r['text']} ({fmt(datetime.fromisoformat(r['due']), now)})" for r in rows)


def _list(title, rows, empty, now):
    return f"{title}, sir:\n{_lines(rows, now)}" if rows else empty


# Jarvis's clarifying questions -> what the short answer completes ("Up or down?" + "up" = "volume up")
ASK = {"Up or down, sir?": "volume ", "Search for what, sir?": "search for ", "How long should the timer run, sir?": "set a timer for ",
       "Snooze for how long, sir?": "snooze for ", "Remind you of what, sir?": "remind me to ",
       "Open Wispr Flow or Wisperno Pro, sir?": "open ", "Close Wispr Flow or Wisperno Pro, sir?": "close "}


UNKNOWN = ["I heard \"{}\", sir, but I'm afraid I can't do that yet.", "I'm afraid \"{}\" is beyond me for now, sir.",
           "I'm afraid I don't know how to handle \"{}\" yet, sir."]
_last_unknown = [-1]


def is_unknown(reply):
    return "afraid" in reply and '"' in reply


def _unknown(t):
    """Say what was heard (so a mishearing is obvious) and don't repeat the same sentence twice in a row."""
    _last_unknown[0] = (_last_unknown[0] + 1) % len(UNKNOWN)
    return UNKNOWN[_last_unknown[0]].format(t.strip(" .,!?")[:60])


def handle(text, store, now=None):
    reply = _handle(text, store, now)
    if reply in ASK and not store.pending:
        store.pending = ("combine", ASK[reply])
    return reply


def _handle(text, store, now=None):
    now = now or datetime.now()
    t = re.sub(r"^(?:(?:hey|ok|okay)[,.]?\s+)?jarvis[,.!?]?\s*", "", text.strip(), flags=I)
    t = re.sub(r"^(?:please|kindly)\s+|[,.]?\s+(?:please|sir|thanks|thank you)\s*[.!?]*$", "", t.strip(), flags=I).strip()
    l = t.lower().rstrip(".?! ")
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if not l and text.strip():  # just "Hey Jarvis" (typed, or the wake word arriving as text)
        return "At your service, sir."

    if store.pending:  # answer to a question Jarvis just asked
        (kind, row), store.pending = store.pending, None
        if kind == "combine":  # answer to "Up or down?" / "Search for what?" / "How long?"
            if l in NO:
                return "Very well, sir."
            if len(l.split()) <= (12 if row.startswith("remind") else 5) and not l.startswith(row.split()[0] + " "):  # "search cats" is a whole new command, not an answer
                return handle(row + t, store, now)
        elif kind == "when":  # "When would you like to be reminded?" -> just the time is enough ("5 pm", "tomorrow morning")
            if l in NO:
                return "Very well, sir."
            left, due = parse_when(t, now)
            if due is not None and len(left.split()) <= 1 and not re.match(REMIND, t, I):
                if due < now - timedelta(minutes=1):
                    store.pending = ("when", row)
                    return f"I'm afraid that time has already passed, sir. When would you like to be reminded about '{row}'?"
                r, merged = store.add(row[0].upper() + row[1:], due)
                return f"{'Updated' if merged else 'Noted'}, sir: '{r['text']}' {fmt(due, now)}."
        elif l in YES:
            if kind == "all":
                return f"Cleared everything, sir ({store.clear()} items)."
            store.delete(row["id"])
            return f"Deleted '{row['text']}', sir."
        elif l in NO:
            return "Cancelled, sir."
        # anything else: drop the question and treat it as a normal command

    if re.fullmatch(r"(?:(?:can|could|would|will) you (?:please )?)?(?:remind me|set a reminder|add a reminder|make a reminder)", l):
        return "Remind you of what, sir?"
    m = re.match(REMIND, t, I)
    if m:
        what, due = parse_when(m[1], now)
        if not what:
            return "Remind you of what, sir?"
        if re.search(r"\bevery\b", m[1], I):
            return "I'm afraid repeating reminders aren't supported yet, sir. Could you give me a single date and time?"
        if due is None:
            store.pending = ("when", what)
            return f"When would you like to be reminded about '{what}', sir?"
        if due < now - timedelta(minutes=1):
            store.pending = ("when", what)
            return f"I'm afraid that time has already passed, sir. When would you like to be reminded about '{what}'?"
        row, merged = store.add(what[0].upper() + what[1:], due)
        return f"{'Updated' if merged else 'Noted'}, sir: '{row['text']}' {fmt(due, now)}."

    m = re.match(r"(?:remember|make a note|note)[:,]?(?: that)?\s+(.+)", t, I)
    if m:
        old = [r for r in store.notes(m[1]) if tokens(m[1]) < set(r["key"].split())]
        if old:  # "remember my bike lock code" adds nothing new: never let it wipe "my bike lock code is 4512"; answer instead
            return "\n".join(r["text"] for r in old)
        row, merged = store.add(m[1], None, kind="note")
        return f"{'Updated' if merged else 'Remembered'}, sir."

    m = re.match(r"(?:what do you remember about|do you remember|recall)\s+(.+)", l, I)
    if m:
        notes = store.notes(m[1])
        return "\n".join(r["text"] for r in notes) if notes else "I don't have anything on that, sir."

    m = re.match(r"(?:rename|edit|update)\s+(?:the |my )?(?:reminder\s+)?(?:(?:of|for|about|called|named)\s+)?(.+?)\s+to\s+(?:say\s+)?(.+)", t, I)
    if m:
        row = store.find(m[1])
        if not row:
            return "I'm sorry, sir, I couldn't find that."
        new, due = parse_when(m[2], now)
        new = re.sub(r"\s+(?:for|on|at|by|in)$", "", (new or "").strip(" .,!?"), flags=I)
        if new:
            row = store.rename(row["id"], new[0].upper() + new[1:])
        if due is not None:
            store.set_due(row["id"], due)
        return f"{'Updated' if new else 'Moved'}, sir: '{row['text']}'" + (f" {fmt(due, now)}." if due is not None else ".")

    reply = act(l, store, now)  # PC actions (M2): only allowlisted things ever run
    if reply:
        return reply

    m = re.match(r"(?:change|move|reschedule|postpone|push)\s+(?:the |my )?(.+?)\s+(?:to|until|till|for)\s+(.+)", l, I)
    if m:
        row = store.find(m[1])
        if not row:
            return "I'm sorry, sir, I couldn't find that."
        _, due = parse_when(m[2], now)
        if due is None or due < now - timedelta(minutes=1):
            return "To when, sir? A date or time in the future, if you would."
        store.set_due(row["id"], due)
        return f"Moved, sir: '{row['text']}' {fmt(due, now)}."

    m = re.match(r"snooze(?: it| that| the reminder)?(?: for| by)?\s*(.*)", l, I)
    if m:
        row = store.last_fired()
        if not row:
            return "Nothing to snooze, sir."
        _, due = parse_when(m[1] if re.match(r"in\b", m[1]) else "in " + (m[1] or "10 minutes"), now)
        if due is None:
            return "Snooze for how long, sir?"
        store.set_due(row["id"], due)
        return f"Snoozed, sir: '{row['text']}' {fmt(due, now)}."

    m = re.match(r"(?:i(?:'m| am| have|'ve)?\s+)?(?:done|finished|completed?)(?: with)?(?: the| my)?\s+(.+)", l, I) \
        or re.match(r"mark\s+(?:the |my )?(.+?)\s+(?:as\s+)?(?:done|finished|complete[d]?)$", l, I) \
        or re.match(r"mark (?:as )?(?:done|finished|completed?)\s+(.+)", l, I)
    if m:
        row = store.find(m[1])
        if not row:
            return "I'm sorry, sir, I couldn't find that."
        store.set_status(row["id"], "done")
        return f"Marked done, sir: '{row['text']}'."

    m = re.match(r"(?:delete|clear|remove|cancel|get rid of)\s+(?:all\s+)?(?:of\s+)?(?:the\s+|my\s+)*(?:(\w+)'s\s+)?reminders?(?:\s+(?:for|on|from|of|that are|due)\s+(.+))?$", l, I)
    if m and (m[1] or m[2]):  # "cancel all the reminders for tomorrow", "delete Friday's reminders"
        word = m[1] or m[2]
        _, d = parse_when(word if re.search(r"\b(?:today|tonight|tomorrow)\b", word) else "on " + word, now)
        if d:
            day = datetime(d.year, d.month, d.day)
            rows = [r for r in store.between(day, day + timedelta(days=1)) if r["kind"] == "reminder"]
            name = word if re.search(r"\b(?:today|tonight|tomorrow)\b", word) else day.strftime("%a %d %b")
            if not rows:
                return f"You have no reminders for {name}, sir."
            for r in rows:
                store.delete(r["id"])
            return f"Cancelled {len(rows)} reminder{'s' if len(rows) > 1 else ''} for {name}, sir: " + " and ".join(r["text"] for r in rows) + "."
    if re.fullmatch(r"(?:delete|clear|remove|cancel|get rid of)\s+(?:all\s+)?(?:of\s+)?(?:the\s+|my\s+)*reminders", l, I):
        rows = store.upcoming(now, 1000)
        if not rows:
            return "You have no reminders, sir."
        for r in rows:
            store.delete(r["id"])
        return f"Cancelled all {len(rows)} reminders, sir."

    if re.match(r"(?:delete|clear|remove|cancel)\s+(?:all|everything)(?:\s+(?:my\s+)?(?:reminders|items|notes))?$", l, I):
        n = store.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        if not n:
            return "There's nothing to clear, sir."
        store.pending = ("all", None)
        return f"Delete all {n} items, sir? Please say yes to confirm."

    m = re.match(r"(?:delete|cancel|remove)(?: my| the)?(?: reminder)?\s+(.+)", l, I)
    if m:
        row = store.find(m[1])
        if not row:
            return "I'm sorry, sir, I couldn't find that."
        store.delete(row["id"])
        return f"Cancelled '{row['text']}', sir."

    if re.search(r"\bmiss(ed)?\b|\byesterday\b|\boverdue\b|\bwhat (?:did|have) i forg[eo]t", l):
        start = midnight - timedelta(days=1) if "yesterday" in l else datetime(2000, 1, 1)
        return _list("You missed these", store.between(start, now), "Nothing missed, sir.", now)

    if re.search(r"\bthis week\b", l):
        return _list("This week", store.between(midnight, midnight + timedelta(days=7)), "Nothing on this week, sir.", now)

    if "tomorrow" in l and "today" not in l:
        return _list("Tomorrow", store.between(midnight + timedelta(days=1), midnight + timedelta(days=2)), "Nothing on for tomorrow, sir.", now)

    if re.search(r"\btoday\b|\btonight\b|\bwe got\b|\bagenda\b|\bschedule\b", l):
        return _list("Today", store.between(midnight, midnight + timedelta(days=1)), "Nothing on for today, sir.", now)

    if re.match(r"(?:what|which|anything|any|do i have|do we have|am i|show|tell|read)\b", l, I):
        _, d = parse_when(l, now)  # "what's on friday", "what do I have on 23rd november"
        if d:
            day = datetime(d.year, d.month, d.day)
            return _list(day.strftime("%a %d %b"), store.between(day, day + timedelta(days=1)), f"Nothing on {day.strftime('%a %d %b')}, sir.", now)

    if re.search(r"\b(upcoming|coming up|list|reminders|what next|what's next)\b", l) and not re.search(r"\b(add|put|to my)\b", l):
        return _list("Coming up", store.upcoming(now), "Nothing coming up, sir.", now)

    if re.match(r"(?:what|which|where|when|who|how|tell|give|read|show|say)\b", l, I) and (notes := store.notes(l)):  # a question about a saved note
        return "\n".join(r["text"] for r in notes)

    for pat, answer in CHAT:  # a few stock lines until the local LLM (M5) can chat properly
        if re.fullmatch(pat, l):
            return answer
    return _unknown(t)


def announce_due(store, now=None, fired=None):
    """Spoken-reminder hook: call every few seconds; returns sentences to say. `fired`, if given, also collects the rows."""
    now = now or datetime.now()
    out = []
    for r in store.due_now(now):
        store.set_status(r["id"], "fired")
        if fired is not None:
            fired.append(r)
        out.append(f"Sir, your {r['text']} timer is up." if r["kind"] == "timer" else f"Sir, reminder: {r['text']}.")
        if r['kind']=='reminder': store.schedule_next(r,now)
    return out
