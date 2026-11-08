"""reminder_add / list / change / cancel, note_save / recall / forget, clock. All live in V1's Store (items table), so the old window and alerts keep working."""
import re
from datetime import datetime, timedelta

from jarvis.store import tokens
from jarvis.timeparse import fmt, parse_when

from ..registry import Ask, Bool, Choice, Result, Text, When, ability


def day_bounds(day, now):
    d = day.lower().strip()
    base = {"today": 0, "tomorrow": 1, "yesterday": -1}.get(d)
    if base is not None:
        start = (now + timedelta(days=base)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        _, due = parse_when(day, now)
        if due is None:
            raise Ask("Which day, sir?")
        start = due.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def find_reminder(store, ref):
    t = tokens(ref)
    for r in store.db.execute("SELECT * FROM items WHERE kind='reminder' AND status!='done' ORDER BY id"):
        k = set(r["key"].split())
        if t and (t <= k or k <= t):
            return r


def lines(rows, now):
    return "\n".join(f"  #{r['id']} {r['text']} ({fmt(datetime.fromisoformat(r['due']), now)})" for r in rows)


# ---------- reminders ----------
@ability("reminder_add", "new reminder; text in the user's own words (keep their wording), when = their time words",
         required={"text": Text(), "when": When()},
         examples=[("remind me on friday at 3 that the rent is due", 'reminder_add(text="the rent is due", when="friday at 3")')])
def reminder_add(args, ctx):
    row, merged = ctx.store.add(args["text"], args["when"], "reminder")
    return Result(True, f"{'Updated' if merged else 'Noted'}, sir: '{row['text']}' {fmt(args['when'], ctx.now)}.", {"id": row["id"], "due": args["when"]},
                  undo=None if merged else lambda: (ctx.store.delete(row["id"]), Result(True, "Reminder removed, sir."))[1])


@ability("reminder_list", "what's on the list. day = a day word if they gave one. count = true if they asked how many",
         optional={"day": Text(), "count": Bool()}, examples=[("what's on my list for friday", 'reminder_list(day="friday")')])
def reminder_list(args, ctx):
    day = args.get("day")
    if day:
        a, b = day_bounds(day, ctx.now)
        rows, label = ctx.store.between(a, b), f"For {day}"
        empty = f"Nothing for {day}, sir."
    else:
        rows, label, empty = ctx.store.upcoming(ctx.now), "Coming up", "Nothing coming up, sir."
    if args.get("count"):
        return Result(True, f"You have {len(rows)} reminder{'s' if len(rows) != 1 else ''}{' for ' + day if day else ''}, sir." if rows else empty, {"count": len(rows)}, exact=True)
    return Result(True, f"{label}, sir:\n{lines(rows, ctx.now)}" if rows else empty, {"count": len(rows)}, exact=True)


@ability("reminder_change", "change an existing reminder: item = words of the old one, text = the new words, when = a new time",
         required={"item": Text()}, optional={"text": Text(), "when": When()},
         examples=[("change the dentist reminder to the doctor", 'reminder_change(item="dentist", text="the doctor")')])
def reminder_change(args, ctx):
    r = find_reminder(ctx.store, args["item"])
    if not r:
        return Result(False, "I can't find a reminder like that, sir.")
    if "text" not in args and "when" not in args:
        raise Ask("What should it say, or when, sir?")
    old = dict(r)
    if "text" in args:
        ctx.store.rename(r["id"], args["text"])
    if "when" in args:
        ctx.store.set_due(r["id"], args["when"])
    new = ctx.store.get(r["id"])

    def undo():
        ctx.store.rename(old["id"], old["text"])
        ctx.store.set_due(old["id"], datetime.fromisoformat(old["due"]))
        return Result(True, "Changed back, sir.")
    return Result(True, f"Changed, sir: '{new['text']}' {fmt(datetime.fromisoformat(new['due']), ctx.now)}.", {"id": r["id"]}, undo=undo)


@ability("reminder_cancel", "cancel a reminder (item = its words), or every reminder on a day (day)", optional={"item": Text(), "day": Text()},
         examples=[("wipe sunday's reminders", 'reminder_cancel(day="sunday")')])
def reminder_cancel(args, ctx):
    if args.get("item"):
        r = find_reminder(ctx.store, args["item"])
        rows = [r] if r else []
    elif args.get("day"):
        rows = ctx.store.between(*day_bounds(args["day"], ctx.now))
    else:
        raise Ask("Which reminder, sir?")
    if not rows:
        return Result(False, "I can't find such a reminder, sir.")
    saved = [(r["text"], datetime.fromisoformat(r["due"])) for r in rows]
    for r in rows:
        ctx.store.delete(r["id"])
    return Result(True, f"Cancelled, sir: {rows[0]['text']}." if len(rows) == 1 else f"Cancelled {len(rows)} reminders, sir.", {"count": len(rows)},
                  undo=lambda: ([ctx.store.add(t, d, "reminder") for t, d in saved], Result(True, "Reminders restored, sir."))[1])


# ---------- notes ----------
def spoken_symbols(text):
    """'jane dot doe at the rate example dot edu' -> 'jane.doe@example.edu' (only around 'at the rate')."""
    w = text.split()
    i = next((k for k in range(1, len(w) - 3) if [x.lower() for x in w[k:k + 3]] == ["at", "the", "rate"]), None)
    if i is None:
        return text
    j = i - 1
    while j >= 2 and w[j - 1].lower() == "dot":                      # name dot name dot name
        j -= 2
    end = i + 4
    while end + 1 < len(w) and w[end].lower() == "dot":
        end += 2
    local = ".".join(x for x in w[j:i] if x.lower() != "dot")
    domain = ".".join(x for x in w[i + 3:end] if x.lower() != "dot")
    return " ".join(w[:j] + [local + "@" + domain] + w[end:])


@ability("note_save", "remember a fact: text = the WHOLE fact as the user said it, including what it is about ('my wifi password is purple tiger'). 'at the rate' = @, 'dot' = .", required={"text": Text()}, examples=[("my bike number is 1234", 'note_save(text="my bike number is 1234")')])
def note_save(args, ctx):
    text = spoken_symbols(args["text"])
    row, merged = ctx.store.add(text, None, "note")
    return Result(True, f"{'Updated' if merged else 'Noted'}, sir: {row['text']}.", {"id": row["id"], 'copy_text': fact_value(row['text'])},
                  undo=None if merged else lambda: (ctx.store.delete(row["id"]), Result(True, "Note removed, sir."))[1])


@ability("note_recall", "say a saved fact back", required={"query": Text()}, examples=[("what was my bike number", 'note_recall(query="bike number")')])
def note_recall(args, ctx):
    rows = ctx.store.notes(args["query"])
    if not rows:
        return Result(True, "I have no note about that, sir.", {"count": 0, 'copy_text': ''}, exact=True)
    return Result(True, "; ".join(r["text"] for r in rows[:3]) + ", sir.", {"count": len(rows), 'copy_text': '\n'.join(fact_value(r['text']) for r in rows[:3])}, exact=True)


def fact_value(text):
    if re.search(r'password|secret|\bpin\b', re.sub(r'\b(?:postal )?pin\s*code\b', 'postal code', text, flags=re.I), re.I):
        return ''
    email = re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', text)
    if email:
        return email[0].rstrip('.')
    match = re.fullmatch(r'my .+? (?:is|are) (.+)', text, re.I)
    return match[1] if match else text


@ability('note_copy', 'copy one saved fact to the clipboard; query is its heading, omit only for copy that', optional={'query': Text()})
def note_copy(args, ctx):
    if args.get('query'):
        notes = ctx.store.notes(args['query'])
        if len(notes) != 1:
            return Result(False, 'Please choose one saved fact to copy, sir.', exact=True)
        value = fact_value(notes[0]['text'])
    else:
        value = getattr(ctx.app, 'copy_text', '')
    if not value:
        return Result(False, 'Please choose a non-secret saved fact to copy, sir.', exact=True)
    ok = ctx.os.clipboard_write(value)
    return Result(ok, 'Copied to the clipboard, sir.' if ok else 'I could not verify the clipboard copy, sir. Please try again.', exact=True)


@ability('note_open', 'open a website saved in a personal fact', required={'query': Text()})
def note_open(args, ctx):
    from ..knowledge import website_url
    rows = ctx.store.notes(args['query'])
    if len(rows) != 1:
        return Result(False, 'Please choose one saved website, sir.', exact=True)
    value = fact_value(rows[0]['text']).strip()
    url = website_url(value)
    if not url:
        return Result(False, 'That saved fact is not a website address, sir.', exact=True)
    ok = ctx.os.url('edge', url)
    return Result(ok, 'Opening your saved website, sir.' if ok else 'I could not open that website, sir.', exact=True)


@ability("note_forget", "delete a saved fact", required={"query": Text()}, examples=[("drop my bike number", 'note_forget(query="bike number")')])
def note_forget(args, ctx):
    rows = ctx.store.notes(args["query"])
    if not rows:
        return Result(False, "I have no note about that, sir.")
    if len(rows)!=1:return Result(False,'Please choose one saved fact to forget, sir.',exact=True)
    r = rows[0]
    ctx.store.delete(r["id"])
    return Result(True, f"Forgotten, sir: {r['text']}.", {"id": r["id"]}, undo=lambda: (ctx.store.add(r["text"], None, "note"), Result(True, "Note restored, sir."))[1])


# ---------- clock ----------
@ability("clock", "the real time, date or weekday (day = tomorrow, friday... if they asked about another day)",
         required={"what": Choice("time", "date", "day")}, optional={"day": Text()},
         examples=[("which day is it today", 'clock(what="day")')])
def clock(args, ctx):
    when, day = ctx.now, args.get("day")
    if day:
        when = day_bounds(day, ctx.now)[0]
    word = f"{day}" if day else "today"
    if args["what"] == "time":
        return Result(True, f"It's {ctx.now.strftime('%I:%M %p').lstrip('0')}, sir.", {"time": ctx.now.strftime("%H:%M")}, exact=True)
    if args["what"] == "date":
        return Result(True, f"{'Today' if not day else day.capitalize()} is {when.strftime('%A')}, {when.day} {when.strftime('%B %Y')}, sir.", {"date": when.date().isoformat()}, exact=True)
    return Result(True, f"{'Today' if not day else day.capitalize()} is {when.strftime('%A')}, sir.", {"day": when.strftime("%A")}, exact=True)
