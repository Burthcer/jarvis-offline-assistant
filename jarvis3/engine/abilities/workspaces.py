from ..registry import Text,Result,ability
@ability('workspace_run',None,required={'name':Text()},patterns=[
    (r'(?:(?:i want to |i would like to |let ?s )?(?:continue working on|continue with|get back to|work on)|(?:start|open|run) (?:my )?workspace) (.+)',lambda m:{'name':m[1].strip().lower()})])
def workspace_run(args,ctx):
    from jarvis3.workspaces import run
    ctx.app.workspace_cancel.clear()
    return run(args['name'],ctx)
@ability('workspace_resume',None,required={'name':Text()},patterns=[(r'resume (?:my )?workspace (.+)',lambda m:{'name':m[1].strip().lower()})])
def workspace_resume(args,ctx):
    from jarvis3.workspaces import run
    ctx.app.workspace_cancel.clear()
    return run(args['name'],ctx,resume=True)

@ability('workspace_stop',None,phrases={p:{} for p in ('stop workspace','cancel workspace','stop the workspace','cancel the workspace')})
def workspace_stop(args,ctx):
    ctx.app.workspace_cancel.set()
    return Result(True,'Pending workspace steps stopped, sir.',exact=True)
