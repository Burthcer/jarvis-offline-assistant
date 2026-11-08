"""volume (the computer's, or one app's) and media (what is playing). Both check the real state afterwards."""
import re

from ..osapi import STEP
from ..registry import Ask, Choice, Name, Number, Result, ability
from .apps import pretty


def named_next_to_volume(ctx):
    """'reduce the YouTube volume': the app is named right beside the word volume, even if the AI left it out."""
    for n, k in ctx.catalog.items():
        if k in ("app", "site") and len(n) >= 4 and re.search(rf"\b{re.escape(n)}(?:'s)?\s+(?:volume|sound|audio)\b|\b(?:volume|sound|audio)\s+(?:of|on|for)\s+(?:the\s+)?{re.escape(n)}\b", ctx.text.lower()):
            return n
    return None

def query_route(text):
    t=text.lower().strip(' .!?').replace("what's",'what is').replace('whats ','what is ')
    if t in ('what volume is it','what volume is it at','how loud is it','how loud is my computer','how loud is the computer'):
        return {}
    match=re.fullmatch(r'(?:what is|tell me|check|read|show me) (?:the |my )?(?:(?:current|system|computer|laptop|speaker|pc) )?volume(?: level)?(?: (?:at|now|right now))?',t)
    if match:return {}
    match=re.fullmatch(r'(?:what is|tell me|check|read|show me) (?:the |my )?(?:volume(?: level)? (?:of|on|for) (.+?)|(.+?) volume(?: level)?)(?: at)?',t)
    if match:return {'app':match[1] or match[2]}
    return None

@ability('volume_read','read the current computer or named app volume without changing it',optional={'app':Name(kinds=('app','site'))})
def volume_read(args,ctx):
    app=args.get('app')
    try:
        level=ctx.os.app_volume(ctx.os.audio_app(app,ctx.kind(app))) if app else ctx.os.volume()
        if level is None:return Result(False,f'I could not read {pretty(app)} volume; no audio session is available, sir.',exact=True)
        if type(level) not in (int,float) or not 0<=level<=100:raise ValueError('Invalid volume readback')
        muted=ctx.os.muted() if not app else None
        return Result(True,f"{pretty(app) if app else 'Computer'} volume is {level:g} percent"+(' and muted' if muted else '')+', sir.',{'level':level,'muted':muted,'changed':False},exact=True)
    except Exception:return Result(False,'I could not read the current volume, sir.',exact=True)


@ability("volume", "the COMPUTER's sound. level = 0 to 100 for set (full, max = 100, half = 50). amount = percent for up or down. app only if one app was named",
         required={"action": Choice("set", "up", "down", "mute", "unmute", aliases={"quieter": "down", "softer": "down", "lower": "down", "decrease": "down", "reduce": "down", "louder": "up", "higher": "up", "raise": "up", "increase": "up"})},
         optional={"level": Number(0, 100), "amount": Number(1, 100), "app": Name(kinds=("app", "site"))},
         examples=[("max the sound", 'volume(action="set", level=100)'), ("turn it up by fifteen", 'volume(action="up", amount=15)')],
         clean=lambda a: {k: v for k, v in a.items() if not (k == "level" and a["action"] != "set") and not (k == "amount" and a["action"] not in ("up", "down"))},
         phrases={"mute": {"action": "mute"}, "unmute": {"action": "unmute"}, "volume up": {"action": "up"}, "volume down": {"action": "down"},
                  "volume full": {"action": "set", "level": 100}, "volume max": {"action": "set", "level": 100}})
