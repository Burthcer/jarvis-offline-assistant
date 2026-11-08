"""search, play_on, video (YouTube keys), tab_close. Pages open in the site's own browser (Edge unless it's one of Chrome's three); a search with no site is Google in Edge."""
import re
import threading
from urllib.parse import quote_plus

from jarvis3.legacy.actions import SITES as V1_SITES, TAB

from ..osapi import EXTRA_SITES

SITES = {**EXTRA_SITES, **V1_SITES}

from ..registry import Choice, Name, Result, Text, ability
from .apps import pretty

@ability('browser_tabs', 'focus or close browser tabs; selector = original positions (second, fifth) or a unique title',
         required={'action':Choice('focus','close'), 'selector':Text()})
def browser_tabs(args, ctx):
    result = ctx.os.browser_tabs(args['action'],args['selector'])
    count = len(result['done'])
    say = (f"{'Closed' if args['action']=='close' else 'Selected'} {count} tab{'s' if count!=1 else ''}, sir."
           if result['ok'] else f"Completed {count} tabs. {result['message']}")
    return Result(result['ok'],say, result, exact=True)

KEEP = r'(?:except(?: for)?|other than|but(?: not)?|apart from|besides|leaving|save|keep(?:ing)?(?: only)?|not)'


def tab_words(text):
    """V4 (the owner's log, 8 Nov): speech writes 'tab' as 'Tap' and 'close' as 'Closes'/'Closed'."""
    t = re.sub(r'[.!?]+', ' ', (text or '').lower())
    t = re.sub(r'\s*,\s*', ', ', t)
    t = re.sub(r'\s+', ' ', t).strip(' ,')
    t = re.sub(r'^(?:please |jarvis )*', '', t)
    t = re.sub(r'(?<=\S)\s+taps\b', ' tabs', t)
    t = re.sub(r'(?<=\S)\s+tap\b', ' tab', t)                  # never the first word: 'tap on Shorts' is a click
    t = re.sub(r'^(?:closes|closed|close up)\b', 'close', t)
    return t


def tab_route(text):
    import re
    t = tab_words(text)
    plain = t.replace(',', '')
    keep = re.fullmatch(r'close (?:all|every|everything)?\s*(?:of )?(?:the )?(?:other )?(?:tabs?|everything|the rest)?\s*' + KEEP + r' (?:the |my )?(.+?)(?: one| ones| tab| tabs| open)?', plain)
    if keep and re.search(r'\btabs?\b|\bother\b|\beverything\b|\brest\b', plain):
        return [('browser_tabs', {'action': 'close', 'selector': 'all except ' + keep[1].strip()})]
    if re.fullmatch(r'close (?:all )?(?:of )?(?:the )?other tabs?', plain):
        return [('browser_tabs', {'action': 'close', 'selector': 'all except this'})]
    match = re.fullmatch(r'(close|closed|shut(?: down)?|kill|focus(?: on)?|switch to|select|go to) (?:the )?(.+?) tabs?',t,re.I)
    if not match:match=re.fullmatch(r'(close|closed|shut(?: down)?|kill) (?:the )?tabs? (?:number |numbers )?(.+)',t,re.I)
    text = t
    if not match:
        bare=re.fullmatch(r'(?:go to the |the )?(previous|next|last|first) tab',text.strip(' .!?'),re.I)
        if bare:return [('browser_tabs',{'action':'focus','selector':bare[1].lower()})]
    if match:
        closing=match[1].lower() in ('close','closed','shut','shut down','kill')
        selector=match[2].lower().strip();site=None
        for name in sorted(SITES,key=len,reverse=True):
            if selector.endswith(' '+name):selector,site=selector[:-len(name)].strip(),name;break
        selector={'this fucking':'this','that':'this','current':'this'}.get(selector,selector)
        if closing and selector in ('this','all'):
            return [('tab_close',{'which':selector,**({'site':site} if site else {})})]
        if closing:
            from ..browser_tabs import ORDINALS
            tokens = re.findall(r'\w+',selector)
            if any(t not in ORDINALS and t not in ('and','the','last') and not re.fullmatch(r'\d+(?:st|nd|rd|th)?',t) for t in tokens):
                return None
            if site:
                if selector in ('first','second','third','last'):return [('tab_close',{'which':selector,'site':site})]
                return [('tab_group_close',{'selector':selector,'site':site})]
        elif site:return None
        return [('browser_tabs',{'action':'close' if closing else 'focus','selector':selector})]
    return None

