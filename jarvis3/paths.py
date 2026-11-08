"""Absolute V3-owned state paths; original model weights are read-only resources."""
import os
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]
RUNTIME=Path(os.environ.get('JARVIS_V3_HOME',PROJECT/'data/v3')).resolve()
ASSETS=PROJECT/'jarvis3/assets'
DATA=RUNTIME/'data'
LOGS=RUNTIME/'logs'
if RUNTIME.is_relative_to(PROJECT) and not RUNTIME.is_relative_to(PROJECT/'data/v3'):
    raise RuntimeError('V3 state inside this project must stay under data/v3.')
if RUNTIME in (PROJECT,PROJECT/'data') or any(RUNTIME.is_relative_to(PROJECT/name) for name in ('jarvis','jarvis2','data/runtime','data/models')):
    raise RuntimeError('V3 state cannot use V1/V2 source, runtime or models.')
if any((RUNTIME/name).exists() for name in ('jarvis.db','settings2.json','jarvis2.db')):
    raise RuntimeError('V3 state must use its own folder, not V2 data.')

def prepare():
    DATA.mkdir(parents=True,exist_ok=True);LOGS.mkdir(parents=True,exist_ok=True)
    os.environ['HF_HUB_OFFLINE']='1'
    os.environ['HF_DATASETS_OFFLINE']='1'
    os.environ['JARVIS_REQUESTS']=str(DATA/'requests.md')

def enter():
    prepare();os.chdir(RUNTIME)
