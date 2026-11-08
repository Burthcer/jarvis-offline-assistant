"""Offline independent forward oracle from two checksum-pinned official wheels.

Only audited architecture definitions are selected from Asteroid0.4.0 and
asteroid-filterbanks0.3.0. Package initializers, imports, hub/deserialization,
training, file and network helpers never run. The unchanged upstream forward
methods instantiate a real nn.Module; the lab implementation is functional.
"""
import ast,hashlib,inspect,types,warnings,zipfile
from pathlib import Path
from typing import List,Optional

WHEELS={
    'asteroid-0.4.0-py3-none-any.whl':(221880,'0aaf5436a51e1cbf049aa70fc12938d10033d2840db0fbd34297e84d6df69288'),
    'asteroid_filterbanks-0.3.0-py3-none-any.whl':(26943,'339a660efe0f212bda7905a14be04b24394c2974b3bff1df43a567460ebb6486')}

def definitions(path,member,names,namespace,methods=None):
    expected_size,expected_hash=WHEELS[path.name]
    if path.stat().st_size!=expected_size or hashlib.sha256(path.read_bytes()).hexdigest()!=expected_hash:raise ValueError('Unverified official architecture wheel')
    with zipfile.ZipFile(path) as archive:source=archive.read(member).decode('utf-8')
    nodes=[n for n in ast.parse(source).body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    if {n.name for n in nodes}!=set(names):raise ValueError('Missing official architecture definition')
    for node in nodes:
        if methods and isinstance(node,ast.ClassDef):
            node.body=[m for m in node.body if isinstance(m,ast.FunctionDef) and m.name in methods]
    # Fixed allowlisted official library code only. Never model repository code
    # or checkpoint-selected names. No imports/package initialization execute.
    exec(compile(ast.Module(body=nodes,type_ignores=[]),member,'exec'),namespace)

def reference_class(folder,torch):
    folder=Path(folder);asteroid=folder/'asteroid-0.4.0-py3-none-any.whl';filters=folder/'asteroid_filterbanks-0.3.0-py3-none-any.whl'
    base={'torch':torch,'nn':torch.nn,'F':torch.nn.functional,'warnings':warnings,'List':List,'Optional':Optional,'script_if_tracing':lambda fn:fn,'__name__':'trusted_separation_reference'}
    fb=dict(base)
    definitions(filters,'asteroid_filterbanks/enc_dec.py',{'Filterbank','_EncDec','Encoder','Decoder','multishape_conv1d','batch_packed_1d_conv','multishape_conv_transpose1d'},fb)
    definitions(filters,'asteroid_filterbanks/free_fb.py',{'FreeFB'},fb)
    definitions(filters,'asteroid_filterbanks/__init__.py',{'get','make_enc_dec'},fb)
    norms=dict(base,EPS=1e-8)
    definitions(asteroid,'asteroid/masknn/norms.py',{'z_norm','_glob_norm','_LayerNorm','GlobLN'},norms)
    activation_map={None:torch.nn.Identity,'linear':torch.nn.Identity,'relu':torch.nn.ReLU}
    activations=types.SimpleNamespace(get=lambda name:activation_map[name])
    conv=dict(base,norms=types.SimpleNamespace(get=lambda name:{'gLN':norms['GlobLN']}[name]),activations=activations,inspect=inspect)
    definitions(asteroid,'asteroid/utils/generic_utils.py',{'has_arg'},conv)
    definitions(asteroid,'asteroid/masknn/convolutional.py',{'Conv1DBlock','TDConvNet'},conv)
    encoder=dict(base,activations=activations)
    definitions(asteroid,'asteroid/utils/torch_utils.py',{'pad_x_to_y','jitable_shape'},encoder)
    definitions(asteroid,'asteroid/models/base_models.py',{'BaseModel'},encoder,methods={'__init__','forward','sample_rate'})
    definitions(asteroid,'asteroid/models/base_models.py',{'_unsqueeze_to_3d','_shape_reconstructed'},encoder)
    definitions(asteroid,'asteroid/models/base_models.py',{'BaseEncoderMaskerDecoder'},encoder,methods={'__init__','forward','forward_encoder','forward_masker','apply_masks','forward_decoder'})
    model=dict(base,make_enc_dec=fb['make_enc_dec'],TDConvNet=conv['TDConvNet'],BaseEncoderMaskerDecoder=encoder['BaseEncoderMaskerDecoder'])
    definitions(asteroid,'asteroid/models/conv_tasnet.py',{'ConvTasNet'},model)
    return model['ConvTasNet']