@ability('tab_group_close',None,required={'selector':Text(),'site':Name(kinds=('site',))})
def tab_group_close(args,ctx):
    report=ctx.os.tab_action(args['selector'],tab_pattern(args['site']))
    count=len(report['done'])
    return Result(report['ok'],f'Closed {count} matching tabs, sir.' if report['ok'] else f"Closed {count} matching tabs. {report['message']}",report,exact=True)


@ability('tab_focus', 'focus a browser tab by its position',
         required={'which': Choice('first', 'second', 'third', 'fourth', 'fifth', 'last')},
         patterns=[(r'(?:focus(?: on)?|switch to|go to|select) (?:the )?(first|second|third|fourth|fifth|last) tab', lambda m: {'which': m[1]})])
def tab_focus(args, ctx):
    ok = ctx.os.focus_tab(args['which'])
    return Result(ok, f"Switched to the {args['which']} tab, sir." if ok else 'I could not select that browser tab, sir.', exact=True)

VIDEO = {"fullscreen": (0x46, False, "Full screen, sir."), "exit_fullscreen": (0x1B, False, "Out of full screen, sir."), "skip_ahead": (0x4C, False, "Skipping ahead, sir."), "rewind": (0x4A, False, "Going back, sir."),
         "captions": (0x43, False, "Captions switched, sir.")}
VIDEO_PHRASES = {**{p: {"action": "fullscreen"} for p in ("fullscreen", "full screen", "go fullscreen", "go full screen", "make it fullscreen", "make it full screen")},
                 **{p: {"action": "exit_fullscreen"} for p in ("exit fullscreen", "exit full screen", "leave fullscreen", "leave full screen", "come out of full screen", "come out of fullscreen", "get out of full screen", "get out of fullscreen")}}


def tab_pattern(site):
    import re
    return None if not site else TAB.get(site, r"\b%s\b" % re.escape(site))


def search_route(text,catalog=None):
    """Exact site/browser search grammar; never infer a site from query words.

    A supported `open SITE and search QUERY` is one scoped search, so it does
    not open an extra homepage first. Other compound actions stay with the
    general resolver; no suffix or remainder is silently discarded.
    """
    import re
    normal=lambda s:' '.join(s.lower().split())
    known={}
    for name,kind in (catalog if catalog is not None else {name:'site' for name in SITES}).items():
        if kind not in ('site','bookmark'):continue
        key=normal(name)
        known[key]=name if key not in known else None
    text=text.strip().rstrip('.!?').strip()
    scope=None
    opened=re.fullmatch(r'open(?: up)? (?:the )?(.+?) and(?: then)? (?:search(?: up| for)?|look up|google) (.+)',text,re.I)
    if opened:
        scope=known.get(normal(opened[1]))
        if scope not in SITES or not SITES[scope][2]:return None
        body=opened[2]
    else:
        command=re.fullmatch(r'(?:search(?: up| for)?|look up|google) (.+)',text,re.I)
        if not command:return None
        body=command[1]
    browser=None
    prefix=re.fullmatch(r'(?:on|with|using) (?:the )?(edge|chrome)(?: browser)? (.+)',body,re.I)
    if prefix:browser,body=prefix[1].lower(),prefix[2]
    # Both "search on SITE for Q" and "search SITE for Q" name the
    # destination explicitly. "search for SITE tutorials" stays a web query.
    for key in sorted(known,key=len,reverse=True):
        if known[key] is None:continue
        prefix=re.fullmatch(r'(?:(?:on|in) '+re.escape(key)+r' (?:for )?|'+re.escape(key)+r' for )(.+)',body,re.I)
        if prefix:
            if scope and scope!=known[key]:return None
            scope,body=known[key],prefix[1]
            break
    for _ in range(4):
        suffix=re.fullmatch(r'(.+?) (?:on|with|using) (?:the )?(edge|chrome)(?: browser)?',body,re.I)
        if suffix:
            if browser and browser!=suffix[2].lower():return None
            browser,body=suffix[2].lower(),suffix[1]
            continue
        site=None
        for marker in re.finditer(r'\s+on\s+',body,re.I):
            candidate=known.get(normal(body[marker.end():]))
            if candidate is not None:site=(candidate,body[:marker.start()]);break
        if site:
            if scope and scope!=site[0]:return None
            scope,body=site
            continue
        break
    else:return None
    # A query may contain ordinary "on"/"with" text. Distinct action clauses
    # need the general resolver, including negated/retracted second clauses.
    actions=r'open|close|focus|search|look up|google|play|pause|set|remind|copy|remember|save|shut|exit|quit|stop|cancel|minimi[sz]e|maximi[sz]e|restore|switch|select|go'
    if re.search(r'(?:\b(?:and(?: then)?|then|but|instead)\s+|[;.!?]\s*)(?:(?:do not|don\x27t|never|please)\s+)?(?:'+actions+r')\b',body,re.I):return None
    body=body.strip()
    if not body or len(body)>200:return None
    return [('search',{'query':body,**({'site':scope} if scope else {}),**({'browser':browser} if browser else {})})]


