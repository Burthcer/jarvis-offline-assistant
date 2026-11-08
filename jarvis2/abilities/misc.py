"""stop_talking: cuts Jarvis's speech off at once. Instant route only, never waits for the AI (says=None hides it from the AI)."""
from ..registry import Result, ability


@ability("stop_talking", None, phrases={p: {} for p in ("shut up", "shut the fuck up", "stop talking", "be quiet", "quiet", "fuck off", "shut it", "stop speaking", "enough", "zip it")})
def stop_talking(args, ctx):
    ctx.speech.stop()
    return Result(True, "", {"silent": True}, exact=True)
