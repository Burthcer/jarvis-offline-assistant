"""Separate, CPU-only ConvTasNet lab. Never imported by the assistant runtime.

Fixed operator graph audited against Asteroid v0.4.0 ConvTasNet/TDConvNet,
GlobLN and asteroid-filterbanks FreeFB. No checkpoint-selected constructors,
repository execution, hub access, automatic resampling or dependency installs.

The publisher card says 16k training. Asteroid v0.4.0's LibriMix recipe passed
the data rate to the dataset but omitted it from ConvTasNet construction,
leaving the FreeFB sample-rate metadata at its 8000 default. FreeFB's learned
convolutions do not use that metadata numerically. We retain 8000 as serialized
metadata and explicitly evaluate 16000 Hz, rather than silently downsample.
Primary evidence:
https://github.com/asteroid-team/asteroid/blob/v0.4.0/egs/librimix/ConvTasNet/train.py
https://github.com/asteroid-team/asteroid/blob/v0.4.0/asteroid/models/conv_tasnet.py
https://github.com/asteroid-team/asteroid/blob/v0.4.0/asteroid/masknn/convolutional.py
https://github.com/asteroid-team/asteroid/blob/v0.4.0/asteroid/masknn/norms.py
"""
import hashlib,os
from pathlib import Path

REVISION='e1ef95ab7a037950f3a606b9a56760cf94701d3d'
SHA256='8d97f012f7b2f22bb79cb0d0983a7ba27a52c1796ee3f63cbf25b4d28630adce'
SIZE=20394640
MODEL_ARGS={'fb_name':'FreeFB','n_filters':512,'kernel_size':32,'stride':16,'sample_rate':8000,
            'in_chan':512,'out_chan':512,'bn_chan':128,'hid_chan':512,'skip_chan':128,
            'conv_kernel_size':3,'n_blocks':8,'n_repeats':3,'n_src':2,'norm_type':'gLN',
            'mask_act':'relu','encoder_activation':None}

def tensor_shapes():
    shapes={'encoder.filterbank._filters':(512,1,32),'decoder.filterbank._filters':(512,1,32),
            'masker.bottleneck.0.gamma':(512,),'masker.bottleneck.0.beta':(512,),
            'masker.bottleneck.1.weight':(128,512,1),'masker.bottleneck.1.bias':(128,),
            'masker.mask_net.0.weight':(1,),'masker.mask_net.1.weight':(1024,128,1),'masker.mask_net.1.bias':(1024,)}
    for i in range(24):
        prefix=f'masker.TCN.{i}.'
        for key,shape in {'shared_block.0.weight':(512,128,1),'shared_block.0.bias':(512,),
                          'shared_block.1.weight':(1,),'shared_block.2.gamma':(512,),'shared_block.2.beta':(512,),
                          'shared_block.3.weight':(512,1,3),'shared_block.3.bias':(512,),
                          'shared_block.4.weight':(1,),'shared_block.5.gamma':(512,),'shared_block.5.beta':(512,),
                          'res_conv.weight':(128,512,1),'res_conv.bias':(128,),
                          'skip_conv.weight':(128,512,1),'skip_conv.bias':(128,)}.items():shapes[prefix+key]=shape
    return shapes

def validate_state(torch,data):
    if not isinstance(data,dict) or data.get('model_name')!='ConvTasNet' or data.get('model_args')!=MODEL_ARGS:raise ValueError('Unexpected separator architecture/configuration')
    if data.get('dataset')!='Libri2Mix' or data.get('task')!='sep_clean':raise ValueError('Unexpected separator training task')
    if data.get('infos',{}).get('software_versions',{}).get('asteroid_version')!='0.4.0':raise ValueError('Unexpected separator source version')
    state=data.get('state_dict');shapes=tensor_shapes()
    if not isinstance(state,dict) or state.keys()!=shapes.keys():raise ValueError('Unexpected separator tensor keys')
    for key,shape in shapes.items():
        value=state[key]
        if type(value) is not torch.Tensor or value.device.type!='cpu' or value.dtype!=torch.float32 or value.layout!=torch.strided or tuple(value.shape)!=shape:raise ValueError('Unexpected separator tensor: '+key)
        if not bool(torch.isfinite(value).all()):raise ValueError('Non-finite separator tensor: '+key)
    return {key:value.detach().contiguous() for key,value in state.items()}

