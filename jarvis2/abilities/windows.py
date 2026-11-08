"""Window state is never a synonym for closing an app."""
import re
from ..registry import Choice, Text, Result, ability

@ability('window_state', 'minimize, maximize or restore windows; target = app name, this, all windows, or all tabs (browser windows)',
         required={'action': Choice('minimize','maximize','restore'), 'target': Text()})
def window_state(args, ctx):
    done, total = ctx.os.window_state(args['action'], args['target'])
    return Result(done == total and total > 0,
                  f"{args['action'].capitalize()}: {done} of {total} windows, sir." if total else 'I could not find that window, sir.',
                  {'changed': done, 'total': total}, exact=True)

def route(text):
    parts = re.split(r'\s+(?:and then|and|then)\s+(?=(?:minimi[sz]e|maximi[sz]e|restore)\b)', text, flags=re.I)
    if len(parts) > 1:
        calls = [route(part) for part in parts]
        return [call for part in calls for call in part] if all(calls) else None
    match = re.fullmatch(r'(minimi[sz]e|maximi[sz]e|restore)\s+(?:(?:the|my)\s+)?(.+)', text.strip(' .!?'), re.I)
    if match:
        return [('window_state', {'action':match[1].lower().replace('s','z') if match[1].lower() != 'restore' else 'restore', 'target':match[2]})]
    return None
