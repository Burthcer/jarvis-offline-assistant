from ..registry import Result,ability

@ability('music_start',None,patterns=[
    (r'(?:(?:i |i would |i would really |i really )?(?:want|wanna|would like) to listen to|put on|start|play) (?:some |my |the )?(?:music|default playlist|default mix)',lambda m:{})])
def music_start(args,ctx):
    music=getattr(ctx.app,'music',None)
    return music.start() if music else Result(False,'Music sessions are available in the V3 desktop, sir.',exact=True)

REJECTIONS=("i don't like this","i do not like this","i don't like this song","i do not like this song","play something else","something else")
@ability('music_reject',None)
def music_reject(args,ctx):
    music=getattr(ctx.app,'music',None)
    if not music or not music.player:return Result(False,'Which music session do you mean, sir?',exact=True)
    return music.reject(ctx.app.selection)
