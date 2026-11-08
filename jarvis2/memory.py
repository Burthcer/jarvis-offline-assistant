"""Memory (plan 13.8). L1 events, L2 aliases + usage, L3 facts (what he told it: notes live in V1's store; `facts` holds preferences), L4 habits (offers only), L5 routines.
Everything is local, visible (summary()) and deletable. `paused` stops every write that was not asked for outright; corrections, routines and notes are always explicit."""
import json
import os
import sqlite3
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, at TEXT, trigger TEXT, heard TEXT, plan_json TEXT, ability TEXT, args_json TEXT, ok INTEGER, reply TEXT, corrected_by INTEGER, clip_id TEXT);
CREATE TABLE IF NOT EXISTS aliases(heard TEXT PRIMARY KEY, name TEXT, kind TEXT, source TEXT, uses INTEGER, last_at TEXT);
CREATE TABLE IF NOT EXISTS usage(name TEXT, kind TEXT, hour INTEGER, count INTEGER, last_at TEXT, PRIMARY KEY(name, kind, hour));
CREATE TABLE IF NOT EXISTS facts(id INTEGER PRIMARY KEY, key TEXT, value TEXT, source_event INTEGER, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK(id=1), text TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS habits(id INTEGER PRIMARY KEY, pattern TEXT, seen INTEGER, offered_at TEXT, answer TEXT);
CREATE TABLE IF NOT EXISTS routines(name TEXT PRIMARY KEY, steps_json TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS routine_progress(name TEXT PRIMARY KEY, fingerprint TEXT, calls TEXT, cursor INTEGER, state TEXT, updated TEXT);
"""
CONFIRMED = 3           # confirmed successes before a repeated mishearing becomes an alias (one explicit correction is enough)
HABIT_DAYS, HABIT_SEEN = 21, 3


def iso(t):
    return t.isoformat(timespec="seconds")


class Memory:
    def __init__(self, path="data/jarvis2.db", settings_path=None):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.executescript(SCHEMA)
        self.lock = threading.RLock()
        self.settings_path = settings_path
        self.paused = False
        if settings_path and os.path.exists(settings_path):
            try:
                self.paused = bool(json.load(open(settings_path, encoding="utf-8")).get("learning_paused"))
            except (OSError, ValueError):
                pass

    def set_paused(self, on):
        self.paused = on
        if self.settings_path:                      # the same file holds the window's settings: change this one key only
            try:
                cur = json.load(open(self.settings_path, encoding="utf-8"))
            except (OSError, ValueError):
                cur = {}
            cur["learning_paused"] = on
            json.dump(cur, open(self.settings_path, "w", encoding="utf-8"), indent=2)

    def _q(self, sql, *a):
        with self.lock:
            return self.db.execute(sql, a).fetchall()

    def _w(self, sql, *a):
        with self.lock:
            cur = self.db.execute(sql, a)
            self.db.commit()
            return cur

    # ----- L1: every turn -----
    def log_event(self, trigger, heard, plan, results, reply, clip_id=None, at=None):
        first = results[0][0] if results else None
        cur = self._w("INSERT INTO events(at,trigger,heard,plan_json,ability,args_json,ok,reply,clip_id) VALUES(?,?,?,?,?,?,?,?,?)",
                      iso(at or datetime.now()), trigger, heard,
                      json.dumps({"kind": plan.kind, "source": plan.source, "raw_model": plan.raw_model, "error": plan.error}),
                      ",".join(c.ability for c, _ in results) or None, json.dumps([c.args for c, _ in results], default=str) if first else None,
                      int(all(r.ok for _, r in results)) if results else None, reply, clip_id)
        return cur.lastrowid

    def next_id(self):
        return (self._q("SELECT COALESCE(MAX(id),0)+1 FROM events")[0][0])

    def mark_corrected(self, event_id, by):
        self._w("UPDATE events SET corrected_by=? WHERE id=?", by, event_id)

    # ----- L2: usage ranks close names -----
    def usage_add(self, name, kind, now):
        if self.paused:
            return
        self._w("INSERT INTO usage(name,kind,hour,count,last_at) VALUES(?,?,?,1,?) ON CONFLICT(name,kind,hour) DO UPDATE SET count=count+1, last_at=excluded.last_at",
                name, kind, now.hour, iso(now))

    def usage_total(self, name):
        return self._q("SELECT COALESCE(SUM(count),0) FROM usage WHERE name=?", name)[0][0]

    def usage_at(self, name, hour):
        return self._q("SELECT COALESCE(SUM(count),0) FROM usage WHERE name=? AND ABS(hour-?)<=1", name, hour)[0][0]

    # ----- L2: aliases ("prome" means Chrome) -----
    def alias_active(self, heard):
        r = self._q("SELECT name,kind FROM aliases WHERE heard=? AND (source='correction' OR uses>=?)", heard, CONFIRMED)
        return tuple(r[0]) if r else None

    def alias_correct(self, heard, name, kind, now):
        """One explicit correction is enough. Always allowed: he said it outright."""
        self._w("INSERT INTO aliases(heard,name,kind,source,uses,last_at) VALUES(?,?,?,'correction',1,?) ON CONFLICT(heard) DO UPDATE SET name=excluded.name, kind=excluded.kind, source='correction', uses=uses+1, last_at=excluded.last_at",
                heard, name, kind, iso(now))

    def alias_confirm(self, heard, name, kind, now):
        """A fuzzy match worked and nobody objected: after CONFIRMED of them it is an alias."""
        if self.paused:
            return
        self._w("INSERT INTO aliases(heard,name,kind,source,uses,last_at) VALUES(?,?,?,'repeat',1,?) ON CONFLICT(heard) DO UPDATE SET uses=CASE WHEN name=excluded.name THEN uses+1 ELSE 1 END, name=CASE WHEN source='correction' THEN name ELSE excluded.name END, last_at=excluded.last_at",
                heard, name, kind, iso(now))

    def alias_delete(self, heard):
        return self._w("DELETE FROM aliases WHERE heard=?", heard).rowcount

    def aliases(self):
        return [dict(zip(("heard", "name", "kind", "source", "uses"), r)) for r in self._q("SELECT heard,name,kind,source,uses FROM aliases ORDER BY last_at DESC")]

    # ----- L4: habits, offered and never done on their own -----
    def habit_due(self, now):
        """A pattern worth offering right now, or None: he opened the same thing in the same hour (+-1) on 3 or more different days, it is that hour now,
        he has not opened it today, it was not offered today, and he never said no."""
        since = iso(now - timedelta(days=HABIT_DAYS))
        days = defaultdict(set)
        for at, ab, args in self._q("SELECT at,ability,args_json FROM events WHERE ok=1 AND ability LIKE '%open%' AND at>=?", since):
            for a, ar in zip((ab or "").split(","), json.loads(args or "[]")):
                if a == "open" and ar.get("target") and not ar.get("count", 1) > 1:
                    t = datetime.fromisoformat(at)
                    days[(ar["target"], t.hour)].add(t.date())
        today_open = {t for (t, _), ds in days.items() if now.date() in ds}
        best = None
        for (target, hour), ds in days.items():
            seen = len(ds - {now.date()})
            near = len(set().union(*[days.get((target, h), set()) for h in (hour - 1, hour, hour + 1)]) - {now.date()})
            if hour != now.hour or near < HABIT_SEEN or target in today_open:
                continue
            pat = f"open:{target}@{hour}"
            row = self._q("SELECT id,offered_at,answer FROM habits WHERE pattern=?", pat)
            if row and (row[0][2] == "no" or (row[0][1] or "")[:10] == now.date().isoformat()):
                continue
            if best is None or near > best["seen"]:
                best = {"pattern": pat, "target": target, "hour": hour, "seen": near}
        return best

    def habit_offered(self, h, now):
        if self._q("SELECT 1 FROM habits WHERE pattern=?", h["pattern"]):
            self._w("UPDATE habits SET seen=?, offered_at=? WHERE pattern=?", h["seen"], iso(now), h["pattern"])
        else:
            self._w("INSERT INTO habits(pattern,seen,offered_at) VALUES(?,?,?)", h["pattern"], h["seen"], iso(now))

    def habit_answer(self, pattern, answer):
        self._w("UPDATE habits SET answer=? WHERE pattern=?", answer, pattern)

    def habits(self):
        return [dict(zip(("pattern", "seen", "answer"), r)) for r in self._q("SELECT pattern,seen,answer FROM habits ORDER BY id DESC")]

    def habit_delete(self, pattern):
        return self._w("DELETE FROM habits WHERE pattern=?", pattern).rowcount

    def usage_top(self, n=6):
        return [list(r) for r in self._q("SELECT name, SUM(count) c FROM usage GROUP BY name ORDER BY c DESC LIMIT ?", n)]

    def routine_steps(self, name):
        return self.routine_get(name) or []

    # ----- L5: routines -----
    def routine_save(self, name, steps, now):
        self._w('DELETE FROM routine_progress WHERE name=?',name)
        self._w("INSERT INTO routines(name,steps_json,created) VALUES(?,?,?) ON CONFLICT(name) DO UPDATE SET steps_json=excluded.steps_json", name, json.dumps(steps), iso(now))

    def routine_get(self, name):
        r = self._q("SELECT steps_json FROM routines WHERE name=?", name)
        return json.loads(r[0][0]) if r else None

    def routines(self):
        return [r[0] for r in self._q("SELECT name FROM routines ORDER BY name")]

    def routine_forget(self, name):
        self._w('DELETE FROM routine_progress WHERE name=?',name)
        return self._w("DELETE FROM routines WHERE name=?", name).rowcount

    # ----- seeing and deleting everything -----
    def summary(self, now=None):
        """What Jarvis has learned, in a few plain sentences (this is also the text of the 'what do you know about me' answer)."""
        now = now or datetime.now()
        top = self._q("SELECT name, SUM(count) c FROM usage GROUP BY name ORDER BY c DESC LIMIT 5")
        hours = Counter()
        for h, c in self._q("SELECT hour, SUM(count) FROM usage GROUP BY hour"):
            hours[h] = c
        parts = []
        if top:
            parts.append("You use most: " + ", ".join(f"{n} ({c}x)" for n, c in top) + ".")
        if hours:
            parts.append(f"You are most active around {hours.most_common(1)[0][0]}:00.")
        al = self.aliases()
        if al:
            parts.append("Words I learned: " + ", ".join(f"'{a['heard']}' means {a['name']}" for a in al[:5] if a["source"] == "correction" or a["uses"] >= CONFIRMED) + ".")
        if self.routines():
            parts.append("Routines: " + ", ".join(self.routines()) + ".")
        if self.paused:
            parts.append("Learning is paused.")
        return " ".join(parts) or "I haven't learned anything about you yet, sir."

    def counts(self):
        return {t: self._q(f"SELECT COUNT(*) FROM {t}")[0][0] for t in ("events", "aliases", "usage", "facts", "habits", "routines")}

    def clear_learned(self):
        """Forget everything learned (keeps the plain log of turns). Returns how many things went."""
        n = 0
        for t in ("aliases", "usage", "facts", "habits", "routines", "routine_progress", "profile"):
            n += self._w(f"DELETE FROM {t}").rowcount
        return n
