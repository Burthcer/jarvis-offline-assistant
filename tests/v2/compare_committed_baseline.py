"""Run the committed baseline with today's identical grading, fake PC, silent.
Only tracked source is unpacked to an owned temporary workspace.
"""
import os,sys,tempfile,subprocess,tarfile,io,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['JARVIS_SILENT']='1'
folder=Path(tempfile.mkdtemp(prefix='jarvis-quality-baseline-',dir=ROOT/'data')).resolve()
assert folder.is_relative_to((ROOT/'data').resolve())
try:
    data=subprocess.check_output(['git','archive','HEAD','jarvis','jarvis2','tests/v2'],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:archive.extractall(folder,filter='data')
    # Use the identical newer effect normalisation and cooling schedule.
    shutil.copy2(Path(__file__).with_name('harness.py'),folder/'tests/v2/harness.py')
    result=subprocess.run([sys.executable,'-u',str(folder/'tests/v2/harness.py'),'--label','committed-baseline','--cool'],cwd=folder,env={**os.environ,'JARVIS_SILENT':'1'})
    assert result.returncode==0
    source=folder/'data/gold/results/v2_committed-baseline.json'
    assert source.exists(),'baseline result file was not produced'
    shutil.copy2(source,ROOT/'data/gold/results/v2_committed-baseline.json')
finally:
    assert folder.is_relative_to((ROOT/'data').resolve())
    shutil.rmtree(folder)
