"""Explicitly approved CPU-only experiment. No writes to V2 or Wisperno."""
import os,sys,json,hashlib,subprocess,venv
from pathlib import Path
from urllib.request import urlopen,Request
ROOT=Path(__file__).resolve().parents[1]
LAB=(ROOT/'data/v3/lab').resolve();LAB.mkdir(parents=True,exist_ok=True)
assert LAB.is_relative_to((ROOT/'data/v3').resolve())
ENV=LAB/'env';python=ENV/'Scripts/python.exe'
if not python.exists():venv.EnvBuilder(with_pip=True,system_site_packages=True).create(ENV)
subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','--no-deps','-r',str(ROOT/'jarvis3/lab/requirements.txt')],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
def get_json(url):
    with urlopen(Request(url,headers={'User-Agent':'JarvisV3-local-approved-test'}),timeout=30) as response:return json.load(response)
revision='0f99f2d0ebe89ac095bcc5903c4dd8f72b367286'
info=get_json('https://huggingface.co/api/models/speechbrain/spkrec-ecapa-voxceleb/revision/'+revision+'?blobs=true')
assert info['sha']==revision,'Unexpected model revision'
files={item['rfilename']:item for item in info['siblings']}
target=LAB/'model';target.mkdir(exist_ok=True)
manifest={'model':'speechbrain/spkrec-ecapa-voxceleb','revision':revision,'files':{}}
for name in ('embedding_model.ckpt',):
    expected=files[name]['lfs']['sha256'];size=files[name]['lfs']['size']
    assert expected=='0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2' and size==83316686,'Unapproved model content'
    assert size<90*1024**2,'Unapproved model size'
    path=target/name
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        part=target/(name+'.part');h=hashlib.sha256();count=0
        with urlopen('https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb/resolve/'+revision+'/'+name,timeout=60) as response,part.open('wb') as output:
            while chunk:=response.read(1024*1024):
                count+=len(chunk)
                if count>size:raise RuntimeError('Download exceeded declared size')
                output.write(chunk);h.update(chunk)
        assert count==size and h.hexdigest()==expected,'Model checksum mismatch'
        part.replace(path)
    manifest['files'][name]={'sha256':expected,'bytes':size}
    print('Verified model bytes:',size,flush=True)
(target/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Approved CPU experiment prepared. Nothing enabled in V2 or V3.',flush=True)
