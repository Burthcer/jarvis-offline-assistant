"""Local event/deadline and task records. Dates are evidence, never model guesses."""
import json
import re
from datetime import datetime, timedelta

from jarvis3.legacy.timeparse import parse_when

SCHEMA = """
CREATE TABLE IF NOT EXISTS commitments(
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, happens TEXT, deadline TEXT,
 source TEXT NOT NULL DEFAULT 'you', status TEXT NOT NULL DEFAULT 'active', kind TEXT NOT NULL DEFAULT 'event',
 reminders TEXT NOT NULL DEFAULT '[]', updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(
 id INTEGER PRIMARY KEY, request TEXT NOT NULL, steps TEXT NOT NULL,
 cursor INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'ready',
 results TEXT NOT NULL DEFAULT '[]', updated TEXT NOT NULL);
"""


def setup(memory):
    with memory.lock:
        memory.db.executescript(SCHEMA)
        if 'kind' not in [c[1] for c in memory.db.execute('PRAGMA table_info(commitments)')]:
            memory.db.execute("ALTER TABLE commitments ADD COLUMN kind TEXT NOT NULL DEFAULT 'event'")
            memory.db.commit()


def rows(memory, table):
    setup(memory)
    assert table in ('commitments', 'jobs')
    with memory.lock:
        cur = memory.db.execute(f'SELECT * FROM {table} ORDER BY id DESC')
        keys = [c[0] for c in cur.description]
        return [dict(zip(keys, r)) for r in cur.fetchall()]


def find_event(memory, title):
    items = [r for r in rows(memory, 'commitments') if r['status'] == 'active']
    if str(title).isdigit():
        return next((r for r in items if r['id'] == int(title)), None)
    exact = [r for r in items if r['title'].casefold() == title.casefold()]
    if exact:
        return exact[0]
    matches = [r for r in items if title.casefold() in r['title'].casefold()]
    return matches[0] if len(matches) == 1 else None


def date(text, now):
    """Refuse ambiguous numeric dates, impossible dates and explicit past years.
    Legacy parser rolls past month/day to next year; explicit years must agree.
    """
    if re.search(r'\b\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?\b', text):
        return None
    year = re.search(r'\b(20\d{2})\b', text)
    base = datetime(int(year[1]), 1, 1) if year else now
    _, due = parse_when(text, base)
    if due and year and due.year != int(year[1]):
        return None
    return due if due and due > now else None


def _reminder(store, title, due):
    # These must have their own identities: Store.add's fuzzy merge could merge
    # the advance warning, deadline and event into one reminder.
    now = datetime.now().isoformat()
    from jarvis3.legacy.store import tokens
    with store.lock:
        cur = store.db.execute("INSERT INTO items(kind,text,key,due,created,updated) VALUES('reminder',?,?,?,?,?)",
                               (title, ' '.join(sorted(tokens(title))), due.isoformat(), now, now))
        store.db.commit()
        return cur.lastrowid


def save_event(memory, store, title, now, happens=None, deadline=None, source='you'):
    setup(memory)
    old = find_event(memory, title)
    kind = 'exam' if re.search(r'\b(exams?|tests?)\b', title, re.I) else 'event'
    happens = happens or (datetime.fromisoformat(old['happens']) if old and old['happens'] else None)
    deadline = deadline or (datetime.fromisoformat(old['deadline']) if old and old['deadline'] else None)
    if happens and deadline and deadline > happens:
        raise ValueError('Registration closes after the event. Please check the dates, sir.')
    if old:
        for rid in json.loads(old['reminders']):
            store.delete(rid)
    ids = []
    if deadline:
        before = deadline - timedelta(days=1)
        if before > now:
            ids.append(_reminder(store, f'Register for {title}: deadline tomorrow', before))
        if deadline > now:
            ids.append(_reminder(store, f'Registration deadline for {title}', deadline))
    elif kind != 'exam':
        # Honest follow-up, not an invented registration deadline.
        check = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        if happens:
            check = min(check, happens - timedelta(days=1))
        if check <= now:
            check = now + timedelta(minutes=5)
        ids.append(_reminder(store, f'Check registration deadline for {title} (not known yet)', check))
    if happens and happens > now:
        if kind == 'exam' and happens - timedelta(days=1) > now:
            ids.append(_reminder(store, f'Prepare for {title}: starts tomorrow', happens - timedelta(days=1)))
        ids.append(_reminder(store, f'{title} starts', happens))
    values = (title, happens and happens.isoformat(), deadline and deadline.isoformat(), source, json.dumps(ids), now.isoformat(), kind)
    if old:
        memory._w('UPDATE commitments SET title=?,happens=?,deadline=?,source=?,reminders=?,updated=?,kind=? WHERE id=?', *values, old['id'])
        return old['id']
    return memory._w('INSERT INTO commitments(title,happens,deadline,source,reminders,updated,kind) VALUES(?,?,?,?,?,?,?)', *values).lastrowid


