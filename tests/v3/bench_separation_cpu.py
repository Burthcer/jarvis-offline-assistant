"""Explicit CPU-only separator timing on fixed non-private synthetic buffers."""
import os,sys,time,json,threading,subprocess
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['JARVIS_SILENT']='1';os.environ['HF_HUB_OFFLINE']='1'
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
sys.path.append(r'C:\Users\USER\Desktop\Wisperno-pro\.venv\Lib\site-packages')
import numpy as np,torch,psutil
torch.set_num_threads(2);torch.set_num_interop_threads(1)
from jarvis3.lab.separation import ConvTasNetCPU
REPORT=ROOT/'data/v3/lab/separation/cpu-benchmark.json'
done=threading.Event();samples=[];errors=[];rows=[];model=None
process=psutil.Process()
def monitor():
    process.cpu_percent(None)
    while not done.is_set():
        try:
            used,temp=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu','--format=csv,noheader,nounits'],text=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=3).strip().split(',')
            samples.append({'at':time.monotonic(),'rss_mb':round(process.memory_info().rss/2**20),'process_cpu_percent':process.cpu_percent(None),'total_gpu_mib':int(used),'gpu_temperature_c':int(temp)})
            if int(temp)>=78:errors.append('GPU temperature reached78C');return
        except Exception as error:errors.append(str(error));return
        done.wait(.15)
worker=threading.Thread(target=monitor,daemon=True)
try:
    worker.start();start=time.perf_counter();model=ConvTasNetCPU();load_ms=round((time.perf_counter()-start)*1000)
    for seconds in (.8,1.6,3.,6.):
        t=np.arange(round(seconds*16000),dtype=np.float32)/16000
        rng=np.random.default_rng(620)
        signal=(.06*np.sin(2*np.pi*220*t)+.04*np.sin(2*np.pi*610*t)+.005*rng.normal(size=len(t))).astype(np.float32)
        timing=[]
        for iteration in range(7):
            if errors:raise RuntimeError(errors)
            started=time.perf_counter();result=model.separate(signal);elapsed=1000*(time.perf_counter()-started)
            assert result.shape==(2,len(signal)) and np.isfinite(result).all() and not torch.cuda.is_initialized()
            if iteration>=2:timing.append(elapsed)
        p95=float(np.percentile(timing,95,method='higher'))
        row={'input_seconds':seconds,'warmups':2,'timed_repetitions':5,'times_ms':[round(v,2) for v in timing],'p50_ms':round(float(np.median(timing)),2),'p95_ms':round(p95,2),'p95_method':'higher; maximum of five timed repetitions','target_p95_ms':200,'within_target':p95<200}
        rows.append(row);print(json.dumps(row),flush=True)
finally:
    if model:model.close()
    done.set()
    if worker.ident:worker.join(4)
    assert not worker.is_alive(),'Owned monitoring thread remains'
    assert not torch.cuda.is_initialized()
    report={'status':'complete' if len(rows)==4 else 'incomplete','device':'cpu','threads':2,'interop_threads':1,'torch':str(torch.__version__),'load_ms':locals().get('load_ms'),'timing_scope':'separation only, including CPU input validation and output copy; excludes speaker selection, shared gain, resampling and ASR','input':'fixed synthetic two tones plus seeded noise; no speech/private audio','durations':rows,'resource_peak':{key:max((s[key] for s in samples),default=None) for key in ('rss_mb','process_cpu_percent','total_gpu_mib','gpu_temperature_c')},'cpu_temperature':'not available from this Windows probe; GPU temperature is not CPU temperature','cuda_initialized':False,'monitor_errors':errors}
    REPORT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Owned CPU separator closed. Report:',REPORT,flush=True)
