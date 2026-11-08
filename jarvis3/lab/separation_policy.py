"""Frozen experimental owner selection; no labels, transcripts or PC actions.

The existing lab cosine threshold is retained. The extra margin is declared
before evaluation; uncertainty refuses both streams rather than using an oracle.
Nothing imports this module in the production voice pipeline.
"""
import numpy as np
THRESHOLD=.25
MARGIN=.05
MIN_SAMPLES=16000
MIN_RMS=1e-4

def published_gain(mixture,streams):
    """Asteroid's shared L1 reconstruction gain, with a silence/finite guard.
    One gain applies to both outputs; no truth, per-stream boost or oracle.
    """
    x=np.asarray(mixture,dtype=np.float32);y=np.asarray(streams,dtype=np.float32)
    if x.ndim!=1 or y.shape!=(2,len(x)) or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('Invalid separation buffers')
    numerator=float(np.abs(x.astype(np.float64)).sum());denominator=float(np.abs(y.astype(np.float64)).sum())
    if numerator==0 or denominator<=1e-12:return np.zeros_like(y)
    result=y*(numerator/denominator)
    if not np.isfinite(result).all():raise ValueError('Invalid reconstruction gain')
    return result

def choose(streams,score):
    audio=np.asarray(streams,dtype=np.float32)
    result={'accepted':False,'index':None,'scores':[None,None],'reason':'invalid'}
    if audio.ndim!=2 or audio.shape[0]!=2 or not np.isfinite(audio).all():return result
    if audio.shape[1]<MIN_SAMPLES:return {**result,'reason':'short'}
    active=np.sqrt(np.mean(audio.astype(np.float64)**2,axis=1))>=MIN_RMS
    candidates=[]
    for i in range(2):
        if not active[i]:continue
        try:value=score(audio[i])
        except Exception:return {**result,'reason':'checker_error'}
        if value is None:return {**result,'reason':'unscored'}
        if not np.isfinite(value) or abs(value)>1.00001:return result
        value=float(value);result['scores'][i]=value;candidates.append((value,i))
    if not candidates:return {**result,'reason':'silence'}
    candidates.sort(reverse=True)
    best,index=candidates[0]
    if best<THRESHOLD:return {**result,'reason':'no_owner'}
    if len(candidates)>1 and best-candidates[1][0]<MARGIN:return {**result,'reason':'ambiguous'}
    return {**result,'accepted':True,'index':index,'reason':'owner_candidate'}

def check_original(audio,score):
    """Lab whole-mixture baseline; identity presence does not separate words."""
    x=np.asarray(audio,dtype=np.float32)
    if x.ndim!=1 or len(x)<MIN_SAMPLES or not np.isfinite(x).all():return {'accepted':False,'score':None}
    if np.sqrt(np.mean(x.astype(np.float64)**2))<MIN_RMS:return {'accepted':False,'score':None}
    try:value=score(x)
    except Exception:value=None
    valid=value is not None and np.isfinite(value) and abs(value)<=1.00001
    return {'accepted':bool(valid and value>=THRESHOLD),'score':float(value) if valid else None}
