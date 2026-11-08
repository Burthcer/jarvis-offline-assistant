"""Inspect approved lab weights with tensor-only CPU loading; no repository code."""
import os,sys,json,hashlib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(Path(__file__).resolve().parent)]
sys.dont_write_bytecode=True
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['JARVIS_SILENT']='1';os.environ['HF_HUB_OFFLINE']='1'
sys.path.append(r'C:\Users\USER\Desktop\Wisperno-pro\.venv\Lib\site-packages')
from prepare_separation_trial import LAB,SHA256,SIZE,REVISION

def main():
    path=LAB/'pytorch_model.bin'
    if path.stat().st_size!=SIZE or hashlib.sha256(path.read_bytes()).hexdigest()!=SHA256:raise ValueError('Unverified lab checkpoint')
    import torch,psutil
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    t=time.perf_counter();data=torch.load(path,map_location='cpu',weights_only=True)
    if not isinstance(data,dict):raise ValueError('Unexpected checkpoint structure')
    state=data.get('state_dict',{})
    if not isinstance(state,dict) or any(not isinstance(v,torch.Tensor) or v.device.type!='cpu' for v in state.values()):raise ValueError('Unexpected non-CPU state')
    report={'revision':REVISION,'sha256':SHA256,'torch':str(torch.__version__),'weights_only':True,'load_ms':round((time.perf_counter()-t)*1000),'keys':list(data),'model_name':data.get('model_name'),'model_args':data.get('model_args'),'tensors':len(state),'parameters':sum(v.numel() for v in state.values()),'tensor_keys':list(state)[:18],'cuda_initialized':torch.cuda.is_initialized(),'ram_mb':round(psutil.Process().memory_info().rss/2**20)}
    encoded=json.dumps(report,indent=2)
    (LAB/'inspection.json').write_text(encoded,encoding='utf-8');print(encoded,flush=True)

if __name__=='__main__':main()
