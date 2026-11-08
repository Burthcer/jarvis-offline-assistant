"""Same full gold grader against private V3; frozen fake catalog; results stay V3-owned."""
import sys,os,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tests/v2')]
os.environ['JARVIS_SILENT']='1'
source=(ROOT/'tests/v2/harness.py').read_text(encoding='utf-8')
source=source.replace("if '--cool' in sys.argv and i%25==24:time.sleep(1)","if '--cool' in sys.argv and i%10==9:time.sleep(3)")
source=source.replace('jarvis2.','jarvis3.engine.').replace('from jarvis.','from jarvis3.legacy.')
scope={'__name__':'v3_gold_harness','__file__':str(ROOT/'tests/v2/harness.py')}
exec(compile(source,scope['__file__'],'exec'),scope)
frozen=json.loads((ROOT/'data/gold/catalog.json').read_text(encoding='utf-8'))
scope['Fake'].catalog=lambda self:dict(frozen)
scope['OUT']=str(ROOT/'data/v3-dev-checks/gold')
if '--baseline-prompt' in sys.argv or '--candidate-prompt' in sys.argv:
    # Controlled regression experiment only. No app/source/model changes and
    # no held-out examples inspected or used to construct the prompt.
    from jarvis3.engine import understand
    baseline='- Nothing outside the abilities can be done (Bluetooth, changing settings, deleting files, shutting the laptop, reading the screen): CHAT, say so.'
    candidate='- Use only the listed abilities. Opening a settings page is different from toggling its switches. Never claim an unsupported operation; ASK for missing details or CHAT to explain the limit.'
    understand.RULES=understand.RULES.replace(candidate,baseline) if '--baseline-prompt' in sys.argv else understand.RULES.replace(baseline,candidate)
scope['main']()
