"""Matched current V2/V3 gold grading with stronger cooling, fake OS, owned source copy."""
import os,sys,subprocess,tarfile,io,tempfile,shutil,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/v3-dev-checks/quality';OUT.mkdir(parents=True,exist_ok=True)
os.environ['JARVIS_SILENT']='1'
if '--child' in sys.argv:
    mode=sys.argv[-2];folder=Path(sys.argv[-1])
    origin=folder/'tests/v2/harness.py'
    sys.path[:0]=[str(ROOT if mode=='v3' else folder),str(folder/'tests/v2')]
    source=origin.read_text(encoding='utf-8')
    if mode=='v3':source=source.replace('jarvis2.','jarvis3.engine.').replace('from jarvis.','from jarvis3.legacy.')
    source=source.replace("if '--cool' in sys.argv and i%25==24:time.sleep(1)","if '--cool' in sys.argv and i%10==9:time.sleep(3)")
    scope={'__name__':'matched_quality','__file__':str(origin)}
    exec(compile(source,str(origin),'exec'),scope)
    frozen=json.loads((ROOT/'data/gold/catalog.json').read_text(encoding='utf-8'))
    scope['Fake'].catalog=lambda self:dict(frozen)
    scope['OUT']=str(OUT)
    sys.argv=[str(origin),'--label',mode+'-matched','--cool']
    scope['main']()
else:
    folder=Path(tempfile.mkdtemp(prefix='baseline-',dir=OUT)).resolve()
    assert folder.is_relative_to(OUT.resolve()) and folder!=OUT.resolve()
    try:
        archive=subprocess.check_output(['git','archive','49cb25a','jarvis','jarvis2','tests/v2'],cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:bundle.extractall(folder,filter='data')
        for mode in ('v2','v3'):
            result=subprocess.run([sys.executable,'-u',str(Path(__file__).resolve()),'--child',mode,str(folder)],cwd=ROOT,env={**os.environ,'JARVIS_SILENT':'1'},timeout=300)
            assert result.returncode==0,(mode,result.returncode)
        old=json.loads((OUT/'v2_v2-matched.json').read_text());new=json.loads((OUT/'v2_v3-matched.json').read_text())
        print('Changed EVEN cases only (held-out wording not shown):',flush=True)
        for a,b in zip(old,new):
            if a['i']%2==0 and (a['g'],a['r'])!=(b['g'],b['r']):print(a['i'],a['t'],a['g'],'->',b['g'],flush=True)
    finally:
        assert folder.is_relative_to(OUT.resolve()) and folder!=OUT.resolve()
        shutil.rmtree(folder)
