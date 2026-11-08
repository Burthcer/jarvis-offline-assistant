"""Explicit isolated CPU lab check, never a normal Jarvis/UI test or enablement."""
import os,sys,json,time,tempfile
from pathlib import Path
from unittest.mock import patch
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['JARVIS_SILENT']='1';os.environ['HF_HUB_OFFLINE']='1'
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(Path(__file__).resolve().parent)]
sys.path.append(r'C:\Users\USER\Desktop\Wisperno-pro\.venv\Lib\site-packages')
import torch,numpy as np
torch.set_num_threads(2);torch.set_num_interop_threads(1)
from jarvis3.lab.separation import ConvTasNetCPU,MODEL_ARGS,tensor_shapes,validate_state
from separation_reference import reference_class,WHEELS
LAB=ROOT/'data/v3/lab/separation'
model=ConvTasNetCPU();reference=None;results=[]
try:
    assert len(tensor_shapes())==345 and model.metadata['parameters']==5066929
    Ref=reference_class(LAB/'reference',torch)
    reference=Ref(**MODEL_ARGS).cpu().eval();reference.load_state_dict(model.state,strict=True)
    reference.requires_grad_(False)
    assert reference.sample_rate==8000 and model.serialized_sample_rate==8000 and model.sample_rate==16000
    rng=np.random.default_rng(923)
    for audio in (np.zeros(1600,np.float32),rng.normal(0,.03,1600).astype(np.float32),rng.normal(0,.03,1613).astype(np.float32)):
        start=time.perf_counter();actual=model.separate(audio)
        with torch.inference_mode():expected=reference(torch.from_numpy(audio)).numpy()
        delta=float(np.max(np.abs(actual-expected)))
        assert actual.shape==expected.shape==(2,len(audio)) and np.isfinite(actual).all()
        assert np.allclose(actual,expected,rtol=1e-5,atol=1e-6),delta
        results.append({'samples':len(audio),'max_abs_difference':delta,'two_forwards_ms':round((time.perf_counter()-start)*1000)})
    # Changing the reference's rate metadata leaves all numeric operations the
    # same: direct forward has no hidden resampling or gain normalisation.
    ref16=Ref(**{**MODEL_ARGS,'sample_rate':16000}).cpu().eval();ref16.load_state_dict(model.state,strict=True)
    with torch.inference_mode():
        x=torch.from_numpy(rng.normal(0,.03,1600).astype(np.float32))
        assert torch.equal(reference(x),ref16(x))
    del ref16
    data={'model_name':'ConvTasNet','model_args':dict(MODEL_ARGS),'state_dict':model.state,'dataset':'Libri2Mix','task':'sep_clean','infos':{'software_versions':{'asteroid_version':'0.4.0'}}}
    invalid=[]
    extra=dict(model.state,unexpected=torch.zeros(1));invalid.append({**data,'state_dict':extra})
    bad=dict(model.state);bad['masker.mask_net.0.weight']=torch.tensor([float('nan')]);invalid.append({**data,'state_dict':bad})
    bad=dict(model.state);bad['masker.mask_net.0.weight']=torch.zeros(2);invalid.append({**data,'state_dict':bad})
    invalid.append({**data,'model_args':{**MODEL_ARGS,'sample_rate':16000}})
    for value in invalid:
        try:validate_state(torch,value);raise AssertionError('invalid architecture accepted')
        except ValueError:pass
    for audio,rate in ((np.zeros(31,np.float32),16000),(np.zeros((2,100),np.float32),16000),(np.array([np.nan]*32,np.float32),16000),(np.zeros(32,np.float32),8000)):
        try:model.separate(audio,rate);raise AssertionError('invalid input accepted')
        except ValueError:pass
    with tempfile.TemporaryDirectory(prefix='v3-owned-separation-check-') as temp:
        wrong=Path(temp)/'bad.bin';wrong.write_bytes(b'not a model')
        with patch.object(torch,'load',side_effect=AssertionError('unverified file reached deserialization')):
            try:ConvTasNetCPU(wrong);raise AssertionError('wrong checkpoint accepted')
            except ValueError:pass
    assert not torch.cuda.is_initialized()
    report={**model.metadata,'reference_wheels':WHEELS,'parity':results,'cuda_initialized':False,'checks':'strict config/key/shape/finites/hash, CPU/mono/rate/length, independent official forward parity; no production enablement',
            'sample_rate_evidence':{'publisher_training_card':16000,'serialized_metadata':8000,'checkpoint_asteroid_version':'0.4.0','explanation':'Version0.4.0 LibriMix recipe passes data sample_rate to dataset but omits it from ConvTasNet construction; FreeFB defaults8000 metadata and does not resample. Card/recipe support16k evaluation; cannot prove training provenance solely from tensors.','recipe':'https://github.com/asteroid-team/asteroid/blob/v0.4.0/egs/librimix/ConvTasNet/train.py','constructor':'https://github.com/asteroid-team/asteroid/blob/v0.4.0/asteroid/models/conv_tasnet.py'},
            'gain_policy':'This class matches raw model.forward. Official asteroid/separate.py convenience wrapper multiplies both outputs by abs(input).sum()/abs(outputs).sum(), undefined0/0 on silence. Root evaluation freezes a guarded shared gain (zero denominator=>zero outputs), outside the graph; no per-stream/oracle scaling.'}
    (LAB/'architecture-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
finally:
    model.close();del reference
    assert not torch.cuda.is_initialized()
