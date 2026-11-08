"""screenshot, voice_tune (Jarvis's own voice), capabilities, and three that only the instant route can reach: shut_down, mic, (stop_talking is in misc.py).
Those have no `says`, so the AI is never offered them: closing Jarvis or switching off the microphone must be asked for in plain words."""
from ..registry import Bool, Choice, Result, Text, ability

@ability('settings_open',None,required={'page':Text()},patterns=[
    (r'(?:open(?: up)?|show(?: me)?|go to|take me to) (?:the |my |windows )?(.+?) settings(?: page)?',lambda m:{'page':m[1]}),
    (r'(?:open(?: up)?|show(?: me)?) (?:the |windows )?settings (?:for|on) (.+)',lambda m:{'page':m[1]})])
def settings_open(args,ctx):
    from ..windows_settings import page
    target=page(args['page'])
    if not target:return Result(False,'I do not have a direct link for that settings page, sir. Try Wi-Fi, Bluetooth, sound or display.',exact=True)
    ok=ctx.os.settings_page(target[1])
    return Result(ok,f'Opening {target[0]} settings, sir.' if ok else f'I could not open {target[0]} settings, sir.',{'page':target[0],'uri':target[1]},exact=True)

CAN = ("I can open and close apps, sites and folders, switch between them, search the web, play things on YouTube, control the music and video, "
       "change the volume, set timers, keep reminders and notes, tell you the time and date, and take screenshots, sir.")


@ability("screenshot", "picture of the screen", examples=[("grab the screen", "screenshot()")],
         phrases={p: {} for p in ("take a screenshot", "screenshot", "take screenshot", "click a screenshot", "click screenshot", "capture the screen")})
def screenshot(args, ctx):
    try:
        path = ctx.os.screenshot()
    except Exception:
        path = None
    return Result(bool(path), "Screenshot taken, sir." if path else "I couldn't take the screenshot, sir.", {"path": path})


TUNE = {"slower": "Speaking slower, sir.", "faster": "Speaking faster, sir.", "louder": "Speaking louder, sir.", "quieter": "Speaking quieter, sir."}


@ability("voice_tune", "Jarvis's OWN voice (your volume, speak up, speak slower), not the computer's", required={"change": Choice("slower", "faster", "louder", "quieter")},
         patterns=[(r'(?:increase|raise|speed up) (?:your|the) (?:(?:speaking|speech|talking|voice) )?(?:speed|rate)',lambda m:{'change':'faster'}),
                   (r'(?:decrease|reduce|lower|slow down) (?:your|the) (?:(?:speaking|speech|talking|voice) )?(?:speed|rate)',lambda m:{'change':'slower'}),
                   (r'(?:speak|talk) (?:a (?:little|bit) |more )?(faster|slower|louder|quieter)',lambda m:{'change':m[1]})],
         examples=[("talk louder please", 'voice_tune(change="louder")')],
         phrases={**{p: {"change": "slower"} for p in ("speak slower", "speak slowly", "speak more slowly", "slow down", "talk slower")},
                  **{p: {"change": "faster"} for p in ("speak faster", "speak quicker", "speed up", "talk faster")},
                  **{p: {"change": "louder"} for p in ("speak louder", "speak up", "increase your volume", "raise your volume", "talk louder")},
                  **{p: {"change": "quieter"} for p in ("speak quieter", "speak softer", "decrease your volume", "lower your volume", "talk quieter")}})
def voice_tune(args, ctx):
    current=getattr(ctx.speech,'v',None)
    key='speed' if args['change'] in ('faster','slower') else 'volume'
    before=getattr(current,key,None)
    ok = getattr(ctx.speech, "tune", lambda c: False)(args["change"])
    v=getattr(ctx.speech,'v',None)
    state={k:getattr(v,k,None) for k in ('speed','volume')}
    at_limit=ok and before is not None and before==state[key]
    text=('Already at my '+{'faster':'fastest','slower':'slowest','louder':'loudest','quieter':'quietest'}[args['change']]+' setting, sir.') if at_limit else TUNE[args['change']] if ok else "I'm not speaking aloud just now, sir."
    return Result(bool(ok),text, {"change": args["change"],**state},exact=True)


@ability("capabilities", "what Jarvis can do", phrases={p: {} for p in ("what can you do", "what are you able to do", "help", "what are your commands")})
def capabilities(args, ctx):
    return Result(True, CAN, exact=True)


@ability("shut_down", None, phrases={p: {} for p in ("shut down", "shutdown", "quit", "exit", "goodbye", "go to sleep", "power off", "turn yourself off", "close yourself", "shut yourself down")})
def shut_down(args, ctx):
    ctx.app.exit_requested = True
    return Result(True, "Goodbye, sir.", exact=True)


@ability("mic", None, required={"on": Bool()},
         phrases={**{p: {"on": False} for p in ("microphone off", "mic off", "stop listening", "turn off the microphone", "mute your microphone")}})
def mic(args, ctx):
    ok = ctx.app.set_mic(args["on"]) if ctx.app.set_mic else False
    if not ok:
        return Result(False, "I have no microphone to switch, sir.")
    return Result(True, "Microphone off for ten minutes, sir. I can't hear you until then." if not args["on"] else "Listening again, sir.", {"on": args["on"]})