@ability("search", "search the web. site or browser ONLY if the user named it", required={"query": Text()},
         optional={"site": Name(kinds=("site", "bookmark"), lenient=True), "browser": Choice("edge", "chrome")},
         examples=[("find cheap shoes on amazon", 'search(query="cheap shoes", site="amazon")'), ("look for used bikes", 'search(query="used bikes")')])
def search(args, ctx):
    q, site = args["query"].strip(), args.get("site") or "google"
    kind = ctx.catalog.get(site)
    if kind == "site" and site in SITES and SITES[site][2]:
        browser, url, where = args.get("browser") or SITES[site][0], SITES[site][2] + quote_plus(q[:200]), pretty(site)
    else:                                                     # a site with no search page of its own: Google, with the site's name added
        q2 = q if site == "google" else f"{q} {site}"
        browser, url, where = args.get("browser") or "edge", SITES["google"][2] + quote_plus(q2[:200]), "Google"
    ok = ctx.os.url(browser, url)
    return Result(ok, f"Searching {where} for {q}, sir." if ok else f"I couldn't open the search, sir.", {"query": q, "site": site, "browser": browser})


@ability("play_on", "find and play a song or video by name (site = youtube or youtube music; the default is youtube music)", required={"query": Text()},
         optional={"site": Name(kinds=("site",))}, examples=[("put on some jazz on youtube", 'play_on(query="jazz", site="youtube")')])
def play_on(args, ctx):
    q, site = args["query"].strip(), args.get("site") or "youtube music"
    if site not in SITES or not SITES[site][2]:
        return Result(False, f"I can't play on {pretty(site)}, sir.")
    ok = ctx.os.url(SITES[site][0], SITES[site][2] + quote_plus(q[:200]))
    if ok and site == "youtube":
        threading.Thread(target=ctx.os.first_video, args=(4,), daemon=True).start()      # once the results page has loaded
    return Result(ok, f"Playing {q} on {pretty(site)}, sir." if ok else f"I couldn't open {pretty(site)}, sir.", {"query": q, "site": site})


@ability("video", "YouTube page keys: fullscreen, exit_fullscreen, skip_ahead, rewind, captions, or first (play the first video on the results page)",
         required={"action": Choice("fullscreen", "exit_fullscreen", "skip_ahead", "rewind", "captions", "first")}, examples=[("make it fullscreen", 'video(action="fullscreen")')], phrases=VIDEO_PHRASES)
def video(args, ctx):
    act = args["action"]
    if act == "first":
        ok = ctx.os.first_video(0)
        return Result(ok, "Playing the first video, sir." if ok else "I can't see a YouTube results page, sir.")
    vk, shift, say = VIDEO[act]
    front = ctx.os.front() if hasattr(ctx.os, 'front') else ('', '')
    if front[0] in ('msedge', 'chrome') and re.search(r'- YouTube(?: - .*)?$', front[1] or '') and hasattr(ctx.os, 'front_keys'):
        ok = ctx.os.front_keys(vk, shift)          # the focused YouTube tab, never another one
    else:
        ok = ctx.os.video_key(vk, shift)
    return Result(ok, say if ok else "I can't see YouTube open, sir.")


@ability("tab_close", "close browser tabs: which = this (the one in front), first, second, third, last or all; site if they named one",
         required={"which": Choice("this", "first", "second", "third", "last", "all")}, optional={"site": Name(kinds=("site",))},
         examples=[("shut the second amazon tab", 'tab_close(which="second", site="amazon")'), ("kill this tab", 'tab_close(which="this")')])
def tab_close(args, ctx):
    which, site = args["which"], args.get("site")
    report=ctx.os.tab_action(which,tab_pattern(site))
    n=len(report['done'])
    what = f"{pretty(site)} tab" if site else "tab"
    if not report['ok'] and n:
        return Result(False,f"Closed {n} tabs, sir. {report['message']}",{'closed':n},exact=True)
    if not n:
        detail=report.get('message','')
        return Result(False, detail if detail and detail!='No matching tab.' else f"I can't find {'a' if which in ('this', 'all') else 'that'} {what} to close, sir.", {"closed": 0},exact=True)
    return Result(True, f"Closing {'all ' + what + 's' if which == 'all' else 'the ' + (which + ' ' if which != 'this' else '') + what}, sir.", {"closed": n})
