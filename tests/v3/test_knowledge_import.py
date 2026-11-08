"""Validate the additive import using disposable V2 and V3 databases."""
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.memory import SCHEMA
from jarvis3.legacy.store import Store
from tools.import_v2_knowledge import import_knowledge

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    old, old_learning, new, new_learning = (root/name for name in ('old.db', 'old-learn.db', 'new.db', 'new-learn.db'))
    for path, facts in ((old, ('my college is Old College', 'my city is Test City')),
                        (new, ('my college is New College', 'my city is Test City'))):
        store = Store(path)
        for fact in facts:
            store.add(fact, kind='note', merge=False)
        store.add('Fixture reminder', kind='reminder')
        store.db.close()
    with closing(sqlite3.connect(old)) as db, db:
        db.execute("INSERT INTO note_meta(note_id,aliases) VALUES(1,'[\"campus\"]')")
    for path, name in ((old_learning, 'old app'), (new_learning, 'new app')):
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript(SCHEMA)
            db.execute("INSERT INTO aliases VALUES('ambiguous',?,'app','correction',1,'2026-11-07')", (name,))
            if path == old_learning:
                db.execute("INSERT INTO aliases VALUES('unique','test app','app','correction',1,'2026-11-07')")
    sources = old.read_bytes(), old_learning.read_bytes()
    result = import_knowledge(old, old_learning, new, new_learning)
    assert result == {'facts_added': 1, 'exact_facts_skipped': 1, 'names_added': 1, 'existing_names_kept': 1}, result
    with closing(sqlite3.connect(new)) as db:
        assert db.execute('SELECT text FROM items ORDER BY id').fetchall() == [
            ('my college is New College',), ('my city is Test City',), ('Fixture reminder',), ('my college is Old College',)]
        assert db.execute('SELECT aliases,source FROM note_meta').fetchone() == ('["campus"]', 'Imported from V2')
    with closing(sqlite3.connect(new_learning)) as db:
        assert db.execute("SELECT name FROM aliases WHERE heard='ambiguous'").fetchone() == ('new app',)
    again = import_knowledge(old, old_learning, new, new_learning)
    assert again['facts_added'] == again['names_added'] == 0
    assert sources == (old.read_bytes(), old_learning.read_bytes())
print('PASS additive fact and name copy, conflicts, idempotence and read-only V2')
