"""Separate approved lab: CPU separator/checker; unchanged ASR/NLU in owned child.
Audio stays in memory/local pipes. Only case IDs and numeric measurements persist.
"""
import os,sys,json,time,hashlib,statistics,threading,subprocess,argparse
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(Path(__file__).resolve().parent)]
LAB=ROOT/'data/v3/lab/separation'

def p95(values):return round(sorted(values)[max(0,int(np.ceil(len(values)*.95))-1)],2) if values else None

def sisdr(reference,estimate):
    a=np.asarray(reference,dtype=np.float64);b=np.asarray(estimate,dtype=np.float64)
    a=a-a.mean();b=b-b.mean();energy=float(a@a)
    if energy<1e-12 or float(b@b)<1e-12:return None
    target=a*float(b@a)/energy;error=b-target
    return round(10*np.log10((float(target@target)+1e-12)/(float(error@error)+1e-12)),3)

class Monitor:
    def __init__(self):
        import psutil
        self.p=psutil.Process();self.done=threading.Event();self.thread=None;self.error=None
        self.peak={'ram_mb':0,'cpu_percent':0,'total_gpu_mib':0,'gpu_temperature_c':0}
    def start(self):self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def run(self):
        while not self.done.is_set():
            try:
                processes=[self.p,*self.p.children(recursive=True)]
                ram=sum(p.memory_info().rss for p in processes if p.is_running())/2**20
                self.peak['ram_mb']=max(self.peak['ram_mb'],round(ram));self.peak['cpu_percent']=max(self.peak['cpu_percent'],self.p.cpu_percent())
                raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,temperature.gpu','--format=csv,noheader,nounits'],text=True,timeout=4)
                gpu,temp=map(int,raw.strip().split(','))
                self.peak['total_gpu_mib']=max(self.peak['total_gpu_mib'],gpu);self.peak['gpu_temperature_c']=max(self.peak['gpu_temperature_c'],temp)
                if gpu>4096 or temp>=78:self.error='Graphics/temperature limit reached';return
            except Exception:pass
            self.done.wait(.5)
    def check(self):
        if self.error:raise RuntimeError(self.error)
    def close(self):
        self.done.set()
        if self.thread:self.thread.join(5)

