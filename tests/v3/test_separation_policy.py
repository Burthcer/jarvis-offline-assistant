"""Stream selection never sees expected words/labels or chooses an oracle stream."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import numpy as np
from jarvis3.lab.separation_policy import choose,check_original,published_gain
a=np.ones(32000,np.float32)*.1;b=np.ones(32000,np.float32)*.2
score=lambda x:.8 if x[0]<.15 else .1
assert choose([a,b],score)['index']==0
assert choose([b,a],score)['index']==1
assert not choose([a,b],lambda x:.6)['accepted']
assert not choose([a,b],lambda x:.2)['accepted']
assert not choose([a,b],lambda x:None)['accepted']
assert not choose([a,b],lambda x:float('nan'))['accepted']
def bad(x):raise ValueError('owned fake checker failure')
assert not choose([a,b],bad)['accepted']
assert choose([a,np.zeros_like(a)],score)['index']==0
assert not choose(np.zeros((2,32000)),score)['accepted']
assert not choose(np.ones((2,12800)),score)['accepted']
assert not choose(np.zeros((1,32000)),score)['accepted']
assert check_original(a,score)['accepted'] and not check_original(b,score)['accepted']
assert not check_original(np.zeros(32000),score)['accepted']
assert not check_original(a[:12000],score)['accepted']
streams=np.stack([a,b]);mix=a+b;scaled=published_gain(mix,streams*.2)
assert np.allclose(scaled,streams) and np.allclose(scaled[1]/scaled[0],2),'gain changed source ratio'
assert not published_gain(np.zeros_like(a),streams).any()
assert not published_gain(a,np.zeros_like(streams)).any()
print('SEPARATION POLICY: permutation, no oracle, ambiguity/short/silent/invalid/checker failure rejection and fixed baseline passed')
