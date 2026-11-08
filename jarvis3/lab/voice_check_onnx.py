"""Dormant CPU-only experiment, no torch dependency or automatic voice enrolment."""
import hashlib,json
from pathlib import Path
import numpy as np

class OnnxVoiceCheck:
    def __init__(self,folder):
        import onnxruntime as ort
        folder=Path(folder);path=folder/'voice-check-fp32.onnx'
        info=json.loads((folder/'export.json').read_text(encoding='utf-8'))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=info['onnx_sha256'] or info['precision']!='float32':raise ValueError('Unverified voice-check export')
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        self.profile=None
    def embedding(self,audio):
        if len(audio)<16000:return None
        vector=self.session.run(None,{'audio':np.asarray(audio,dtype=np.float32).reshape(1,-1)})[0].reshape(-1)
        if not np.isfinite(vector).all():return None
        return vector/max(np.linalg.norm(vector),1e-12)
    def enroll(self,clips):
        vectors=[self.embedding(a) for a in clips]
        if len(vectors)<3 or any(v is None for v in vectors):raise ValueError('Use three separate clips of at least one second')
        self.profile=np.mean(vectors,axis=0);self.profile/=max(np.linalg.norm(self.profile),1e-12)
    def score(self,audio):
        if self.profile is None:raise ValueError('No explicit voice profile')
        vector=self.embedding(audio)
        return None if vector is None else float(np.dot(self.profile,vector))
