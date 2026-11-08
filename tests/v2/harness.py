"""The V2 harness: the owner's 265 labelled sentences through the WHOLE app (resolver, real AI, abilities, fake PC), strict grading.
Run: py -3.12 tests/v2/harness.py [--limit N] [--label name] [--model path.gguf]
Tuning rule (kept from the spike): only look at failures with an EVEN index; odd index stays held out.
Grades each sentence three ways: plan (ability + arguments), effect (the fake PC and the timer list really changed), reply (non-empty, names the target).
Sentences whose expected ability isn't built yet are listed as 'later phase' and not counted against Jarvis."""
import difflib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path[:0] = [ROOT, HERE]
from gold_text import ALL  # noqa: E402

from jarvis.store import Store  # noqa: E402
from jarvis2.ai import AI, DEFAULT_MODEL  # noqa: E402
from jarvis2.app import App  # noqa: E402
from jarvis2.osapi import Fake  # noqa: E402
from jarvis2.registry import ABILITIES  # noqa: E402

OUT = os.path.join(ROOT, "data", "gold", "results")
CLOCK = datetime(2026, 10, 31, 10, 0)  # Saturday, as in the spike's situation line


class Speech:
    stopped = 0

    def tune(self, change):
        return True

    def stop(self):
        self.stopped += 1


