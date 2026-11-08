"""A bounded local agent: propose, validate, persist, execute, check, stop.
No shell, code writing, recursive plans, or actions outside the registry.
"""
import json
import re

from .. import organizer as O, understand
from ..registry import ABILITIES, Ask, Result, Text, ability, signature

ALLOWED = {'open', 'close', 'focus', 'search', 'volume', 'media', 'timer_set', 'reminder_add', 'note_save', 'clock',
           'screen_ask', 'ui_click', 'ui_type', 'ui_press', 'event_track', 'event_deadline','window_state','browser_tabs'}


def job(memory, ident=''):
    items = O.rows(memory, 'jobs')
    if ident:
        return next((j for j in items if str(j['id']) == str(ident)), None)
    return next((j for j in items if j['state'] not in ('done', 'cancelled')), None)


def update(ctx, j, state, cursor=None, results=None):
    ctx.memory._w('UPDATE jobs SET state=?,cursor=?,results=?,updated=? WHERE id=?', state,
                  j['cursor'] if cursor is None else cursor, j['results'] if results is None else json.dumps(results), ctx.now.isoformat(), j['id'])
    ctx.app.on_progress()


def checked(raw, ctx, request):
    if not 1 <= len(raw) <= 5 or any(a not in ALLOWED for a, _ in raw):
        raise ValueError('The plan contains unsupported steps')
    env = understand.Env(request, ctx.app.names, ctx.now, followup=False)
    normalized = lambda s: ' '.join(re.findall(r'[a-z0-9]+', s.lower()))
    for name, args in raw:
        if args.get('when') and normalized(args['when']) not in normalized(request):
            raise ValueError('A date was not present in your request')
        if name in ('event_track', 'note_save') and normalized(args['text']) not in normalized(request):
            raise ValueError('A saved fact or event was not present in your request')
    understand.unsupported(raw, env)
    return understand.convert(raw, env)


@ability('goal_plan', None, required={'text': Text()})
def goal_plan(args, ctx):
    O.setup(ctx.memory)
    if ctx.ai is None:
        return Result(False, 'I need my planning model for that, sir.', exact=True)
    request = args['text'][:400]
    specs = '\n'.join(signature(ABILITIES[n]) for n in sorted(ALLOWED) if n in ABILITIES and ABILITIES[n].says)
    prompt = ('Plan the user request using ONLY these functions. At most five function calls, one per line. No code fences or explanation. '
              'Copy app names, dates, numbers and saved facts from the request. Never invent dates or deadlines. '
              'Do not run anything. If essential information is missing answer ASK: followed by one question. '
              'Do not substitute a different task. Functions:\n' + specs)
    try:
        msgs = [{'role': 'system', 'content': prompt},
                {'role': 'user', 'content': 'launch obsidian then keep a 13 minute timer'},
                {'role': 'assistant', 'content': 'open(target="obsidian")\ntimer_set(duration="13 minutes")'},
                {'role': 'user', 'content': 'make volume 35 and open calculator'},
                {'role': 'assistant', 'content': 'volume(action="set", level=35)\nopen(target="calculator")'},
                {'role': 'user', 'content': request}]
        out = ctx.ai.complete(msgs, temperature=0.0, max_tokens=250)
        if len([l for l in out.splitlines() if l.strip()]) > 5:
            raise ValueError('Too many steps')
        kind, raw = understand.parse(out)
        if kind != 'act':
            return Result(False, raw if kind == 'ask' else 'I could not make a checked plan, sir. Please describe the steps.', exact=True)
        checked(raw, ctx, request)     # All steps must pass before anything runs.
    except (ValueError, SyntaxError, Ask) as e:
        return Result(False, f'I need a clearer plan, sir. {e}', exact=True)
    ident = ctx.memory._w('INSERT INTO jobs(request,steps,updated) VALUES(?,?,?)', request, json.dumps(raw), ctx.now.isoformat()).lastrowid
    preview = '; '.join(f'{i + 1}. {a.replace("_", " ")}: ' + ', '.join(str(v) for v in ar.values()) for i, (a, ar) in enumerate(raw))
    raise Ask(f'Plan #{ident}, sir: {preview}. Shall I run it?', pending={'goal_slot': ident})


@ability('goal_run', None, optional={'id': Text()})
def goal_run(args, ctx):
    j = job(ctx.memory, args.get('id', ''))
    if not j or j['state'] in ('cancelled', 'done'):
        return Result(False, 'No unfinished plan to run, sir.', exact=True)
    if j['state'] == 'running':
        update(ctx, j, 'blocked')
        return Result(False, 'This plan was interrupted during a step, sir. Please check what happened before making a new plan.', exact=True)
    raw = json.loads(j['steps'])
    try:
        calls = checked(raw, ctx, j['request'])   # Recheck current names and dates after restart.
    except (ValueError, Ask) as e:
        update(ctx, j, 'blocked')
        return Result(False, f'The plan needs updating, sir: {e}', exact=True)
    results = json.loads(j['results'])
    ctx.app.cancel_goal.clear()
    for i in range(j['cursor'], len(calls)):
        if ctx.app.cancel_goal.is_set():
            update(ctx, j, 'cancelled', i, results)
            return Result(False, 'Plan stopped, sir. Finished steps are kept in the task history.', exact=True)
        call = calls[i]
        ab = ABILITIES[call.ability]
        update(ctx, j, 'running', i, results)
        # A yes applies to one specific paused step, never the whole chain.
        step_yes = bool(ctx.confirmed and getattr(ctx.app, 'confirmed_goal_step', None) == (j['id'], i))
        ctx.confirmed = step_yes
        ctx.text = j['request']
        try:
            if ab.risk == 'confirm' and not step_yes:
                raise Ask('This step needs your yes, sir.')
            res = ab.fn(call.args, ctx)
        except Ask as ask:
            if ask.pending and 'event_slot' in ask.pending:
                update(ctx, j, 'blocked', i, results)
                raise
            update(ctx, j, 'waiting', i, results)
            raise Ask(f'Plan #{j["id"]}, step {i + 1}: {ask.question}', pending={'goal_step': [j['id'], i]})
        except Exception:
            update(ctx, j, 'blocked', i, results)
            raise
        results.append({'step': i + 1, 'ok': res.ok, 'reply': res.plain})
        if not res.ok:
            update(ctx, j, 'blocked', i, results)
            return Result(False, f'Plan paused at step {i + 1}, sir. {res.plain}', exact=True)
        update(ctx, j, 'running', i + 1, results)
        ctx.app.confirmed_goal_step = None
    update(ctx, j, 'done', len(calls), results)
    return Result(True, 'Plan finished, sir. ' + ' '.join(r['reply'] for r in results[-5:]), {'job': j['id']}, exact=True)


@ability('goal_cancel', None, optional={'id': Text()})
def goal_cancel(args, ctx):
    j = job(ctx.memory, args.get('id', ''))
    if not j:
        return Result(False, 'No unfinished plan, sir.', exact=True)
    ctx.app.cancel_goal.set()
    update(ctx, j, 'cancelled')
    return Result(True, 'Plan cancelled, sir. Finished steps are kept in the task history.', exact=True)


@ability('goal_list', None)
def goal_list(args, ctx):
    items = O.rows(ctx.memory, 'jobs')[:8]
    return Result(True, '\n'.join(f'#{j["id"]} {j["request"]}: {j["state"]}, {j["cursor"]}/{len(json.loads(j["steps"]))} steps' for j in items) or 'No plans yet, sir.', exact=True)
