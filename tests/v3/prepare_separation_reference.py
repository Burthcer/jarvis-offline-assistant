"""Fetch only tiny official pinned architecture wheels for isolated parity QA.

No install, import, model download, package-init or checkpoint execution.
Release hashes checked against official PyPI metadata on 7 November2026.
"""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
FOLDER=ROOT/'data/v3/lab/separation/reference'
FILES=[
    ('asteroid-0.4.0-py3-none-any.whl',221880,'0aaf5436a51e1cbf049aa70fc12938d10033d2840db0fbd34297e84d6df69288','https://files.pythonhosted.org/packages/6a/c2/e2a23266374546f3e5f14e6cac5c1bc6ab1a7d49ecaa643162021cbb48b9/asteroid-0.4.0-py3-none-any.whl'),
    ('asteroid_filterbanks-0.3.0-py3-none-any.whl',26943,'339a660efe0f212bda7905a14be04b24394c2974b3bff1df43a567460ebb6486','https://files.pythonhosted.org/packages/9a/4d/6b495269b9e5ae93647d47316ff51585047d3c689ee67c3c84ff33bc30e9/asteroid_filterbanks-0.3.0-py3-none-any.whl')]

def main():
    FOLDER.mkdir(parents=True,exist_ok=True);records=[]
    for filename,size,digest,url in FILES:
        path=FOLDER/filename
        if not path.exists():
            with urllib.request.urlopen(url,timeout=20) as response:body=response.read(size+1)
            if len(body)!=size or hashlib.sha256(body).hexdigest()!=digest:raise ValueError('Official reference wheel checksum mismatch')
            with path.open('xb') as target:target.write(body)
        if path.stat().st_size!=size or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Cached architecture wheel changed')
        records.append({'filename':filename,'bytes':size,'sha256':digest,'source':url})
    (FOLDER/'reference-sources.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print('Pinned official architecture sources verified; no packages installed or executed.')

if __name__=='__main__':main()
