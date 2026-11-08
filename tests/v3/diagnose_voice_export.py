"""Locate CPU export round-off; no profile, microphone, speakers or app actions."""
import os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['HF_HUB_OFFLINE']='1'
sys.path.append(r'C:\Users\USER\Desktop\Wisperno-pro\.venv\Lib\site-packages')
import torch,numpy as np,onnx,onnxruntime as ort,soundfile as sf
torch.set_num_threads(2)
from jarvis3.lab.voice_check import VoiceCheck
folder=ROOT/'data/v3/lab/model';reference=VoiceCheck(folder)
graph=onnx.load(folder/'voice-check-fp32.onnx')
graph.graph.output.append(onnx.helper.make_tensor_value_info('/Sub_output_0',onnx.TensorProto.FLOAT,None))
options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
session=ort.InferenceSession(graph.SerializeToString(),sess_options=options,providers=['CPUExecutionProvider'])
speech,rate=sf.read(ROOT/'data/feedback-audio/command.wav',dtype='float32');assert rate==16000
for label,audio in [('tone',np.sin(np.arange(32000,dtype=np.float32)/13)*.1),('speech',speech[:32000])]:
    with torch.inference_mode():
        raw=reference.features(torch.tensor(audio).reshape(1,-1))
        normalized=reference.norm(raw,torch.ones(1))
        direct=raw-raw.mean(dim=1,keepdim=True)
        expected=reference.embedding(audio).numpy()
    actual,features=session.run(None,{'audio':audio.reshape(1,-1)})
    actual=actual.reshape(-1)
    print(label,{'normalization_implementation_error':float(torch.max(torch.abs(normalized-direct))),'feature_max_error':float(np.max(np.abs(features-normalized.numpy()))),'embedding_max_error':float(np.max(np.abs(actual-expected))),'embedding_cosine':float(np.dot(actual,expected))},flush=True)
