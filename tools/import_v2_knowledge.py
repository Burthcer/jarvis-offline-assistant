"""One-time additive copy of V2's saved facts and learned names into V3."""
import sqlite3
from contextlib import closing
from pathlib import Path


def open_readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def import_knowledge(v2_facts, v2_learning, v3_facts, v3_learning):
    with closing(open_readonly(v2_facts)) as old, closing(open_readonly(v2_learning)) as learned:
        notes = old.execute("""
            SELECT i.text, i.key, i.created, i.updated, COALESCE(m.aliases, '[]')
            FROM items i LEFT JOIN note_meta m ON i.id=m.note_id
            WHERE i.kind='note' ORDER BY i.id
        """).fetchall()
        names = learned.execute('SELECT heard,name,kind,source,uses,last_at FROM aliases').fetchall()

    dest = Path(v3_facts).resolve().as_uri() + '?mode=rw'
    learning = Path(v3_learning).resolve().as_uri() + '?mode=rw'
    with closing(sqlite3.connect(dest, uri=True, timeout=10)) as db:
        db.execute('ATTACH DATABASE ? AS learning', (learning,))
        with db:
            db.execute('BEGIN IMMEDIATE')
            existing = {r[0] for r in db.execute("SELECT text FROM items WHERE kind='note'")}
            added = 0
            for text, key, created, updated, aliases in notes:
                if text in existing:
                    continue
                cursor = db.execute("""
                    INSERT INTO items(kind,text,key,created,updated) VALUES('note',?,?,?,?)
                """, (text, key, created, updated))
                db.execute("INSERT INTO note_meta(note_id,aliases,source) VALUES(?,?,'Imported from V2')",
                           (cursor.lastrowid, aliases))
                existing.add(text)
                added += 1
            copied = db.executemany("""
                INSERT INTO learning.aliases(heard,name,kind,source,uses,last_at) VALUES(?,?,?,?,?,?)
                ON CONFLICT(heard) DO NOTHING
            """, names).rowcount
    return {'facts_added': added, 'exact_facts_skipped': len(notes)-added,
            'names_added': copied, 'existing_names_kept': len(names)-copied}


if __name__ == '__main__':
    data = Path(__file__).resolve().parents[1] / 'data'
    destination = data / 'v3' / 'data'
    print(import_knowledge(data/'jarvis.db', data/'jarvis2.db',
                           destination/'facts.db', destination/'learning.db'))
