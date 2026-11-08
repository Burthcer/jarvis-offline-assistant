"""Pull a date/time out of a sentence: parse_when("buy milk tomorrow at 5pm", now) -> ("buy milk", datetime)."""
import re
from datetime import datetime, timedelta

MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
DAYS = "monday tuesday wednesday thursday friday saturday sunday".split()
_M = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_ORD = r"(?:st|nd|rd|th)?"
PARTS = {"morning": 9, "afternoon": 15, "evening": 18, "night": 21, "tonight": 21}

UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
ORDS = {w: i + 1 for i, w in enumerate("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth".split())}
ORDS.update({"twentieth": 20, "thirtieth": 30})
_NUMW = "|".join(sorted([*UNITS, *TENS, *ORDS], key=len, reverse=True))
_NUMRUN = re.compile(r"\b(?:%s)(?:[\s-]+(?:%s))*\b" % (_NUMW, _NUMW), re.I)
_AFTER_OK = re.compile(r"(?:am|pm|a\.?m|p\.?m|o'?clock|minutes?|mins?|hours?|hrs?|days?|weeks?|st|nd|rd|th)\b", re.I)
_MONTH_WORD = re.compile(_M + r"\b", re.I)


def _suffix(n):
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _words_to_numbers(s):
    """'at five thirty pm' -> 'at 5:30 pm'; 'twenty fourth november' -> '24th november'. Only in time-like contexts."""
    def sub(m):
        toks = re.split(r"[\s-]+", m[0].lower())
        vals, i = [], 0
        while i < len(toks):
            t = toks[i]
            if t in TENS:
                v, ordinal = TENS[t], False
                if i + 1 < len(toks) and 1 <= (UNITS.get(toks[i + 1]) or ORDS.get(toks[i + 1]) or 0) <= 9:
                    nxt = toks[i + 1]
                    v, ordinal, i = v + (UNITS.get(nxt) or ORDS[nxt]), nxt in ORDS, i + 1
                vals.append((v, ordinal))
            else:
                vals.append((UNITS[t], False) if t in UNITS else (ORDS[t], True))
            i += 1
        before = s[:m.start()].split()[-1:] or [""]
        before = before[0].lower().strip(",.")
        after = s[m.end():].lstrip()
        ordinal = any(o for _, o in vals)
        if ordinal:
            if not (_MONTH_WORD.match(after) or re.match(r"of\b", after, re.I) or _MONTH_WORD.match(before) or before == "the"):
                return m[0]
            return " ".join(f"{v}{_suffix(v)}" if o else str(v) for v, o in vals)
        if not (before in ("at", "in", "past", "to", "on", "by", "of", "for", "within", "after", "until", "till") or _AFTER_OK.match(after)):
            return m[0]
        nums = [v for v, _ in vals]
        if len(nums) == 2 and before in ("at", "past", "to") and 1 <= nums[0] <= 12 and 10 <= nums[1] <= 59:
            return f"{nums[0]}:{nums[1]:02d}"
        return " ".join(map(str, nums))
    return _NUMRUN.sub(sub, s)


def normalize(text):
    """Make speech-to-text style wording ('5 p.m.', 'five thirty', 'half past 4', 'noon') look like plain digits."""
    s = _words_to_numbers(text)
    s = re.sub(r"(\d)\s*([ap])\.\s?m\b\.?", r"\1\2m", s, flags=re.I)
    # speech-to-text writes "8.30" for half past eight; "at 8.30" or "8.30 am", never plain decimals like "1.5 hours"
    s = re.sub(r"\b(at\s+)(\d{1,2})\.([0-5]\d)\b", r"\1\2:\3", s, flags=re.I)
    s = re.sub(r"\b(\d{1,2})\.([0-5]\d)(\s*[ap]m\b)", r"\1:\2\3", s, flags=re.I)
    s = re.sub(r"\b(on |to )?the (\d{1,2})\s*[.!?]?\s*$", lambda m: f"{m[1] or ''}the {m[2]}{_suffix(int(m[2]))}" if 1 <= int(m[2]) <= 31 else m[0], s, flags=re.I)  # "move it to the 26."
    s = re.sub(r"\bhalf past (\d{1,2})\b", r"\1:30", s, flags=re.I)
    s = re.sub(r"\bquarter past (\d{1,2})\b", r"\1:15", s, flags=re.I)
    s = re.sub(r"\bquarter to (\d{1,2})\b", lambda m: f"{(int(m[1]) - 2) % 12 + 1}:45", s, flags=re.I)
    s = re.sub(r"\bnoon\b", "12 pm", s, flags=re.I)
    s = re.sub(r"\bmidnight\b", "12 am", s, flags=re.I)
    s = re.sub(r"(?:\bat\s+)?\b(\d{1,2})(?::(\d{2}))?\s*o['’]?clock\b", lambda m: f"at {m[1]}" + (f":{m[2]}" if m[2] else ""), s, flags=re.I)
    return s


def _cut(s, m):
    return s[:m.start()] + " " + s[m.end():]


def parse_when(text, now):
    try:
        return _parse(normalize(text), now)
    except (ValueError, OverflowError):  # absurd numbers ("in 99999999999 hours"): no time found
        return _tidy(text), None


