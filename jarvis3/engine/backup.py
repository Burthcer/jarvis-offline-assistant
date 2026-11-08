"""Local consistent SQLite snapshots. No credentials, models or recordings."""
import json, sqlite3, tempfile, zipfile
from pathlib import Path
from datetime import datetime
from uuid import uuid4

def create(store,memory,folder):
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    path=folder/(datetime.now().strftime('%Y%m%d-%H%M%S-')+uuid4().hex[:6]+'.zip')
    with tempfile.TemporaryDirectory() as temp, store.lock, memory.lock:
        for name,db in [('facts.db',store.db),('learning.db',memory.db)]:
            dest=sqlite3.connect(str(Path(temp)/name))
            try: db.backup(dest)
            finally: dest.close()
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json',json.dumps({'version':1,'created':datetime.now().isoformat()}))
            for name in ('facts.db','learning.db'): archive.write(Path(temp)/name,name)
    return path.name

def restore(store,memory,folder,name):
    folder=Path(folder).resolve(); path=(folder/name).resolve()
    if path.parent!=folder or path.suffix!='.zip': raise ValueError('Choose a local Jarvis backup.')
    with tempfile.TemporaryDirectory() as temp:
        sources=[]
        try:
            with zipfile.ZipFile(path) as archive:
                if set(archive.namelist())!={'manifest.json','facts.db','learning.db'}: raise ValueError('Invalid backup files.')
                if sum(i.file_size for i in archive.infolist())>50*1024*1024: raise ValueError('Backup is too large.')
                if json.loads(archive.read('manifest.json')).get('version')!=1: raise ValueError('Unsupported backup version.')
                for name,required in [('facts.db',{'items','note_meta','repeats'}),('learning.db',{'events','aliases','routines'})]:
                    file=Path(temp)/name; file.write_bytes(archive.read(name))
                    source=sqlite3.connect(file); sources.append(source)
                    tables={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if not required<=tables or source.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Damaged backup database.')
            safety=create(store,memory,folder)
            with store.lock,memory.lock:
                rollback=[sqlite3.connect(':memory:'),sqlite3.connect(':memory:')]
                try:
                    store.db.backup(rollback[0]); memory.db.backup(rollback[1])
                    try: sources[0].backup(store.db); sources[1].backup(memory.db)
                    except Exception:
                        rollback[0].backup(store.db); rollback[1].backup(memory.db); raise
                finally:
                    for db in rollback: db.close()
            return safety
        finally:
            for db in sources: db.close()
