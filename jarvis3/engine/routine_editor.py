"""Ordered, typed steps for the routine page. Keep unchanged saved actions intact."""
import hashlib
import json
import re

from . import understand
from .abilities.skills import MAX_STEPS, _check_step, name_error


def version(steps):
    return hashlib.sha256(json.dumps(steps, sort_keys=True).encode()).hexdigest()


def pills(steps):
    for index, step in enumerate(steps):
        action, args = step['a'], step['args']
        if action == 'say':
            text = args['text']
            match = re.fullmatch(r'open (.+)', text, re.I)
            kind, label = ('app', match[1]) if match else ('command', text)
        elif action == 'open' and set(args) == {'target'}:
            kind, label = 'app', args['target']
        else:
            values = ', '.join(f'{key}: {value}' for key, value in args.items())
            kind, label = 'saved', f"{action.replace('_', ' ')} · {values}" if values else action
        yield {'kind': kind, 'text': label, 'index': index}


def save(name, revision, entries, ctx):
    def fail(message):
        return {'ok': False, 'message': message}

    name = name.strip().lower()
    if problem := name_error(name, ctx):
        return fail(problem)
    memory = ctx.memory
    original = memory.routine_get(name)
    if revision is None and original is not None:
        return fail('That routine already exists. Open it with Edit.')
    if revision is not None and (original is None or version(original) != revision):
        return fail('This routine changed. Cancel and reopen it before saving.')
    limit = max(MAX_STEPS, len(original or []))
    if not isinstance(entries, list) or not 1 <= len(entries) <= limit:
        return fail(f'Add between 1 and {limit} steps.')
    old_pills = list(pills(original or []))
    steps = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('text'), str):
            return fail('A routine step could not be read.')
        index = entry.get('index')
        if type(index) is int and 0 <= index < len(old_pills) and entry == old_pills[index]:
            steps.append(original[index])
            continue
        kind, text = entry.get('kind'), entry['text'].strip()
        if not text or len(text) > 200 or '\n' in text or '\r' in text:
            return fail('Each pill needs a single line of up to 200 characters.')
        if kind == 'app':
            text = 'open ' + text
            hit = understand.instant(text, ctx.app.names, None)
            if not hit or len(hit[1]) != 1 or hit[1][0][0] != 'open':
                return fail(f'Use one known app or website in “{entry["text"]}”.')
        elif kind != 'command':
            return fail('Replace that saved action with a new command to change it.')
        if problem := _check_step(text, ctx):
            return fail(problem + ', sir. Nothing was saved.')
        steps.append({'a': 'say', 'args': {'text': text}})

    with memory.lock:
        if memory.routine_get(name) != original:
            return fail('This routine changed. Cancel and reopen it before saving.')
        if steps != original:
            memory.routine_save(name, steps, ctx.now)
    return {'ok': True, 'message': f'Saved {name}.'}
