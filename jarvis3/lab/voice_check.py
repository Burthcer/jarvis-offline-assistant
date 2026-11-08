"""CPU-only voice similarity experiment, NOT speech separation/authentication."""
import hashlib,json
from pathlib import Path

class VoiceCheck:
    def __init__(self,folder):
        import torch
        from speechbrain.lobes.features import Fbank
        from speechbrain.processing.features import InputNormalization
        from speechbrain.lobes.models.ECAPA_TDNN import ECAPA_TDNN
        folder=Path(folder)
        info=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        path=folder/'embedding_model.ckpt'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=info['files'][path.name]['sha256']:raise ValueError('Voice-check weight checksum changed')
        self.torch=torch
        self.features=Fbank(n_mels=80).eval()
        self.norm=InputNormalization(norm_type='sentence',std_norm=False).eval()
        self.model=ECAPA_TDNN(input_size=80,channels=[1024,1024,1024,1024,3072],kernel_sizes=[5,3,3,3,1],dilations=[1,2,3,4,1],attention_channels=128,lin_neurons=192).eval()
        self.model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True)
        self.profile=None

    def embedding(self,audio):
        torch=self.torch
        if len(audio)<16000:return None  # short wake words cannot identify a voice reliably
        with torch.inference_mode():
            signal=torch.as_tensor(audio,dtype=torch.float32,device='cpu').reshape(1,-1)
            features=self.norm(self.features(signal),torch.ones(1))
            vector=self.model(features,torch.ones(1)).reshape(-1)
            return torch.nn.functional.normalize(vector,dim=0)

    def enroll(self,clips):
        vectors=[self.embedding(a) for a in clips]
        if len(vectors)<3 or any(v is None for v in vectors):raise ValueError('Use at least three separate clips of one second or longer')
        self.profile=self.torch.nn.functional.normalize(self.torch.stack(vectors).mean(0),dim=0)

    def score(self,audio):
        if self.profile is None:raise ValueError('No explicit voice profile')
        vector=self.embedding(audio)
        return None if vector is None else float(self.torch.dot(self.profile,vector))
