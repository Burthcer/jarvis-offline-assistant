"""30+ multi-turn conversations through the whole app: real AI, natural replies on, fake PC. Every turn is checked three ways:
the plan (ability + arguments, or a question, or no action), the real state afterwards (fake PC, timer list), and the reply (names what it should, says "sir"-style truth).
Run: py -3.12 tests/v2/conversations.py [--plain]   -> failures with detail, then counts.
Add a conversation = add one line to CONVOS. Don't tune on these by copying their sentences into the prompt."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(os.path.dirname(HERE)), HERE]
from harness import calls_ok, fresh  # noqa: E402

from jarvis2.ai import AI, DEFAULT_MODEL  # noqa: E402


def T(text, act=None, ask=False, has=(), state=None, nots=()):
    """act: expected calls [{"a":..}] (None = must not act); ask: must ask a question; has: words the reply must contain; state: lambda(os, store) -> bool."""
    return dict(text=text, act=act, ask=ask, has=has, state=state, nots=nots)


def op(*t): return [{"a": "open", "target": x} for x in t]
def cl(*t): return [{"a": "close", "target": x} for x in t]
def ran(os_, name): return name in os_._running
def mins(store): return sorted(r["text"] for r in store.all_timers())
def paused(store): return sorted(r["text"] for r in store.all_timers() if r["status"] == "paused")


CONVOS = {
    "open then close it": [T("open notepad", op("notepad"), has=["notepad"], state=lambda o, s: ran(o, "notepad")),
                           T("close it", cl("notepad"), has=["notepad"], state=lambda o, s: not ran(o, "notepad"))],
    "close then again": [T("close discord", cl("discord"), state=lambda o, s: not ran(o, "discord")),
                         T("open discord", op("discord"), state=lambda o, s: ran(o, "discord")),
                         T("do that again", [{"a": "repeat"}], state=lambda o, s: ran(o, "discord"))],
    "pause play next": [T("pause", [{"a": "media", "action": "pause"}], state=lambda o, s: not o.playing["playing"]),
                        T("play", [{"a": "media", "action": "play"}], state=lambda o, s: o.playing["playing"]),
                        T("next song", [{"a": "media", "action": "next"}])],
    "volume then undo": [T("volume 30", [{"a": "volume", "action": "set", "level": 30}], has=["30"], state=lambda o, s: o.vol == 30),
                         T("turn it up a bit", [{"a": "volume", "action": "up"}], state=lambda o, s: o.vol == 40),
                         T("undo that", [{"a": "undo"}], state=lambda o, s: o.vol == 30)],
    "mute twice": [T("mute", [{"a": "volume", "action": "mute"}], state=lambda o, s: o.mute),
                   T("mute", [{"a": "volume", "action": "mute"}], has=["already"], state=lambda o, s: o.mute),
                   T("unmute", [{"a": "volume", "action": "unmute"}], state=lambda o, s: not o.mute)],
    "set a timer then status": [T("set a timer for 2 minutes", [{"a": "timer_set", "seconds": 120}], has=["2"], state=lambda o, s: "2-minute" in mins(s)),
                                T("how much time is left on my timers", [{"a": "timer_control", "action": "status"}], has=["2 minute", "1 minute", "3 minute"])],
    "cancel one of two": [T("cancel the timer", ask=True, has=["which"]),
                          T("the one minute one", [{"a": "timer_control", "action": "cancel", "which": "60"}], state=lambda o, s: mins(s) == ["3-minute"])],
    "pause and resume": [T("pause the 3 minute timer", [{"a": "timer_control", "action": "pause", "which": "180"}], state=lambda o, s: paused(s) == ["3-minute"]),
                         T("resume it", [{"a": "timer_control", "action": "resume"}], state=lambda o, s: paused(s) == [])],
    "cancel all": [T("cancel all timers", [{"a": "timer_control", "action": "cancel", "which": "all"}], state=lambda o, s: mins(s) == []),
                   T("any timers left", [{"a": "timer_control", "action": "status"}], has=["no timers"])],
    "pause both": [T("pause both timers", [{"a": "timer_control", "action": "pause", "which": "all"}], state=lambda o, s: len(paused(s)) == 2),
                   T("resume both timers", [{"a": "timer_control", "action": "resume", "which": "all"}], state=lambda o, s: paused(s) == [])],
    "two opens then recap": [T("open chrome and discord", op("chrome", "discord")),
                             T("what did you just do", [{"a": "recap"}], has=["chrome"])],
    "misheard name: one clear match acts": [T("open prome", op("chrome"), has=["chrome"]), T("open jamin", op("gemini"), has=["gemini"])],
    "misheard name: sound-alike, not a running app": [T("open whisper", op("wisperno pro"))],
    "undo an open": [T("open calculator", op("calculator"), state=lambda o, s: ran(o, "calculator")),
                     T("undo that", [{"a": "undo"}], state=lambda o, s: not ran(o, "calculator"))],
    "small talk": [T("hello", None), T("thank you", None, nots=["opening", "closing"])],
    "stop talking": [T("shut up", [{"a": "stop_talking"}], state=lambda o, s: True)],
    "one app quieter": [T("make edge quieter", [{"a": "volume", "action": "down", "app": "edge"}], state=lambda o, s: o.app_vol["edge"] == 90)],
    "one app to a level": [T("set the volume of edge to 40", [{"a": "volume", "action": "set", "level": 40, "app": "edge"}], state=lambda o, s: o.app_vol["edge"] == 40)],
    "one app, no direction": [T("change the volume of edge", ask=True, has=["louder"])],
    "nothing playing": [T("pause", [{"a": "media", "action": "pause"}], has=["nothing"], state=lambda o, s: True)],
    "tabs count": [T("open youtube twice", [{"a": "open", "target": "youtube", "count": 2}], state=lambda o, s: o.log[-1][3] == 2)],
    "odd length": [T("set a timer for 90 seconds", [{"a": "timer_set", "seconds": 90}], state=lambda o, s: "1-minute and 30-second" in mins(s))],
    "timer asks length": [T("set a timer", ask=True, has=["how long"]),
                          T("ten minutes", [{"a": "timer_set", "seconds": 600}], state=lambda o, s: "10-minute" in mins(s))],
    "open asks what": [T("open", ask=True), T("notepad", op("notepad"), state=lambda o, s: ran(o, "notepad"))],
    "close twice": [T("close edge", cl("edge"), state=lambda o, s: not ran(o, "edge")),
                    T("close edge", cl("edge"), has=["isn't"])],
    "noise": [T("so", None), T("um yeah", None)],
    "three things": [T("open whatsapp and close discord and set a timer for a minute", [{"a": "open", "target": "whatsapp"}, {"a": "close", "target": "discord"}, {"a": "timer_set", "seconds": 60}],
                       state=lambda o, s: not ran(o, "discord"))],
    "again with nothing": [T("do that again", [{"a": "repeat"}], has=["yet"])],
    "open then close it (site)": [T("open youtube", op("youtube")), T("close it", cl("youtube"))],
    "timer then undo": [T("ten minute timer", [{"a": "timer_set", "seconds": 600}], state=lambda o, s: "10-minute" in mins(s)),
                        T("undo that", [{"a": "undo"}], state=lambda o, s: "10-minute" not in mins(s))],
    "half volume": [T("volume full", [{"a": "volume", "action": "set", "level": 100}], state=lambda o, s: o.vol == 100),
                    T("set it to half", [{"a": "volume", "action": "set", "level": 50}], state=lambda o, s: o.vol == 50)],
    "louder quieter": [T("turn it up", [{"a": "volume", "action": "up"}], state=lambda o, s: o.vol == 60),
                       T("turn it down", [{"a": "volume", "action": "down"}], state=lambda o, s: o.vol == 50)],
    "ask what it can't do": [T("turn off bluetooth", None, nots=["turned off", "done"])],
    "reminder then list": [T("remind me tomorrow at 6 pm to call mom", [{"a": "reminder_add", "text": "call mom", "when": "tomorrow at 6 pm"}], has=["call mom"],
                             state=lambda o, s: any("call mom" in r["text"] for r in s.db.execute("SELECT * FROM items WHERE kind='reminder'"))),
                           T("what do I have tomorrow", [{"a": "reminder_list", "day": "tomorrow"}], has=["call mom", "maths test"])],
    "change a reminder": [T("change the maths test reminder to a science test", [{"a": "reminder_change", "item": "maths test", "text": "science test"}],
                            state=lambda o, s: [r["text"] for r in s.db.execute("SELECT * FROM items WHERE kind='reminder'")].count("science test") == 1 and len(list(s.db.execute("SELECT * FROM items WHERE kind='reminder'"))) == 2)],
    "cancel the day then undo": [T("cancel all the reminders for tomorrow", [{"a": "reminder_cancel", "day": "tomorrow"}], state=lambda o, s: not list(s.db.execute("SELECT * FROM items WHERE kind='reminder'"))),
                                 T("undo that", [{"a": "undo"}], state=lambda o, s: len(list(s.db.execute("SELECT * FROM items WHERE kind='reminder'"))) == 2)],
    "note then recall": [T("remember my wifi password is purple tiger", [{"a": "note_save", "text": "my wifi password is purple tiger"}]),
                         T("what is my wifi password", [{"a": "note_recall", "query": "wifi password"}], has=["purple tiger"])],
    "spoken email": [T("remember my work email is jane dot doe at the rate acme dot com", [{"a": "note_save", "text": "my work email is jane dot doe at the rate acme dot com"}],
                       state=lambda o, s: any("jane.doe@acme.com" in r["text"] for r in s.db.execute("SELECT * FROM items WHERE kind='note'"))),
                     T("what is my work email", [{"a": "note_recall", "query": "work email"}], has=["jane.doe@acme.com"])],
    "time": [T("what time is it", [{"a": "clock", "what": "time"}], has=["10:00"])],
    "date": [T("what is the date today", [{"a": "clock", "what": "date"}], has=["31 October"])],
    "search": [T("search for banana bread", [{"a": "search", "query": "banana bread"}], state=lambda o, s: "google.com/search?q=banana" in o.log[-1][2]),
               T("search for shoes on amazon", [{"a": "search", "query": "shoes", "site": "amazon"}], state=lambda o, s: "amazon.in" in o.log[-1][2])],
    "play on youtube": [T("play some jazz on youtube", [{"a": "play_on", "query": "jazz", "site": "youtube"}], state=lambda o, s: "youtube.com/results" in o.log[0][2])],
    "voice tune": [T("speak slower", [{"a": "voice_tune", "change": "slower"}], has=["slower"])],
    "shut down": [T("shut down", [{"a": "shut_down"}], has=["goodbye"])],
    "last tab": [T("close the last youtube tab", [{"a": "tab_close", "which": "last", "site": "youtube"}], state=lambda o, s: o.log[0][2] == "last")],
    "screenshot": [T("take a screenshot", [{"a": "screenshot"}], state=lambda o, s: ("screenshot",) in o.log)],
    "learns a word from one correction": [T("open bluebird", ask=True),
                                          T("no I meant chrome", [{"a": "correction", "target": "chrome"}], has=["bluebird", "chrome"], state=lambda o, s: any(x[:2] == ("open", "chrome") for x in o.log)),
                                          T("open bluebird", [{"a": "open", "target": "chrome"}], state=lambda o, s: [x[1] for x in o.log if x[0] == "open"][-1] == "chrome")],
    "learns after a wrong guess": [T("open whisper", [{"a": "open", "target": "whatsapp"}]),
                                   T("no I meant wisperno pro", [{"a": "correction", "target": "wisperno pro"}], state=lambda o, s: any(x[:2] == ("open", "wisperno pro") for x in o.log)),
                                   T("open whisper", [{"a": "open", "target": "wisperno pro"}])],
    "failed open is said": [T("open discord", op("discord"), has=["couldn't"], state=lambda o, s: True)],
}


def main():
    ai = AI(DEFAULT_MODEL if "--model" not in sys.argv else sys.argv[sys.argv.index("--model") + 1])
    ai.load()
    bad, turns, good_turns, full = [], 0, 0, 0
    for name, convo in CONVOS.items():
        app, os_, store = fresh(ai)
        if "plain" in sys.argv[1:] or "--plain" in sys.argv:
            app.natural = False
        if name == "failed open is said":
            os_.fail.add("discord")
        if name == "nothing playing":
            os_.playing = None
        ok_all = True
        for t in convo:
            turns += 1
            rep = app.handle(t["text"])
            got = [{"a": c.ability, **{k: (c.spoken.get(k, v) if hasattr(v, "isoformat") else v) for k, v in c.args.items()}} for c, _ in rep.results]
            for g in got:
                if g["a"] == "timer_set":
                    g["seconds"] = g.pop("duration")
            why = []
            if t["ask"]:
                if rep.plan.kind != "ask":
                    why.append(f"expected a question, got {rep.plan.kind}")
            elif t["act"] is None:
                if got:
                    why.append(f"should not act, did {got}")
            else:
                if not calls_ok(t["act"], got):
                    why.append(f"plan wrong: want {t['act']} got {got} ({rep.plan.kind}: {rep.text[:60]})")
                elif not all(r.ok for _, r in rep.results) and not t["has"] and name not in ("nothing playing", "failed open is said"):
                    why.append("a result failed: " + rep.plain)
            if t["state"] and not t["state"](os_, store):
                why.append("state wrong")
            low = rep.text.lower()
            why += [f"reply lacks '{w}'" for w in t["has"] if w.lower() not in low and w.lower() not in rep.plain.lower()]
            why += [f"reply has '{w}'" for w in t["nots"] if w in low]
            if rep.error:
                why.append("ability error")
            if why:
                ok_all = False
                bad.append(f"[{name}] '{t['text']}' -> {rep.text[:70]!r}: " + "; ".join(why))
            else:
                good_turns += 1
        full += ok_all
    ai.unload()
    print("\n".join(bad))
    print(f"conversations fully right {full}/{len(CONVOS)}; turns right {good_turns}/{turns}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