def volume(args, ctx):
    act, level, app, os = args["action"], args.get("level"), args.get("app") or named_next_to_volume(ctx), ctx.os
    if app:
        args["app"] = app  # the plan shows the app even when the AI left it out
        prog = os.audio_app(app, ctx.kind(app))
        now = os.app_volume(prog)
        if now is None:
            return Result(False, f"{pretty(app)} isn't playing any sound, sir.", {"app": app})
        if (act == "set" and level is None) or not re.search(r"\b(up|down|louder|quieter|softer|lower|raise|reduce|increase|decrease|more|less|mute|max|full|half|set|to|\d+|percent)\b", ctx.text.lower()):
            raise Ask("Louder or quieter, sir?")  # one app and no direction: never guess
        want = level if act == "set" else now + (args.get("amount", STEP) if act == "up" else -args.get("amount", STEP))
        got = os.set_app_volume(prog, want)
        ok = got is not None and abs(got - max(0, min(100, want))) <= 2
        return Result(ok, f"{pretty(app)} is now at {got} percent, sir." if ok else f"I couldn't change {pretty(app)}'s volume, sir.", {"app": app, "level": got})
    if act in ("mute", "unmute"):
        want = act == "mute"
        if os.muted() == want:
            return Result(True, "Already muted, sir." if want else "Not muted, sir.", {"changed": False})
        got = os.set_muted(want)
        return Result(got == want, ("Muted" if want else "Unmuted") + ", sir." if got == want else "I couldn't change the mute, sir.", {"muted": got}, undo=lambda: volume({"action": "unmute" if want else "mute"}, ctx))
    before = os.volume()
    if act == "set":
        if level is None:
            raise Ask("To what level, sir?")
        want = level
    else:
        want = before + (args.get("amount", STEP) if act == "up" else -args.get("amount", STEP))
    want = max(0, min(100, want))
    if act != "set" and want == before:
        return Result(True, "Already at maximum, sir." if act == "up" else "Already at the minimum, sir.", {"level": before, "changed": False})
    got = os.set_volume(want)
    ok = abs(got - want) <= 2
    say = f"Volume set to {got} percent, sir." if act == "set" else ("Volume up, sir." if act == "up" else "Volume down, sir.")
    return Result(ok, say if ok else "I couldn't change the volume, sir.", {"level": got, "before": before}, undo=(lambda: volume({"action": "set", "level": before}, ctx)) if ok else None)


SAY = {"pause": "Paused, sir.", "play": "Playing, sir.", "next": "Next one, sir.", "previous": "Previous one, sir."}
COUNTS = {'one': 1, 'two': 2, 'second': 2, 'twice': 2, 'three': 3, 'third': 3, 'thrice': 3,
          'four': 4, 'fourth': 4, 'five': 5, 'fifth': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10}
COUNT = r'(?:10|[1-9]|' + '|'.join(COUNTS) + ')'


def count_value(word):
    return int(word) if word.isdigit() else COUNTS[word]


class MediaCount(Number):
    def unsupported(self, v, env):
        words = re.findall(r'\w+', env.text.lower())
        return v > 1 and not (any(count_value(w) == v for w in words if w in COUNTS or w.isdigit())
                             or words.count('next') == v or words.count('previous') == v)


def skip_args(m):
    return {'action': m['action'], 'count': count_value(m['count'])}


@ability("media", "control what is playing (play, pause, next, previous; video or song). count = next/previous steps, only when explicitly requested",
         required={"action": Choice("play", "pause", "next", "previous")},
         optional={"count": MediaCount(1, 10)},
         examples=[("skip this song", 'media(action="next")'), ("hold the music", 'media(action="pause")')],
         patterns=[
             (rf'(?:play |go to )?(?:the )?(?P<action>next|previous) (?P<count>{COUNT})(?: times?)?(?: (?:songs?|tracks?|videos?))?', skip_args),
             (rf'(?:play |go to )?(?:the )?(?P<action>next|previous) (?:song|track|video) (?P<count>{COUNT})(?: times?)?', skip_args),
             (rf'(?:play |go to )?(?:the )?(?P<count>{COUNT}) (?P<action>next|previous)(?: (?:songs?|tracks?|videos?))?', skip_args),
             (rf'(?P<direction>skip|skip ahead|go forward|go back) (?P<count>{COUNT})(?: (?:songs?|tracks?|videos?))',
              lambda m: {'action': 'previous' if m['direction'] == 'go back' else 'next', 'count': count_value(m['count'])}),
             (r'next(?: next){1,9}', lambda m: {'action': 'next', 'count': len(m[0].split())}),
             (r'previous(?: previous){1,9}', lambda m: {'action': 'previous', 'count': len(m[0].split())}),
         ],
         phrases={**{p: {"action": "pause"} for p in ("pause", "pause the music", "pause music", "pause the song", "pause the video", "pause it")},
                  **{p: {"action": "play"} for p in ("play", "resume", "play the music", "play music", "resume the music", "resume the video", "continue playing")},
                  **{p: {"action": "next"} for p in ("next", "next song", "next video", "next track", "skip", "skip this song", "skip the song")},
                  **{prefix + direction + suffix: {'action': direction} for direction in ('next', 'previous')
                     for prefix in ('', 'the ', 'play ', 'play the ', 'go to the ', 'skip to the ')
                     for suffix in (' song', ' track', ' video', ' one')},
                  **{p: {"action": "previous"} for p in ("previous", "previous song", "previous video", "previous track", "go back a song")}})