def cancel_event(memory, store, ref, now):
    event = find_event(memory, ref)
    if not event:
        return False
    for rid in json.loads(event['reminders']):
        store.delete(rid)
    memory._w("UPDATE commitments SET status='cancelled',updated=? WHERE id=?", now.isoformat(), event['id'])
    return True


def screen_deadline(text, now):
    """Only a labelled date. Multiple different deadlines require clarification."""
    dates = set()
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.search(r'\b(registration|register|applications?|apply|sign.?up|rsvp)\b', line, re.I) and re.search(r'\b(deadline|closes?|ends?|last date|by|until)\b', line, re.I):
            # An opening date earlier in the same line is not the deadline.
            labels = list(re.finditer(r'\b(deadline|closes?|ends?|last date|by|until)\b', line, re.I))
            dated = line[labels[-1].end():] if labels else line
            due = date(dated, now)
            if not due and i + 1 < len(lines) and len(line) < 80:
                due = date(dated + ' ' + lines[i + 1], now)
            if due:
                dates.add(due)
    return next(iter(dates)) if len(dates) == 1 else None


def route(text):
    """Preserve original punctuation, email addresses and date words."""
    t = text.strip().rstrip('.!?')
    patterns = [
        (r'remind me when to register for (.+)', 'event_track', 'text'),
        (r'(?:i have|my) (?:an? |my )?((?:.+? )?exams? .+)', 'event_track', 'text'),
        (r'(?:track|keep track of|i want to (?:go to|attend)|i am going to|i\x27m going to) (.+)', 'event_track', 'text'),
        (r'(?:registration|applications?) for (.+?) (?:closes?|ends?|is due)(?: on)? (.+)', 'event_deadline', None),
        (r'(?:the )?(?:registration )?deadline for (.+?) is (.+)', 'event_deadline', None),
        (r'(?:check|read|find)(?: the)? (?:registration )?deadline(?: for (.+?))? (?:on|from) (?:this page|the screen|this screen)', 'event_read', 'title'),
        (r'(?:cancel|forget|remove) (?:event|commitment) #?(\d+)', 'event_cancel', 'title'),
        (r'(?:plan|handle|take care of)(?: this)?(?: for me)?\s*[: ,]\s*(.+)', 'goal_plan', 'text'),
        (r'(?:do|execute|run|continue|resume) (?:my |the )?(?:plan|task)(?: #?(\d+))?', 'goal_run', 'id'),
        (r'(?:cancel|stop) (?:my |the )?(?:plan|task)(?: #?(\d+))?', 'goal_cancel', 'id'),
    ]
    for pattern, ability, key in patterns:
        m = re.fullmatch(pattern, t, re.I)
        if m:
            if key is None:
                return ability, {'title': m[1], 'when': m[2]}
            return ability, {key: m[1] or ''}
    if t.lower() in ('my events', 'show my events', 'what events am i tracking', 'my deadlines', 'show my deadlines'):
        return 'event_list', {}
    if t.lower() in ('my tasks', 'show my tasks', 'show my plans', 'what are you working on'):
        return 'goal_list', {}
