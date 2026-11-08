"""V2's saved-recording replay (tests/v2/ears_replay.py) against the private V3 ears. Usage: replay_recordings.py [quiet|music|earphones] [--nocancel]"""
import os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
os.environ['JARVIS_SILENT']='1';os.environ.setdefault('JARVIS_V3_HOME',tempfile.mkdtemp(prefix='jarvis-v3-replay-'))
src=(ROOT/'tests/v2/ears_replay.py').read_text(encoding='utf-8')
src=src.replace('jarvis2.ears','jarvis3.engine.ears').replace('import jarvis2.ears as E','import jarvis3.engine.ears as E').replace('from jarvis2 import','from jarvis3.engine import').replace('jarvis2.','jarvis3.engine.')
src=src.replace('''        rows[-1]["exact"] = same(rows[-1]["heard"], rows[-1]["say"])''','''        rows[-1]["exact"] = same(rows[-1]["heard"], rows[-1]["say"])
        rows[-1]["close_delay"] = round(max(h.ended for h in hit) - tk["end"], 2) if hit else None''')
src=src.replace('''    w2 = sorted(h.wait_ms for h in got)''','''    d = sorted(r["close_delay"] for r in n if r["close_delay"] is not None)
    print(f"   sentence closed after his words ended: median {d[len(d)//2] if d else None} s, worst {d[-1] if d else None} s")
    w2 = sorted(h.wait_ms for h in got)''')
assert 'close_delay' in src
exec(compile(src,str(ROOT/'tests/v2/ears_replay.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/v2/ears_replay.py')})
