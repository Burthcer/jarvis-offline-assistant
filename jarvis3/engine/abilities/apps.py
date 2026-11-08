"""open, close, focus: apps, sites, folders, bookmarks."""
from ..registry import Choice, Name, Number, Result, ability

PRETTY = {"youtube": "YouTube", "youtube music": "YouTube Music", "linkedin": "LinkedIn", "dev.to": "dev.to", "chatgpt": "ChatGPT", "whatsapp": "WhatsApp", "wispr flow": "Wispr Flow"}


def pretty(name):
    return PRETTY.get(name) or (name.title() if name.islower() else name)


@ability("open", "open an app, website, folder or bookmark. count = how many tabs",
         required={"target": Name()}, optional={"count": Number(1, 10), "browser": Choice("edge", "chrome")},
         examples=[("open three netflix tabs", 'open(target="netflix", count=3)')],
         verbs=("open", "opened", "launch", "start", "open up"))
def open_(args, ctx):
    name, n = args["target"], args.get("count", 1)
    ok = ctx.os.open(name, ctx.kind(name), n, args.get("browser"))
    return Result(ok, f"Opening {pretty(name)}, sir." if ok else f"I couldn't open {pretty(name)}, sir.", {"target": name, "count": n}, undo=(lambda: close({"target": name}, ctx)) if ok else None)


@ability("close", "close an app or a website completely",
         required={"target": Name()}, examples=[("get rid of netflix and teams", 'close(target="netflix")\nclose(target="teams")')],
         verbs=("close", "closed"))
def close(args, ctx):
    name = args["target"]
    ok, was = ctx.os.close(name, ctx.kind(name))
    if ok and was:
        return Result(True, f"Closing {pretty(name)}, sir.", {"target": name}, undo=lambda: open_({"target": name}, ctx))
    if ok:
        return Result(True, f"{pretty(name)} isn't open, sir.", {"target": name, "changed": False})
    if was:
        return Result(False, f"I asked {pretty(name)} to close, but it is still running, sir.", {"target": name})
    return Result(False, f"I'm afraid I can't close {pretty(name)}, sir.", {"target": name})


@ability("focus", "bring a running app to the front (focus, switch to)",
         required={"target": Name()}, examples=[("switch over to teams", 'focus(target="teams")')],
         verbs=("focus", "switch to"))
def focus(args, ctx):
    name = args["target"]
    if ctx.os.focus(name, ctx.kind(name), wait=0):
        return Result(True, f"Switching to {pretty(name)}, sir.", {"target": name})
    return Result(False, f"I couldn't bring {pretty(name)} to the front, sir.", {"target": name})
