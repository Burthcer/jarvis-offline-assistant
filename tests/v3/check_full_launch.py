"""Reuse the proven owned-process/model check against V3 only; fake mic and audio."""
import os,sys,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));os.environ['JARVIS_SILENT']='1'
if '--child' in sys.argv:os.environ['JARVIS_V3_HOME']=tempfile.mkdtemp(prefix='jarvis-v3-full-')
source=(ROOT/'tests/v2/silent_full_launch.py').read_text(encoding='utf-8')
source=source.replace('jarvis2.','jarvis3.engine.').replace('from jarvis2 import','from jarvis3.engine import').replace('from jarvis.','from jarvis3.legacy.')
source=source.replace('ui.Real = Fake','ui.Real = Fake\n    ui.settings.set_autostart=lambda on:None')
source=source.replace("p=subprocess.Popen([sys.executable,'-u'", "p=subprocess.Popen([str(ROOT/'data/runtime-v4/JarvisV4.exe'),'-u'")
source=source.replace("document.title === 'Jarvis'","document.title === 'Jarvis V4'")
source=source.replace("measure('After answer')","measure('After answer')\n            assert int(gpu().split(',')[0]) <= 4096, 'V3 exceeded the graphics-memory ceiling'")
report=ROOT/'data/v3-dev-checks/resources.jsonl'
if '--child' not in sys.argv:report.unlink(missing_ok=True)
error_report=ROOT/'data/v3-dev-checks/full-launch-error.txt'
if '--child' not in sys.argv:error_report.unlink(missing_ok=True)
source=source.replace('traceback.print_exc()',"traceback.print_exc()\n            (ROOT/'data/v3-dev-checks/full-launch-error.txt').write_text(traceback.format_exc(),encoding='utf-8')")
line="print(label,'GPU MiB/C/%:',gpu(),'RAM incl window GB:',round(ram/2**30,2),flush=True)"
source=source.replace(line,line+"\n                with (ROOT/'data/v3-dev-checks/resources.jsonl').open('a',encoding='utf-8') as output:output.write(json.dumps({'label':label,'gpu_mib_c_percent':gpu(),'ram_gb':round(ram/2**30,2)})+'\\n')")
exec(compile(source,str(Path(__file__).resolve()),'exec'),globals())
