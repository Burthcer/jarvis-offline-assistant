"""Evidence-based event tracking. A missing date is a question, not a guess."""
import re
from datetime import datetime

from jarvis.timeparse import parse_when

from .. import organizer as O
from ..registry import Ask, Result, Text, ability
from ..uia import Refused


@ability('event_track', 'track an event and its registration deadline; text = the whole request exactly as said', required={'text': Text()},
         examples=[('I want to attend a coding meetup on friday', 'event_track(text="coding meetup on friday")')])
def event_track(args, ctx):
    text = args['text'].strip()
    parts = re.split(r'\s*[,;]?\s+(?:and )?(?:registration|applications?) (?:closes?|ends?)(?: on)?\s+', text, maxsplit=1, flags=re.I)
    main = parts[0]
    match = re.fullmatch(r'(.+?)\s+(?:on|starts? on|is on|starts?)\s+(.+)', main, re.I)
    title, happens = (match[1].strip(), O.date(match[2], ctx.now)) if match else (main, None)
    if not match:
        happens = O.date(main, ctx.now)
        if happens:
            title = parse_when(main, ctx.now)[0].strip(' ,:;')
    if match and not happens:
        return Result(False, 'Please give a future event date in words, sir, such as 23 November at 10 am.', exact=True)
    deadline = O.date(parts[1], ctx.now) if len(parts) > 1 else None
    if len(parts) > 1 and not deadline:
        return Result(False, 'Please give a clear future registration deadline, sir.', exact=True)
    if not title or len(title) > 120:
        return Result(False, 'Please use a shorter event name, sir.', exact=True)
    try:
        eid = O.save_event(ctx.memory, ctx.store, title, ctx.now, happens, deadline)
    except ValueError as e:
        return Result(False, str(e), exact=True)
    saved = O.find_event(ctx.memory, str(eid))
    deadline = datetime.fromisoformat(saved['deadline']) if saved['deadline'] else None
    if not deadline and re.search(r'\b(exams?|tests?)\b', title, re.I):
        return Result(True, f'Noted, sir: {title}' + (f' starts {happens:%d %B at %I:%M %p}. Preparation and exam reminders are set.' if happens else '. Tell me the exam date when you know it.'), {'event': eid}, exact=True)
    if not deadline:
        raise Ask(f'I am tracking {title}, sir, and will remind you to check registration. When does registration close? You can say a date, "read the screen", or "I don\'t know".',
                  pending={'event_slot': eid})
    return Result(True, f'Tracking {title}, sir. Registration is due {deadline:%d %B}. I set a reminder for {deadline:%I:%M %p} and an advance reminder when there is time.', {'event': eid}, exact=True)


@ability('event_deadline', 'save a registration deadline the user explicitly gave; title = event name, when = their date words', required={'title': Text(), 'when': Text()})
def event_deadline(args, ctx):
    words = lambda t: ' '.join(re.findall(r'[a-z0-9]+', t.lower()))
    # The small resolver may copy a date, but never supply one of its own.
    if words(args['when']) not in words(ctx.text):
        return Result(False, 'Please tell me the registration date yourself, sir. I will not guess it.', exact=True)
    due = O.date(args['when'], ctx.now)
    if not due:
        return Result(False, 'Please give a future deadline in words, sir.', exact=True)
    try:
        eid = O.save_event(ctx.memory, ctx.store, args['title'], ctx.now, deadline=due)
    except ValueError as e:
        return Result(False, str(e), exact=True)
    return Result(True, f'Registration for {args["title"]} is due {due:%d %B}, sir. I set the deadline reminder for {due:%I:%M %p}.', {'event': eid}, exact=True)


@ability('event_read', None, optional={'title': Text()})
def event_read(args, ctx):
    title = args.get('title', '')
    if not title:
        items = [r for r in O.rows(ctx.memory, 'commitments') if r['status'] == 'active']
        if len(items) != 1:
            return Result(False, 'Which event should I check on the screen, sir?', exact=True)
        title = items[0]['title']
    try:
        text = ctx.os.ui_read()
    except Refused as e:
        return Result(False, str(e), exact=True)
    # Never apply a deadline from a different page to this event.
    significant = [w for w in re.findall(r'[a-z0-9]+', title.lower()) if len(w) > 2 and w not in ('the', 'event', 'meetup')]
    if not significant or not all(w in text.lower() for w in significant):
        return Result(False, f'I cannot verify this page is about {title}, sir. Please tell me the deadline.', exact=True)
    due = O.screen_deadline(text[:12000], ctx.now)
    if not due:
        return Result(False, 'I cannot find one clear registration deadline on this page, sir. I kept your check reminder.', exact=True)
    try:
        eid = O.save_event(ctx.memory, ctx.store, title, ctx.now, deadline=due, source='screen, requested by you')
    except ValueError as e:
        return Result(False, str(e), exact=True)
    return Result(True, f'The page gives {due:%d %B} for registration for {title}, sir. I set a reminder for {due:%I:%M %p}.', {'event': eid}, exact=True)


@ability('event_list', None)
def event_list(args, ctx):
    rows = [r for r in O.rows(ctx.memory, 'commitments') if r['status'] == 'active']
    lines = [f'#{r["id"]} {r["title"]}: ' + ('exam ' + (r['happens'] or 'date not known') if r['kind'] == 'exam' else 'registration ' + (r['deadline'].replace('T', ' ') if r['deadline'] else 'deadline not known; check reminder set')) for r in rows]
    return Result(True, 'Your events, sir:\n' + '\n'.join(lines) if lines else 'No events tracked, sir.', exact=True)


@ability('event_cancel', None, required={'title': Text()})
def event_cancel(args, ctx):
    ok = O.cancel_event(ctx.memory, ctx.store, args['title'], ctx.now)
    return Result(ok, 'Event and its reminders removed, sir.' if ok else 'I cannot find that event, sir.', exact=True)