def summarize(rows):
    groups={}
    for split in ('tuning','heldout','control'):
        for kind in ('clean','overlap','nonoverlap','other','silence'):
            group_rows=[r for r in rows if r['split']==split and r['kind']==kind]
            if not group_rows:continue
            group={'cases':len(group_rows),'added_cpu_p50_ms':round(statistics.median(r['added_cpu_ms'] for r in group_rows),2),'added_cpu_p95_ms':p95([r['added_cpu_ms'] for r in group_rows])}
            for branch in ('raw','voice_check','separated'):
                records=[r[branch] for r in group_rows];evaluated=all(r['evaluated'] for r in records)
                edits=sum(r['wer']['edits'] for r in records if r['wer']);count=sum(r['wer']['reference_words'] for r in records if r['wer'])
                pairs=list(zip(group_rows,records))
                group[branch]={'addressed':sum(r['accepted'] for r in records) if evaluated else None,'owner_commands_correct':sum(row['owner_present'] and r['match'] for row,r in pairs) if evaluated else None,'wrong_action_attempts':sum(r['wrong_action'] for r in records) if evaluated else None,'missing_owner_commands':sum(row['owner_present'] and not r['match'] for row,r in pairs) if evaluated else None,'false_speaker_accepts':sum(not row['owner_present'] and r['speaker_accept'] is True for row,r in pairs) if branch!='raw' else None,'false_addressed':sum(not row['owner_present'] and r['accepted'] for row,r in pairs) if evaluated else None,'prompt_word_error_rate':round(edits/count,4) if count else None}
            groups[split+'-'+kind]=group
    return groups

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='full');parser.add_argument('--limit',type=int);parser.add_argument('--cpu-only',action='store_true');args=parser.parse_args()
    if not args.label.replace('-','').isalnum():raise ValueError('Use a simple report label')
    original_cuda=os.environ.get('CUDA_VISIBLE_DEVICES');os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['JARVIS_SILENT']='1';os.environ['HF_HUB_OFFLINE']='1';sys.dont_write_bytecode=True
    sys.path.append(r'C:\Users\USER\Desktop\Wisperno-pro\.venv\Lib\site-packages')
    import torch
    torch.set_num_threads(2);torch.set_num_interop_threads(1)
    from jarvis3.lab.separation import ConvTasNetCPU
    from jarvis3.lab.voice_check_onnx import OnnxVoiceCheck
    from jarvis3.lab.separation_policy import choose,check_original,published_gain,THRESHOLD,MARGIN
    from separation_cases import Corpus,cases,enrollment,manifest,FROZEN_MANIFEST_SHA256
    from separation_grade import word_error,compare,PROTOCOL
    from separation_asr import ASRWorker
    frozen=manifest();digest=hashlib.sha256(json.dumps(frozen,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if digest!=FROZEN_MANIFEST_SHA256 or frozen['selection_policy']['threshold']!=THRESHOLD or frozen['selection_policy']['runner_up_margin']!=MARGIN:raise ValueError('Frozen experiment changed')
    (LAB/'frozen_matrix.json').write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    corpus=Corpus();model=ConvTasNetCPU();checker=OnnxVoiceCheck(ROOT/'data/v3/lab/model');checker.enroll(enrollment(corpus))
    monitor=Monitor();worker=None;rows=[];started=time.perf_counter();status='running';failure=None;cache={};report_path=LAB/('evaluation-'+args.label+'.json')
    def pipeline(text):
        if text not in cache:cache[text]=worker.interpret(text)
        return cache[text]
    def record(text,gate,truth,branch):
        result=pipeline(text) if worker and gate else {'calls':[],'ok':False,'addressed':False,'ms':0}
        grade=compare(result,truth.expected_intent or [])
        return {**grade,'evaluated':bool(worker),'accepted':bool(gate and result['addressed']),'speaker_accept':bool(gate) if branch!='raw' else None,'wer':word_error(truth.expected_text,text if gate else '') if worker and truth.expected_text else None}
    def save():
        report={'status':status,'failure':failure,'enabled_in_jarvis':False,'label':args.label,'grading_protocol':PROTOCOL,'execution_scope':'fixed lab capability allowlist; blocked plans retained as attempts','complete_matrix':len(rows)==45,'matrix_sha256':digest,'policy':frozen['selection_policy'],'gain':'shared official L1 ratio; zero denominator guarded','separator':model.metadata,'checker':'existing CPU ONNX lab; profile in memory only','asr':'unchanged speech/action models; isolated fake-PC GPU child' if worker else 'not run','nlu_cache':'identical transcripts reuse one fresh-PC interpretation; no expected labels sent','rows':rows,'summary':summarize(rows),'resource_peak':monitor.peak,'cpu_temperature':'not available; GPU temperature is not CPU temperature','cpu_model_cuda_initialized':torch.cuda.is_initialized(),'cpu_model_cuda_allocated_bytes':torch.cuda.memory_allocated(),'profile_saved':False,'audio_saved':False,'elapsed_seconds':round(time.perf_counter()-started,2),'limitations':list(frozen['limitations'])+['Prompt word distance is not manually verified transcript WER.','Synthetic voices and one owner session are not real phone/tired-room acceptance.','Frozen catalog/parser failures remain possible despite correct ASR.','No streaming/production integration; uncertainty rejects with no original-mixture fallback.']}
        report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    try:
        monitor.start()
        if not args.cpu_only:
            raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True,timeout=4)
            if int(raw.strip())>512:raise RuntimeError('Existing graphics workload; defer GPU comparison')
            worker=ASRWorker(gpu_env={'CUDA_VISIBLE_DEVICES':original_cuda},interpret=True)
        for number,case in enumerate(cases(corpus),1):
            if args.limit and number>args.limit:break
            monitor.check();x=case['audio'];truth=case['truth']
            text=worker.transcribe(x)['text'] if worker else '';raw_result=record(text,True,truth,'raw')
            t=time.perf_counter();original=check_original(x,checker.score);original_ms=(time.perf_counter()-t)*1000
            baseline=record(text,original['accepted'],truth,'voice_check')
            t=time.perf_counter();separated=model.separate(x,16000);separation_ms=(time.perf_counter()-t)*1000
            t=time.perf_counter();separated=published_gain(x,separated);choice=choose(separated,checker.score);selection_ms=(time.perf_counter()-t)*1000
            selected=separated[choice['index']] if choice['accepted'] else None
            transcript=worker.transcribe(selected)['text'] if worker and selected is not None else '';outcome=record(transcript,choice['accepted'],truth,'separated')
            rows.append({'id':case['id'],'split':case['split'],'kind':case['kind'],'owner_present':truth.owner_present,'duration_s':round(len(x)/16000,3),'original_score':original['score'],'selection':choice,'separation_ms':round(separation_ms,2),'selection_ms':round(selection_ms,2),'baseline_check_ms':round(original_ms,2),'added_cpu_ms':round(separation_ms+selection_ms,2),'mixture_vs_owner_db':sisdr(truth.owner_reference,x) if truth.owner_present else None,'selected_vs_owner_db':sisdr(truth.owner_reference,selected) if truth.owner_present and selected is not None else None,'selected_clipping_fraction':float(np.mean(np.abs(selected)>1)) if selected is not None else None,'raw':raw_result,'voice_check':baseline,'separated':outcome})
            save();print('Case',number,case['id'],'accepted',choice['accepted'],'added_cpu_ms',round(separation_ms+selection_ms),flush=True)
        monitor.check();status='complete' if len(rows)==45 else 'partial'
    except Exception as error:status='failed';failure=type(error).__name__+': '+str(error);raise
    finally:
        try:
            if worker:worker.close()
        finally:model.close();monitor.close();save()
        if torch.cuda.is_initialized() or torch.cuda.memory_allocated():raise RuntimeError('CPU trial initialized CUDA')
        print('Trial',status,'cases',len(rows),'no profile/audio saved; owned models closed. Report:',report_path,flush=True)

if __name__=='__main__':main()