def fresh(ai, extra_timers=()):
    """A new PC, a new timer list, a new app: every sentence starts the same. extra_timers = lengths in seconds a sentence talks about."""
    store = Store(":memory:")
    for secs in dict.fromkeys([60, 180, *extra_timers]):
        label = " and ".join(f"{v}-{u}" for v, u in ((secs // 3600, "hour"), (secs % 3600 // 60, "minute"), (secs % 60, "second")) if v)
        store.add(label, CLOCK + timedelta(seconds=secs), kind="timer")
    store.add("maths test", CLOCK + timedelta(days=1, hours=7), "reminder")        # tomorrow 5 pm
    store.add("check linkedin", CLOCK + timedelta(days=1, hours=-1), "reminder")   # tomorrow 9 am
    store.add("my college email is x@y.edu", None, "note")
    store.add("my locker code is 4512", None, "note")
    os_ = Fake()
    app = App(os_, store, ai, speech=Speech(), clock=lambda: CLOCK, natural=isinstance(ai, AI) and "--plain" not in sys.argv)
    app.set_mic = lambda on: True
    return app, os_, store


def run_one(app, text, ctx):
    if ctx:
        u, _, a = ctx.partition(" | Jarvis: ")
        app.history.append({"at": CLOCK, "said": u.removeprefix("User: "), "ability": ["ctx"], "reply": a, "ok": True})
    return app.handle(text)


def as_result(rep):
    """Reply -> the dict shape the grader knows."""
    calls = []
    for c, _ in rep.results:
        d = {"a": c.ability, **{k: (c.spoken.get(k, v) if hasattr(v, "isoformat") else v) for k, v in c.args.items()}}   # a time is graded by the words, not the date
        if c.ability == "timer_set":
            d["seconds"] = d.pop("duration")
        if c.ability=='browser_tabs' and c.args.get('action')=='close' and c.args.get('selector') in ('first','second','third','last'):
            d={'a':'tab_close','which':c.args['selector']} # same effect, newer verified adapter
        calls.append(d)
    if rep.plan.kind == "act" and not rep.results:  # asked something half way
        return {"kind": "ask", "calls": [], "say": rep.text}
    return {"kind": rep.plan.kind, "calls": calls, "say": rep.text, "source": rep.plan.source}


def effect_ok(rep, os_, store):
    """The fake PC and the timer list must really show what the plan says."""
    for c, r in rep.results:
        if c.ability in ("repeat", "undo", "recap"):  # their 'last thing' exists only as words in these sentences
            continue
        if not r.ok:
            return False
        if r.facts.get("changed") is False or r.facts.get("silent"):
            continue
        a, t = c.ability, c.args.get("target")
        if a in ("repeat", "undo", "recap"):  # their 'last thing' exists only as words in these sentences
            continue
        if a in ("open", "close", "focus") and (a, t) not in [(x[0], x[1]) for x in os_.log]:
            return False
        if a == "media" and ("media", c.args["action"]) not in os_.log:
            return False
        if a == "volume" and not any(x[0] in ("volume", "mute", "app_volume") for x in os_.log):
            return False
        if a == "timer_set":
            from jarvis.actions import label_secs
            if c.args["duration"] not in [label_secs(x["text"]) for x in store.all_timers()]:
                return False
    return True


def reply_ok(rep):
    if all(r.facts.get("silent") for _, r in rep.results) and rep.results:
        return True
    if not rep.text:
        return False
    sq = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    if rep.how not in ("ai", "plain"):
        return rep.text == rep.plain  # refused wording must have fallen back to the true sentence
    return all(sq(c.args["target"]) in sq(rep.text) for c, _ in rep.results if c.ability in ("open", "close", "focus"))


# ---------- scoring (from the stage 1 experiments) ----------
CANON = {"google chrome": "chrome", "microsoft edge": "edge", "whatsapp - shortcut": "whatsapp", "chat gpt": "chatgpt", "gpt": "chatgpt", "explorer": "file explorer", "files": "file explorer",
         "whisper flow": "wispr flow", "whisper no pro": "wisperno pro", "wisperno": "wisperno pro", "anti gravity": "antigravity", "quickshare": "quick share", "armory crate": "armoury crate",
         "antigravity ide": "antigravity", "claude code": "claude"}


def words(s):
    s = str(s).lower().replace(" at the rate ", "@")
    return set(re.findall(r"[a-z0-9@.]+", s)) - {"the", "a", "an", "my", "to", "for", "i", "that", "is", "of", "it", "at", "on", "by", "have"}


def norm_when(s):
    return re.sub(r"\s+", "", re.sub(r"\b(at|by|on)\b", " ", s.lower())).replace(".", "")


def targets_equal(want, got):
    w, g = CANON.get(want, want), CANON.get(str(got).lower(), str(got).lower())
    return w == g or w.replace(" ", "") == g.replace(" ", "")


def call_ok(want, got):
    if want["a"] != got.get("a"):
        return False
    if want["a"] == "timer_control" and got.get("action") == "status" and want["action"] == "status":
        return True
    for k, v in want.items():
        if k == "a":
            continue
        g = got.get(k)
        if k in ("target", "site", "app"):
            ok = g is not None and targets_equal(v, g)
        elif k in ("query", "text", "item"):
            a, b = words(v), words(g or "")
            ok = len(a & b) >= 0.6 * max(len(a), 1) and len(b - a) <= max(1, len(a) * 0.5)
        elif k == "when":
            ok = bool(g) and norm_when(g) == norm_when(v)
        elif k == "which":
            ok = v == "only" and g in (None, "", "only") or str(g) == str(v)
        elif k == "count":
            ok = bool(g) == bool(v)
        else:
            ok = g == v or str(g) == str(v)
        if not ok:
            return False
    for k in ("site", "browser", "app", "count", "level", "day"):  # must not add a site, browser or app nobody named
        if got.get(k) not in (None, "", 0, 1, False) and k not in want:
            return False
    return True


def calls_ok(want, got):
    got = list(got)
    if len(want) != len(got):
        return False
    for w in want:
        for g in got:
            if call_ok(w, g):
                got.remove(g)
                break
        else:
            return False
    return True


def grade(expected, opts, r):
    kind, calls = r.get("kind"), r.get("calls") or []
    for e in (expected, opts.get("alt", None)):
        if e is None:
            continue
        if e == "ask" and kind == "ask":
            return "right"
        if e == [] and kind in ("chat", "ask", "ignore") and not calls:
            return "right"
        if isinstance(e, list) and e and kind == "act" and calls_ok(e, calls):
            return "right"
    if not calls or kind != "act":
        return "asked" if kind == "ask" else "did_nothing"
    return "false_action" if expected == [] or expected == "ask" else "wrong_action"


def in_scope(expected, opts):
    """Can this sentence be graded now? Every ability it needs must be built."""
    for e in (expected, opts.get("alt")):
        if isinstance(e, list) and e and not all(c["a"] in ABILITIES for c in e):
            return False
    return True


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    label = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else "run"
    model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else DEFAULT_MODEL
    ai = AI(model)
    t0 = time.time()
    ai.load()
    print(f"loaded {time.time() - t0:.1f}s", os.popen("nvidia-smi --query-gpu=memory.used,temperature.gpu --format=csv,noheader").read().strip())
    rows, times = [], []
    for i, (text, exp, opts) in enumerate((ALL[:limit] if limit else ALL)):
        wants = [c["which"] for e in (exp, opts.get("alt")) if isinstance(e, list) for c in e if c.get("a") == "timer_control" and str(c.get("which", "")).isdigit()]
        if any(c.get("a") == "timer_control" for e in (exp, opts.get("alt")) if isinstance(e, list) for c in e):  # "the 25 minute timer": the sentence assumes it exists
            wants += [int(n) * {"s": 1, "m": 60, "h": 3600}[u[0]] for n, u in re.findall(r"(\d+)[ -]*(sec|min|hour)", text.lower())]
        app, os_, store = fresh(ai, [int(w) for w in wants])
        t1, rep = time.perf_counter(), None
        try:
            rep = run_one(app, text, opts.get("ctx"))
            res = as_result(rep)
            g = grade(exp, opts, res)
            eff = effect_ok(rep, os_, store) if g == "right" and res["calls"] else None
            rok = reply_ok(rep) if g == "right" and res["calls"] else None
            err = rep.error
        except Exception as ex:
            res, g, eff, rok, err = {"kind": "crash", "calls": [], "say": repr(ex)[:200]}, "crash", None, None, repr(ex)[:200]
        ms = round((time.perf_counter() - t1) * 1000)
        if res.get("source") == "ai":
            times.append(ms)
        scope = in_scope(exp, opts)
        rows.append({"i": i, "t": text, "e": exp, "o": opts, "r": res, "g": g if scope else "later", "effect": eff, "reply_ok": rok, "scope": scope, "how": getattr(rep, 'how', ''), "ms_reply": getattr(rep, 'ms_reply', 0), "ms": ms, "err": err})
        if '--cool' in sys.argv and i%25==24:time.sleep(1)
    os.makedirs(OUT, exist_ok=True)
    json.dump(rows, open(os.path.join(OUT, f"v2_{label}.json"), "w", encoding="utf-8"), indent=0, default=str)

    def cnt(sel):
        sub = [x for x in rows if sel(x) and x["scope"]]
        c = Counter(x["g"] for x in sub)
        return f"{c['right']}/{len(sub)} " + " ".join(f"{k}={v}" for k, v in sorted(c.items()) if k != "right")
    print(label, "IN SCOPE", cnt(lambda x: True), "| later phase:", sum(not x["scope"] for x in rows))
    print(" sure-only", cnt(lambda x: not x["o"].get("u")))
    print(" tuning(even)", cnt(lambda x: x["i"] % 2 == 0), "| held-out(odd)", cnt(lambda x: x["i"] % 2 == 1))
    acted = [x for x in rows if x["scope"] and x["g"] == "right" and x["r"]["calls"]]
    print(f" effect ok {sum(1 for x in acted if x['effect'])}/{len(acted)}  reply ok {sum(1 for x in acted if x['reply_ok'])}/{len(acted)}  crashes {sum(x['g'] == 'crash' for x in rows)}  model-output errors logged {sum(bool(x["err"]) for x in rows)}")
    how = Counter(x['how'] for x in rows if x.get('how'))
    rw = sorted(x['ms_reply'] for x in rows if x.get('how') == 'ai')
    print(' reply wording:', dict(how), f'median {rw[len(rw) // 2]} ms' if rw else '')
    times.sort()
    if times:
        print(f" AI turns: {len(times)}  ms median {times[len(times) // 2]}  p95 {times[int(len(times) * .95)]}  prompt tokens {ai.prompt_tokens}")
    print(" instant:", sum(1 for x in rows if x['r'].get('source') in ('phrase', 'shape')), "of", len(rows))
    import psutil
    print(f" this process RAM {psutil.Process().memory_info().rss / 2**30:.2f} GB")
    print(" gpu", os.popen("nvidia-smi --query-gpu=memory.used,temperature.gpu,power.draw --format=csv,noheader").read().strip())
    ai.unload()


if __name__ == "__main__":
    main()