def media(args, ctx):
    act = args["action"]
    count = args.get('count', 1)
    session=getattr(ctx.app,'music',None)
    if session and session.player:
        named=[n for n,k in ctx.catalog.items() if k in ('app','site') and n not in ('edge','chrome','youtube','youtube music') and re.search(r'\b'+re.escape(n)+r'\b',ctx.text,re.I)]
        if named:return Result(False,'That is a different player from this music session, sir.',exact=True)
        r=session.control(act,count)
        if r.ok or not r.facts.get('stale'):return r
        session.player=None            # he moved to another tab: control what is in front now, not the old music tab (the owner, 7 Nov)
    front=ctx.os.front() if hasattr(ctx.os,'front') else ('','')
    if act in ('next','previous') and front[0] in ('msedge','chrome') and re.search(r'- YouTube(?: - .*)?$',front[1] or '') and 'YouTube Music' not in (front[1] or ''):
        # the focused YouTube tab gets its own shortcut (Shift+N / Shift+P), never another tab's player
        ok=all(ctx.os.front_keys(0x4E if act=='next' else 0x50,True) for _ in range(count))
        return Result(ok,SAY[act] if count==1 else f"{'Forward' if act=='next' else 'Back'} {count} tracks, sir.",{'front_tab':True,'count':count},exact=True) if ok else Result(False,'The YouTube tab did not take that key, sir.',exact=True)
    if session and act=='play' and re.fullmatch(r'play (?:the |my )?music[.!]?',ctx.text.strip(),re.I):
        return session.start()
    if count > 1 and act not in ('next', 'previous'):
        raise Ask('Do you mean next or previous, sir?')
    done, state = 0, None
    for _ in range(count):
        ok, state = ctx.os.media(act)
        if not ok:
            break
        done += 1
    if not ok and done:
        return Result(False, f"The player accepted {done} of {count} {act} commands, sir.", {'state': state, 'count': done}, exact=True)
    if not ok and state is None:
        if act in ('play','pause') and front[0] in ('msedge','chrome') and re.search(r'- YouTube(?: - .*)?$',front[1] or '') and ctx.os.front_keys(0x4B):
            return Result(True, f"Pressed {act} on the YouTube tab, sir.", {'front_tab': True, 'unverified': True}, exact=True)
        return Result(False, "Nothing is playing that I can control, sir.", {})
    if not ok:
        return Result(False, "The player didn't accept that, sir.", {"state": state})
    if act in ("play", "pause") and state and state["playing"] != (act == "play"):
        return Result(False, f"I asked it to {act}, but it is still {'playing' if state['playing'] else 'paused'}, sir.", {"state": state})
    back = {"play": "pause", "pause": "play"}.get(act)
    say = SAY[act] if count == 1 else f"{'Forward' if act == 'next' else 'Back'} {count} tracks, sir."
    return Result(True, say, {"state": state, 'count': count}, undo=(lambda: media({"action": back}, ctx)) if back else None)
