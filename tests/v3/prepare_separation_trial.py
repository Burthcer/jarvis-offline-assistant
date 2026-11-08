"""Approved separate lab download only; never imports/runs model/repository code."""
import hashlib,json,tempfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
LAB=ROOT/'data/v3/lab/separation'
REPO='JorisCos/ConvTasNet_Libri2Mix_sepclean_16k'
REVISION='e1ef95ab7a037950f3a606b9a56760cf94701d3d'
SIZE=20394640
SHA256='8d97f012f7b2f22bb79cb0d0983a7ba27a52c1796ee3f63cbf25b4d28630adce'

def main():
    LAB.mkdir(parents=True,exist_ok=True)
    weight=LAB/'pytorch_model.bin'
    if not weight.exists():
        part=None
        try:
            with tempfile.NamedTemporaryFile(dir=LAB,suffix='.part',delete=False) as output:
                part=Path(output.name);total=0;digest=hashlib.sha256()
                url=f'https://huggingface.co/{REPO}/resolve/{REVISION}/pytorch_model.bin'
                with urllib.request.urlopen(url,timeout=30) as response:
                    while chunk:=response.read(1024*1024):
                        total+=len(chunk)
                        if total>SIZE:raise ValueError('Unexpected model size')
                        output.write(chunk);digest.update(chunk)
            if total!=SIZE or digest.hexdigest()!=SHA256:raise ValueError('Model checksum mismatch')
            if weight.exists():raise ValueError('Target appeared during download; refusing overwrite')
            part.replace(weight);part=None
        finally:
            if part:part.unlink(missing_ok=True)
    if weight.stat().st_size!=SIZE or hashlib.sha256(weight.read_bytes()).hexdigest()!=SHA256:raise ValueError('Existing lab model checksum mismatch')
    with urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/README.md',timeout=20) as response:
        card=response.read(65536)
        if response.read(1):raise ValueError('Unexpected model card size')
    (LAB/'UPSTREAM_README.md').write_bytes(card)
    manifest={'model':REPO,'revision':REVISION,'file':weight.name,'bytes':SIZE,'sha256':SHA256,'publisher_metadata_license':'cc-by-sa-4.0','status':'download verified; not loaded or enabled','approval':'the owner approved separate CPU trial; production enablement not approved'}
    (LAB/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Approved lab weights verified:',SIZE,'bytes; CPU test not run; Jarvis unchanged',flush=True)

if __name__=='__main__':main()
