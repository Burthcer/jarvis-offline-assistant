"""One native default action; completion is always checked separately by callers."""
def request(control):
    # Chromium's UIA Invoke can block for ~2s after the effect. Its supported
    # native legacy action returns promptly. Neither path uses coordinates/keys.
    action=None
    try:
        pattern=control.GetLegacyIAccessiblePattern()
        if pattern is not None and pattern.DefaultAction:
            action=pattern.DoDefaultAction
    except Exception:pass
    if action is None:
        try:
            pattern=control.GetInvokePattern()
            if pattern is not None:action=pattern.Invoke
        except Exception:pass
    if action is None:return False
    try:action(waitTime=0)
    except Exception:pass # may be post-effect event failure; never send a second action
    return True
