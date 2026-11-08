"""Run the V2 checks against private V3 modules, with frozen fake-PC catalog only."""
import os,sys,subprocess,types,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
def private(text):
    return text.replace('jarvis2.','jarvis3.engine.').replace('from jarvis import','from jarvis3.legacy import').replace('from jarvis.','from jarvis3.legacy.').replace("'jarvis.","'jarvis3.legacy.").replace('"jarvis.','"jarvis3.legacy.')
if '--child' in sys.argv:
    name=sys.argv[-1]
    module=types.ModuleType('harness');module.__file__=str(ROOT/'tests/v2/harness.py')
    sys.modules['harness']=module
    exec(compile(private(Path(module.__file__).read_text(encoding='utf-8')),module.__file__,'exec'),module.__dict__)
    frozen=json.loads((ROOT/'data/gold/catalog.json').read_text(encoding='utf-8'))
    module.Fake.catalog=lambda self:dict(frozen)
    file=ROOT/'tests/v2'/name
    code=private(file.read_text(encoding='utf-8'))
    if name=='test_refinement.py':
        # The old fixture bypasses __init__/capture. Supply V3's state and
        # stamp its synthetic utterance at capture time, just as Ears does.
        code=code.replace('u = UiApp.__new__(UiApp)','u = UiApp.__new__(UiApp)\nfrom jarvis3.feedback import Feedback\nfrom jarvis3.conversation import Conversation\nimport threading\nu.feedback=Feedback()\nu.conversation=Conversation()\nu._shutdown_requested=threading.Event()')
        code=code.replace("Heard('unclear', 'name', '', 8, 9)","Heard('unclear', 'name', '', 8, 9, conversation_generation=u.conversation.generation)")
    exec(compile(code,str(file),'exec'),{'__name__':'__main__','__file__':str(file)})
else:
    import tempfile
    tests=['test_core.py','test_abilities.py','test_memory.py','test_skills.py','test_ears.py','test_organizer.py','test_daily.py','test_fact_actions.py','test_feedback.py','test_dialogue.py','test_window_actions.py','test_request_echo.py','test_refinement.py','test_learning_lifecycle.py','test_expanded_features.py','test_settings_volume.py']
    failed=[]
    with tempfile.TemporaryDirectory(prefix='jarvis-v3-regressions-') as temp:
        for test in tests:
            result=subprocess.run([sys.executable,'-u',str(Path(__file__).resolve()),'--child',test],cwd=ROOT,env={**os.environ,'JARVIS_SILENT':'1','JARVIS_V3_HOME':temp},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=40)
            print(test,'PASS' if result.returncode==0 else 'FAIL',flush=True)
            if result.returncode:
                failed.append(test);print(result.stdout,flush=True)
    assert not failed,failed
    print('PRIVATE V3 REGRESSION SUITES PASSED',flush=True)
