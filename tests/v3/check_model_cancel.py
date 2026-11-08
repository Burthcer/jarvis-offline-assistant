"""Real unchanged action model, token-boundary cancellation, no PC/audio/mic."""
import os,sys,time,threading,subprocess
from pathlib import Path
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.control import CANCEL_INFERENCE
from jarvis3.engine.ai import AI,AIError
import psutil
ai=AI();thread=None;CANCEL_INFERENCE.clear()
try:
    ai.load();first=threading.Event();errors=[];finished=[]
    sample=ai.llm.sample
    def observed(*a,**k):first.set();return sample(*a,**k)
    ai.llm.sample=observed
    def answer():
        try:finished.append(ai.complete([{'role':'user','content':'Count from one to one hundred, giving a short sentence about every number.'}],max_tokens=512))
        except Exception as e:errors.append(e)
    thread=threading.Thread(target=answer);thread.start()
    assert first.wait(10),'No generation token boundary observed'
    start=time.perf_counter();CANCEL_INFERENCE.set();thread.join(3)
    assert not thread.is_alive() and errors and isinstance(errors[0],AIError) and not finished,('Cancellation failed',errors,finished)
    print('REAL MODEL CANCEL ms',round((time.perf_counter()-start)*1000,1),'RAM MB',round(psutil.Process().memory_info().rss/2**20),flush=True)
finally:
    CANCEL_INFERENCE.set()
    if thread:thread.join(5)
    ai.unload();CANCEL_INFERENCE.clear()
    print('GPU after model release',subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu,utilization.gpu','--format=csv,noheader,nounits'],text=True).strip(),flush=True)
