"""search, play_on, video (YouTube keys), tab_close. Pages open in the site's own browser (Edge unless it's one of Chrome's three); a search with no site is Google in Edge."""
import threading
from urllib.parse import quote_plus

from jarvis.actions import SITES as V1_SITES, TAB

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

def tab_route(text):
    import re
    match = re.fullmatch(r'(close|closed|focus(?: on)?|switch to|select|go to) (?:the )?(.+?) tabs?',text.strip(' .!?'),re.I)
    if match and match[2].lower() not in ('all','this'):
        if match[1].lower() in ('close','closed'):
            from ..browser_tabs import ORDINALS
            tokens = re.findall(r'\w+',match[2].lower())
            if any(t not in ORDINALS and t not in ('and','the','last') and not re.fullmatch(r'\d+(?:st|nd|rd|th)?',t) for t in tokens):
                return None  # keep existing site-scoped tab requests intact
        return [('browser_tabs',{'action':'close' if match[1].lower() in ('close','closed') else 'focus','selector':match[2]})]
    return None


@ability('tab_focus', 'focus a browser tab by its position',
         required={'which': Choice('first', 'second', 'third', 'fourth', 'fifth', 'last')},
         patterns=[(r'(?:focus(?: on)?|switch to|go to|select) (?:the )?(first|second|third|fourth|fifth|last) tab', lambda m: {'which': m[1]})])
def tab_focus(args, ctx):
    ok = ctx.os.focus_tab(args['which'])
    return Result(ok, f"Switched to the {args['which']} tab, sir." if ok else 'I could not select that browser tab, sir.', exact=True)

VIDEO = {"fullscreen": (0x46, False, "Full screen, sir."), "skip_ahead": (0x4C, False, "Skipping ahead, sir."), "rewind": (0x4A, False, "Going back, sir."),
         "captions": (0x43, False, "Captions switched, sir.")}


def tab_pattern(site):
    import re
    return None if not site else TAB.get(site, r"\b%s\b" % re.escape(site))


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


@ability("video", "YouTube page keys: fullscreen, skip_ahead, rewind, captions, or first (play the first video on the results page)",
         required={"action": Choice("fullscreen", "skip_ahead", "rewind", "captions", "first")}, examples=[("make it fullscreen", 'video(action="fullscreen")')])
def video(args, ctx):
    act = args["action"]
    if act == "first":
        ok = ctx.os.first_video(0)
        return Result(ok, "Playing the first video, sir." if ok else "I can't see a YouTube results page, sir.")
    vk, shift, say = VIDEO[act]
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
