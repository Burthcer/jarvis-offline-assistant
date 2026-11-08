"""One-time private V3 source snapshot. Refuses to overwrite an existing fork."""
from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'jarvis3'
if (DEST/'engine').exists() or (DEST/'legacy').exists():raise SystemExit('V3 already exists; refusing to overwrite it.')
baseline={}
for source,name in [('jarvis','legacy'),('jarvis2','engine')]:
    for path in (ROOT/source).rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
        relative=path.relative_to(ROOT)
        baseline[str(relative).replace('\\','/')]=hashlib.sha256(path.read_bytes()).hexdigest()
        target=DEST/name/path.relative_to(ROOT/source);target.parent.mkdir(parents=True,exist_ok=True)
        if path.suffix=='.py':
            text=path.read_text(encoding='utf-8')
            text=text.replace('jarvis2.db','learning.db').replace('settings2.json','settings3.json').replace('jarvis.db','facts.db')
            text=text.replace('jarvis2','jarvis3.engine').replace('from jarvis import','from jarvis3.legacy import').replace('from jarvis.','from jarvis3.legacy.').replace('import jarvis.','import jarvis3.legacy.')
            text=text.replace('Jarvis2.Assistant','Jarvis3.Preview').replace('Jarvis2.pyw','Jarvis3.pyw').replace('Jarvis V2','Jarvis V3 Preview')
            text=re.sub(r'^ROOT = .*$', 'from jarvis3.paths import RUNTIME, PROJECT, ASSETS\nROOT = str(RUNTIME)',text,flags=re.M)
            if relative.as_posix()=='jarvis/actions.py':
                text=re.sub(r'^START_CACHE = .*$', 'from jarvis3.paths import DATA\nSTART_CACHE = str(DATA / "start_apps.json")',text,flags=re.M)
            if relative.as_posix() in ('jarvis/settings.py','jarvis2/settings.py'):
                text=re.sub(r'^PATH = .*$', 'from jarvis3.paths import DATA, PROJECT\nPATH = str(DATA / "settings3.json")',text,flags=re.M)
            if relative.as_posix()=='jarvis2/settings.py':
                text=text.replace('os.path.join(ROOT, "Jarvis3.pyw")','str(PROJECT / "Jarvis3.pyw")').replace('"Jarvis2"','"Jarvis3Preview"')
            if relative.as_posix()=='jarvis2/ai.py':
                text=re.sub(r'^CHAT_MODEL = .*$', 'from jarvis3.paths import PROJECT\nCHAT_MODEL = str(PROJECT / "data/models/llm/Qwen3-4B-Instruct-2507-Q4_K_M.gguf")',text,flags=re.M)
            if relative.as_posix()=='jarvis/voice.py':
                text=text.replace('os.path.join(ROOT, "data", "models",','os.path.join(str(PROJECT), "data", "models",')
            if relative.as_posix() in ('jarvis/ui.py','jarvis2/ui.py'):
                text=re.sub(r'^ICON = .*$', 'from jarvis3.paths import ASSETS\nICON = str(ASSETS / "jarvis-v3.ico")',text,flags=re.M)
            text=text.replace('JarvisOfflineAssistant/GoogleReadOnly','JarvisOfflineAssistant/V3/GoogleReadOnly')
            target.write_text(text,encoding='utf-8')
        else:target.write_bytes(path.read_bytes())
(DEST/'BASELINE.json').write_text(json.dumps({'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_hashes':baseline},indent=2),encoding='utf-8')
print('Private V3 snapshot created:',len(baseline),'files. V1/V2 unchanged.')
