"""Local SQLite memory: reminders and notes. Repeating an item updates the existing one."""
import re
import json
import sqlite3
import threading
from functools import wraps
from datetime import datetime, timedelta

STOP = set("a an the my to of for and about that on at is it me i reminder reminders as what whats what's which where when who how are was do does you tell give read show say please sir".split())

SCHEMA = """CREATE TABLE IF NOT EXISTS items(
  id INTEGER PRIMARY KEY, kind TEXT, text TEXT, key TEXT, due TEXT,
  status TEXT DEFAULT 'open', created TEXT, updated TEXT)"""


def _locked(f):  # the voice thread, reminder watcher and UI will share one Store: one query at a time
    @wraps(f)
    def inner(self, *a, **k):
        with self.lock:
            return f(self, *a, **k)
    return inner


def tokens(text):
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t
            for t in re.findall(r"[a-z0-9']+", text.lower()) if t not in STOP}


def note_label(text):
    """An explicitly named fact keeps its identity when its value changes."""
    m = re.fullmatch(r'my\s+(.{1,60}?)\s+(?:is|are)\s+.+', text.strip(), re.I)
    return ' '.join(sorted(tokens(m[1]))) if m else None


class Store:
    def __init__(self, path="data/jarvis.db"):
        self.db = sqlite3.connect(path, check_same_thread=False)  # ponytail: one shared connection; add a lock if threads collide
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute(SCHEMA)
        if "left_s" not in [r[1] for r in self.db.execute("PRAGMA table_info(items)")]:
            self.db.execute("ALTER TABLE items ADD COLUMN left_s INTEGER")  # seconds left on a paused timer
        self.lock = threading.RLock()
        self.db.execute('CREATE TABLE IF NOT EXISTS note_meta(note_id INTEGER PRIMARY KEY, aliases TEXT DEFAULT \'[]\', source TEXT DEFAULT \'user\')')
        self.db.execute('CREATE TABLE IF NOT EXISTS repeats(item_id INTEGER PRIMARY KEY, days INTEGER NOT NULL)')
        self.db.commit()
        self.pending = None  # a risky action waiting for "yes"

    @_locked
    def add(self, text, due=None, kind="reminder", merge=True):
        """Returns (row, merged). Same item again (one's words contain the other's) updates it."""
        now = datetime.now().isoformat(timespec="seconds")
        t = tokens(text)
        # ponytail: subset match; two items where one is a word-subset of the other merge. Add fuzzy match if it bites.
        for r in self.db.execute("SELECT * FROM items WHERE kind=? AND status!='done'", (kind,)) if merge else ():
            k = set(r["key"].split())
            same = len(t & k) >= 0.66 * min(len(t), len(k)) if kind == "note" else t <= k or k <= t  # a note repeated with a new value replaces the old
            if kind == 'note':
                new_label, old_label = note_label(text), note_label(r['text'])
                if new_label or old_label:
                    same = bool(new_label and old_label and new_label == old_label)
            if t and k and same:
                keep = text if kind == "note" or len(t) > len(k) else r["text"]  # reminders keep the more detailed wording
                self.db.execute("UPDATE items SET text=?, key=?, due=COALESCE(?,due), status='open', updated=? WHERE id=?",
                                (keep, " ".join(sorted(t | k)), due and due.isoformat(), now, r["id"]))
                self.db.commit()
                return self.get(r["id"]), True
        cur = self.db.execute("INSERT INTO items(kind,text,key,due,created,updated) VALUES(?,?,?,?,?,?)",
                              (kind, text, " ".join(sorted(t)), due and due.isoformat(), now, now))
        self.db.commit()
        return self.get(cur.lastrowid), False

    @_locked
    def get(self, id):
        return self.db.execute("SELECT * FROM items WHERE id=?", (id,)).fetchone()

    @_locked
    def find(self, ref):
        """Item by number or by words ('maths exam')."""
        if ref.strip().lstrip("#").isdigit():
            return self.get(int(ref.strip().lstrip("#")))
        t = tokens(ref)
        for r in self.db.execute("SELECT * FROM items WHERE status!='done' ORDER BY id"):
            k = set(r["key"].split())
            if t and (t <= k or k <= t):
                return r

    @_locked
    def between(self, start, end):
        """Open reminders due in [start, end), soonest first."""
        return self.db.execute("SELECT * FROM items WHERE kind='reminder' AND status!='done' AND due>=? AND due<? ORDER BY due",
                               (start.isoformat(), end.isoformat())).fetchall()

    @_locked
    def upcoming(self, now, n=10):
        return self.db.execute("SELECT * FROM items WHERE kind='reminder' AND status!='done' AND due>=? ORDER BY due LIMIT ?",
                               (now.isoformat(), n)).fetchall()

    @_locked
    def due_now(self, now):
        """Reminders whose time has come and haven't been announced yet."""
        return self.db.execute("SELECT * FROM items WHERE kind IN ('reminder','timer') AND status='open' AND due<=? ORDER BY due",
                               (now.isoformat(),)).fetchall()

    @_locked
    def timers(self):
        return self.db.execute("SELECT * FROM items WHERE kind='timer' AND status='open' ORDER BY due").fetchall()

    @_locked
    def all_timers(self):
        """Running and paused."""
        return self.db.execute("SELECT * FROM items WHERE kind='timer' AND status IN ('open','paused') ORDER BY id DESC").fetchall()

    @_locked
    def pause_timer(self, id, now):
        r = self.get(id)
        if r and r["status"] == "open":
            self.db.execute("UPDATE items SET status='paused', left_s=? WHERE id=?", (max(0, round((datetime.fromisoformat(r["due"]) - now).total_seconds())), id)); self.db.commit()

    @_locked
    def resume_timer(self, id, now):
        r = self.get(id)
        if r and r["status"] == "paused":
            self.db.execute("UPDATE items SET status='open', due=? WHERE id=?", ((now + timedelta(seconds=r["left_s"] or 0)).isoformat(), id)); self.db.commit()

    @_locked
    def set_timer_left(self, id, secs, now, paused):
        """Reset or +1 minute: keeps it paused if it was."""
        self.db.execute("UPDATE items SET status=?, left_s=?, due=? WHERE id=?", ("paused" if paused else "open", secs, (now + timedelta(seconds=secs)).isoformat(), id)); self.db.commit()

    @_locked
    def cancel_timers(self):
        n = self.db.execute("DELETE FROM items WHERE kind='timer' AND status IN ('open','paused')").rowcount; self.db.commit()
        return n

    @_locked
    def set_status(self, id, status):
        self.db.execute("UPDATE items SET status=? WHERE id=?", (status, id)); self.db.commit()

    @_locked
    def delete(self, id):
        self.db.execute('DELETE FROM note_meta WHERE note_id=?',(id,))
        self.db.execute('DELETE FROM repeats WHERE item_id=?',(id,))
        self.db.execute("DELETE FROM items WHERE id=?", (id,)); self.db.commit()

    @_locked
    def notes(self, query):
        t = tokens(query)
        aliases = {r[0]:json.loads(r[1]) for r in self.db.execute('SELECT note_id,aliases FROM note_meta')}
        rows=list(self.db.execute("SELECT * FROM items WHERE kind='note' ORDER BY id"))
        canonical=lambda words:{'email' if word=='gmail' else word for word in words}
        exact=[]; equivalent=[]; named=[]
        for row in rows:
            match=re.fullmatch(r'my\s+(.+?)\s+(?:is|are)\s+.+',row['text'],re.I|re.S)
            label=tokens(match[1]) if match else set()
            alternate=[tokens(a) for a in aliases.get(row['id'],[])]
            if t and (t==label or t in alternate):exact.append(row)
            elif t and (canonical(t)==canonical(label) or any(canonical(t)==canonical(a) for a in alternate)):equivalent.append(row)
            elif t and label and canonical(t)<=canonical(label):named.append(row)
        if exact:return exact
        if equivalent:return equivalent
        if named:return named
        need = -(-len(t) * 6 // 10)  # at least 60% of the question's words must appear in the note
        return [r for r in rows
                if not t or any(t == tokens(a) for a in aliases.get(r['id'],[])) or len(t & set(r["key"].split())) >= max(1, need)]

    @_locked
    def set_aliases(self, id, aliases):
        row=self.get(id)
        if not row or row['kind']!='note': raise ValueError('Saved fact not found.')
        aliases=list(dict.fromkeys(a.strip() for a in aliases if a.strip()))
        if len(aliases)>8 or any(len(a)>60 for a in aliases): raise ValueError('Use up to eight short alternate names.')
        for alias in aliases:
            if any(r['id']!=id for r in self.notes(alias)):
                raise ValueError('An alternate name already matches another fact.')
        self.db.execute('INSERT INTO note_meta(note_id,aliases) VALUES(?,?) ON CONFLICT(note_id) DO UPDATE SET aliases=excluded.aliases',(id,json.dumps(aliases)))
        self.db.commit()

    @_locked
    def fact_info(self, row):
        from jarvis2.knowledge import describe
        meta=self.db.execute('SELECT aliases,source FROM note_meta WHERE note_id=?',(row['id'],)).fetchone()
        return {**describe(row['text']), 'id':row['id'],'text':row['text'],'aliases':json.loads(meta[0]) if meta else [],'source':meta[1] if meta else 'user','updated':row['updated']}

    @_locked
    def fact_infos(self,limit=None,public=False):
        from jarvis2.knowledge import describe
        out=[]
        for row in self.db.execute("SELECT i.*,COALESCE(m.aliases,'[]') AS aliases,COALESCE(m.source,'user') AS source FROM items i LEFT JOIN note_meta m ON i.id=m.note_id WHERE i.kind='note' ORDER BY i.id"):
            fields=describe(row['text'])
            if public and fields['secret']:continue
            out.append({**fields,'id':row['id'],'text':row['text'],'aliases':json.loads(row['aliases']),'source':row['source'],'updated':row['updated']})
            if limit and len(out)>=limit:break
        return out

    @_locked
    def repeat(self,id,days):
        if days not in (1,7,14,30): raise ValueError('Unsupported repeat interval.')
        self.db.execute('INSERT OR REPLACE INTO repeats VALUES(?,?)',(id,days)); self.db.commit()

    @_locked
    def schedule_next(self,row,now):
        repeat=self.db.execute('SELECT days FROM repeats WHERE item_id=?',(row['id'],)).fetchone()
        if not repeat:return False
        due=datetime.fromisoformat(row['due'])
        delta=timedelta(days=repeat[0])
        due += delta * max(1, (now-due)//delta+1)
        self.set_due(row['id'],due)
        return True

    @_locked
    def set_due(self, id, due):
        self.db.execute("UPDATE items SET due=?, status='open', updated=? WHERE id=?",
                        (due.isoformat(), datetime.now().isoformat(timespec="seconds"), id)); self.db.commit()

    @_locked
    def rename(self, id, text):
        self.db.execute("UPDATE items SET text=?, key=?, updated=? WHERE id=?",
                        (text, " ".join(sorted(tokens(text))), datetime.now().isoformat(timespec="seconds"), id)); self.db.commit()
        return self.get(id)

    @_locked
    def last_fired(self):
        """The reminder Jarvis announced most recently (for 'snooze')."""
        return self.db.execute("SELECT * FROM items WHERE status='fired' ORDER BY due DESC LIMIT 1").fetchone()

    @_locked
    def clear(self):
        self.db.execute('DELETE FROM note_meta')
        self.db.execute('DELETE FROM repeats')
        n = self.db.execute("DELETE FROM items").rowcount; self.db.commit()
        return n
