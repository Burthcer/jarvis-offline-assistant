"""The reply (plan 13.7): the AI rewords the true `plain` sentence in the butler voice; a checker refuses wording that changes a name or number,
swaps next/previous, on/off, flips success or adds a claim; then `plain` is spoken. The action has already happened: nothing here can change it."""
import logging
import re

log = logging.getLogger("jarvis3.engine")
RULES = ("You are Jarvis, a calm, polished British butler. Each message says what the user said and what REALLY HAPPENED. Say what happened in fresh words, "
         "in ONE short sentence, as Jarvis, addressing the user as sir. Keep every name and number exactly. Say nothing that did not happen. "
         "No advice, no questions, no offers, nothing extra.")
SHOTS = [("open netflix", "Opening Netflix, sir.", "Netflix coming up, sir."),
         ("a ten second timer", "Timer set: 10 second timer, sir.", "Ten seconds on the clock, sir."),
         ("skip", "Next one, sir.", "Skipping ahead, sir."),
         ("quieter", "Volume down, sir.", "A little quieter, sir."),
         ("close teams", "I'm afraid I can't close Teams, sir.", "I'm sorry, sir, Teams refuses to close."),
         ("pause it", "Nothing is playing that I can control, sir.", "Nothing seems to be playing, sir.")]
OPPOSITES = [("next", "previous"), ("previous", "next"), ("up", "down"), ("down", "up"), ("loud", "quiet"), ("quiet", "loud"), ("mut", "unmut"), ("unmut", "mut"),
             ("open", "clos"), ("clos", "open"), ("play", "paus"), ("paus", "play"), ("start", "stop"), ("stop", "start"), ("cancel", "resum"), ("resum", "cancel")]
NEG = re.compile(r"\b(couldn't|can't|cannot|isn't|aren't|haven't|hasn't|didn't|wasn't|won't|still|nothing|unable|afraid|unfortunately|not|failed|no)\b", re.I)
CLAIM = re.compile(r"\b(also|additionally|furthermore|meanwhile|anything else|shall i|would you like|let me know|dev)\b|\?|\n", re.I)
W2N = {w: str(i) for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
W2N.update({"thirty": "30", "forty": "40", "fifty": "50", "sixty": "60", "half": "0.5", "hundred": "100"})
W2N.pop("one")  # "the previous one" is not a number


def stem(w):
    return re.sub(r"(ing|ed|es|s|e)$", "", w) if len(w) >= 4 else w


def numbers(s):
    return sorted(W2N.get(t, t) for t in re.findall(r"\d+(?:\.\d+)?|[a-z]+", s.lower()) if t in W2N or t[0].isdigit())


def faithful(plain, wording, ok, names=()):
    """None if the wording can be trusted, else the reason it can't."""
    if not wording or len(wording.split()) > 22:
        return "empty or long"
    if CLAIM.search(wording):
        return "adds something"
    if numbers(plain) != numbers(wording):
        return "numbers differ"
    sq = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
    if any(sq(n) not in sq(wording) for n in names):
        return "name missing"
    P, W = {stem(w) for w in re.findall(r"[a-z']+", plain.lower())}, {stem(w) for w in re.findall(r"[a-z']+", wording.lower())}
    for a, b in OPPOSITES:
        if a in P and b in W and b not in P and a not in W:
            return f"swapped {a}/{b}"
    if bool(NEG.search(plain)) != bool(NEG.search(wording)):
        return "success and failure mixed up"
    return None


def phrase(ai, said, plain, ok, names=()):
    """-> (text to say, how: 'ai' or the reason plain was used)."""
    msgs = [{"role": "system", "content": RULES}]
    for u, d, r in SHOTS:
        msgs += [{"role": "user", "content": f"User said: {u}\nWHAT HAPPENED: {d}"}, {"role": "assistant", "content": r}]
    msgs.append({"role": "user", "content": f"User said: {said[:200]}\nWHAT HAPPENED: {plain[:300]}"})
    try:
        out = ai.complete(msgs, temperature=0.8, max_tokens=40).strip().split("\n")[0].strip()
    except Exception as e:
        log.error("reply wording failed: %s", e)
        return plain, f"error: {e}"
    why = faithful(plain, out, ok, names)
    if why:
        log.info("wording refused (%s): %r for %r", why, out, plain)
        return plain, why
    return out, "ai"