def _parse(text, now):
    s = " " + text + " "
    day, hour, minute, shifted = None, None, 0, False

    m = re.search(r"\bin\s+(\d+)\s*(?:hours?|hrs?)\s*(?:and\s+)?(\d+)\s*(?:minutes?|mins?)\b", s, re.I)
    if m:
        return _tidy(_cut(s, m)), (now + timedelta(hours=int(m[1]), minutes=int(m[2]))).replace(second=0, microsecond=0)

    m = re.search(r"\bin\s+(\d+(?:\.\d+)?|an?|half an?)\s*(minute|min|hour|hr|day|week)s?\b", s, re.I)
    if m:
        n = {"a": 1, "an": 1}.get(m[1].lower(), 0.5 if m[1].lower().startswith("half") else None)
        n = float(m[1]) if n is None else n
        unit = {"min": "minutes", "minute": "minutes", "hr": "hours", "hour": "hours", "day": "days", "week": "weeks"}[m[2].lower()]
        due = (now + timedelta(**{unit: n})).replace(second=0, microsecond=0)
        return _tidy(_cut(s, m)), due

    m = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", s, re.I)
    if m and 1 <= int(m[1]) <= 12 and int(m[2] or 0) < 60:
        hour, minute = int(m[1]) % 12 + (12 if m[3].lower() == "pm" else 0), int(m[2] or 0)
        s = _cut(s, m)
    else:  # invalid like "13pm" is left alone, so no time is found and Jarvis asks
        m = re.search(r"\bat\s+(\d{1,2})(?::(\d{2}))?\b", s, re.I)
        if m and int(m[1]) <= 23 and int(m[2] or 0) < 60:
            hour, minute = int(m[1]), int(m[2] or 0)
            if 1 <= hour <= 6 and not m[1].startswith("0"):  # ponytail: bare "at 5" means 5 pm; "05:00", "5am" or "in the morning" override
                hour, shifted = hour + 12, True
            s = _cut(s, m)

    m = re.search(r"\b(?:in the |this |at )?(morning|afternoon|evening|night|tonight)\b", s, re.I)
    if m:
        p = m[1].lower()
        if hour is None:
            hour = PARTS[p]
        elif p == "morning" and shifted:
            hour -= 12
        elif p != "morning" and 1 <= hour < 12:
            hour += 12
        if p == "tonight":
            day = now.date()
        s = _cut(s, m)

    m = re.search(r"\bday after tomorrow\b", s, re.I)
    if m:
        day = (now + timedelta(days=2)).date(); s = _cut(s, m)
    m = re.search(r"\btomorrow\b", s, re.I)
    if m:
        day = (now + timedelta(days=1)).date(); s = _cut(s, m)
    m = re.search(r"\btoday\b", s, re.I)
    if m:
        day = now.date(); s = _cut(s, m)

    m = re.search(r"\b(?:on\s+)?(?:the\s+)?(\d{1,2})" + _ORD + r"\s+(?:of\s+)?" + _M + r"\b", s, re.I) \
        or re.search(r"\b(?:on\s+)?" + _M + r"\s+(\d{1,2})" + _ORD + r"\b", s, re.I)
    if m:
        a, b = m[1], m[2]
        d, mon = (int(a), b) if a.isdigit() else (int(b), a)
        for year in range(now.year, now.year + 9):  # 29 feb waits for the next leap year; 30 feb never matches
            try:
                found = datetime(year, MONTHS.index(mon[:3].lower()) + 1, d).date()
            except ValueError:
                continue
            if found >= now.date():
                day, s = found, _cut(s, m)
                break

    m = re.search(r"\b(?:on\s+)?the\s+(\d{1,2})(?:st|nd|rd|th)\b", s, re.I) if day is None else None
    if m:  # "the 26th" = next time the 26th comes round
        for k in range(14):
            y, mo = divmod(now.month - 1 + k, 12)
            try:
                found = datetime(now.year + y, mo + 1, int(m[1])).date()
            except ValueError:
                continue
            if found >= now.date():
                day, s = found, _cut(s, m)
                break

    m = re.search(r"\b(?:on\s+|next\s+|this\s+|coming\s+)?(" + "|".join(DAYS) + r")\b", s, re.I)
    if m and day is None:
        ahead = (DAYS.index(m[1].lower()) - now.weekday()) % 7 or 7
        day = (now + timedelta(days=ahead)).date(); s = _cut(s, m)

    if day is None and hour is None:
        return _tidy(s), None
    defaulted = hour is None
    if hour is None:
        hour = 9
    if day is None:
        day = now.date()
        if datetime.combine(day, datetime.min.time()).replace(hour=hour % 24, minute=minute) <= now:
            day += timedelta(days=1)
    due = datetime(day.year, day.month, day.day, hour % 24, minute)
    if defaulted and due <= now:  # "today" with no time, after 9am: remind in an hour rather than in the past
        due = (now + timedelta(hours=1)).replace(second=0, microsecond=0)
    return _tidy(s), due


def _tidy(s):
    """What's left after the time is cut out -> just the task: ', for , I have to do my lab' -> 'do my lab'."""
    s = re.sub(r"\s*(?:,\s*)+", ", ", re.sub(r"\s+", " ", s)).strip(" ,.!?;:")
    prev = None
    while s != prev:  # peel repeatedly: "that I have to do X" -> "I have to do X" -> "do X"
        prev = s
        s = re.sub(r"^(?:to|that|about|of|and|for|so|then)\b[\s,]*", "", s, flags=re.I)
        s = re.sub(r"^(?:i|we) (?:have|need|want|must|got|ought) to\s+|^i(?:'ve| have) got to\s+|^i gotta\s+|^i should\s+|^i must\s+", "", s, flags=re.I)
        s = re.sub(r"^i have (an? |the )?", "", s, flags=re.I) if len(s) > 12 else s
        s = re.sub(r"(\s+(on|at|by|in|for|to|the))+$", "", s, flags=re.I).strip(" ,.!?;:")
    return s


def fmt(due, now):
    if due is None:
        return "no time"
    d = (due.date() - now.date()).days
    word = {0: "today", 1: "tomorrow", -1: "yesterday"}.get(d) or due.strftime("%a %d %b")
    return f"{word} {due.strftime('%I:%M %p').lstrip('0').lower()}"