class ConvTasNetCPU:
    sample_rate=16000
    serialized_sample_rate=8000
    def __init__(self,path=None):
        if os.environ.get('CUDA_VISIBLE_DEVICES')!='-1':raise ValueError('Use the separate CPU-only lab process')
        if path is None:path=Path(__file__).resolve().parents[2]/'data/v3/lab/separation/pytorch_model.bin'
        path=Path(path)
        if path.stat().st_size!=SIZE or hashlib.sha256(path.read_bytes()).hexdigest()!=SHA256:raise ValueError('Unverified separator checkpoint')
        import torch
        if torch.cuda.is_initialized():raise ValueError('The separator lab process already initialised CUDA')
        self.torch=torch
        data=torch.load(path,map_location='cpu',weights_only=True)
        self.state=validate_state(torch,data)
        self.metadata={'revision':REVISION,'sha256':SHA256,'serialized_sample_rate':8000,'effective_sample_rate':16000,'source_version':'asteroid0.4.0','inference':'fixed Torch CPU graph; no from_pretrained','parameters':sum(v.numel() for v in self.state.values())}

    def separate(self,audio,sample_rate=16000):
        """Raw official model.forward parity, not Asteroid's L1-gain wrapper.

        Evaluation may apply one guarded global published gain to both streams;
        that policy belongs outside this fixed graph and cannot pick a speaker.
        """
        if sample_rate!=self.sample_rate:raise ValueError('The trial requires explicit 16000 Hz input')
        if self.state is None:raise ValueError('Separator lab is closed')
        torch=self.torch;F=torch.nn.functional;weights=self.state
        if isinstance(audio,torch.Tensor) and audio.device.type!='cpu':raise ValueError('CPU input only')
        x=torch.as_tensor(audio,dtype=torch.float32,device='cpu')
        if x.ndim!=1 or not 32<=x.numel()<=12*self.sample_rate or not bool(torch.isfinite(x).all()):raise ValueError('Use finite mono lab audio between 32 samples and 12 seconds')
        def conv(value,prefix,**kwargs):return F.conv1d(value,weights[prefix+'.weight'],weights[prefix+'.bias'],**kwargs)
        def norm(value,prefix):
            centered=value-value.mean(dim=(1,2),keepdim=True)
            normalized=centered/(value.var(dim=(1,2),keepdim=True,unbiased=False)+1e-8).sqrt()
            return normalized*weights[prefix+'.gamma'][None,:,None]+weights[prefix+'.beta'][None,:,None]
        with torch.inference_mode():
            encoded=F.conv1d(x[None,None,:],weights['encoder.filterbank._filters'],stride=16)
            hidden=conv(norm(encoded,'masker.bottleneck.0'),'masker.bottleneck.1')
            skip=torch.zeros_like(hidden)
            for i in range(24):
                prefix=f'masker.TCN.{i}.'
                shared=conv(hidden,prefix+'shared_block.0')
                shared=norm(F.prelu(shared,weights[prefix+'shared_block.1.weight']),prefix+'shared_block.2')
                shared=conv(shared,prefix+'shared_block.3',padding=2**(i%8),dilation=2**(i%8),groups=512)
                shared=norm(F.prelu(shared,weights[prefix+'shared_block.4.weight']),prefix+'shared_block.5')
                residual=conv(shared,prefix+'res_conv');block_skip=conv(shared,prefix+'skip_conv')
                skip=skip+block_skip;hidden=hidden+residual
            masks=conv(F.prelu(skip,weights['masker.mask_net.0.weight']),'masker.mask_net.1').reshape(1,2,512,-1).relu()
            masked=(masks*encoded[:,None,:,:]).reshape(2,512,-1)
            result=F.conv_transpose1d(masked,weights['decoder.filterbank._filters'],stride=16)[:,0,:]
            result=F.pad(result,(0,x.numel()-result.shape[-1]))
            if result.shape!=(2,x.numel()) or not bool(torch.isfinite(result).all()):raise ValueError('Invalid separator output')
            return result.numpy().copy()

    def close(self):self.state=None
