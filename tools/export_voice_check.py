"""Float32 export of the approved lab weights. No quantisation/model replacement."""
import os,sys,json,hashlib,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['HF_HUB_OFFLINE']='1'
sys.path.append(r'C:\Users\USER\Desktop\Wisperno-pro\.venv\Lib\site-packages')
import torch
torch.set_num_threads(2)
import numpy as np
import soundfile as sf
import onnxruntime as ort
from jarvis3.lab.voice_check import VoiceCheck
folder=ROOT/'data/v3/lab/model';reference=VoiceCheck(folder)
sample=torch.sin(torch.arange(32000,dtype=torch.float32)/13).reshape(1,-1)*.1
with torch.inference_mode():before=reference.features(sample)
def real_stft(self,x):
    return torch.stft(x,self.n_fft,self.hop_length,self.win_length,self.window.to(x.device),self.center,self.pad_mode,self.normalized_stft,self.onesided,return_complex=False).transpose(2,1)
reference.features.compute_STFT.forward=types.MethodType(real_stft,reference.features.compute_STFT)
with torch.inference_mode():after=reference.features(sample)
feature_error=float(torch.max(torch.abs(before-after)))
assert feature_error<1e-5,feature_error
class Export(torch.nn.Module):
    def __init__(self):super().__init__();self.features=reference.features;self.encoder=reference.model
    def forward(self,audio):
        features=self.features(audio)
        features=features-features.mean(dim=1,keepdim=True)
        vector=self.encoder(features,torch.ones(1)).reshape(1,-1)
        return torch.nn.functional.normalize(vector,dim=1)
wrapper=Export().eval();path=folder/'voice-check-fp32.onnx'
torch.onnx.export(wrapper,sample,str(path),opset_version=17,input_names=['audio'],output_names=['embedding'],dynamic_axes={'audio':{1:'samples'}},do_constant_folding=True,dynamo=False)
options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
errors=[]
speech,rate=sf.read(ROOT/'data/feedback-audio/command.wav',dtype='float32');assert rate==16000
for length in (16000,32000,48000):
    audio=np.resize(speech,length).astype(np.float32)
    expected=reference.embedding(audio).numpy()
    actual=session.run(None,{'audio':audio.reshape(1,-1)})[0].reshape(-1)
    error=float(np.max(np.abs(actual-expected)));errors.append(error)
    assert error<1e-4,(length,error)
info={'weights_manifest':json.loads((folder/'manifest.json').read_text()),'precision':'float32','onnx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'stft_feature_max_error':feature_error,'speech_embedding_max_errors':errors,'providers':session.get_providers(),'scope':'Lab only; full holdout decision parity required. Pure-tone stress has larger cross-runtime spectral round-off; see diagnostic.'}
(folder/'export.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
print('Same-weight float32 CPU export verified:',errors,flush=True)
