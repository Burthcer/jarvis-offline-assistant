"""Pure matrix/source checks: no speaker/separator/STT models or audio output."""
import os,sys,json,hashlib,tempfile,wave
from pathlib import Path
from dataclasses import fields
from unittest.mock import patch
import numpy as np
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(Path(__file__).resolve().parent)]
import separation_cases as S

matrix=S.primary_cases();assert len(matrix)==45 and len({c.id for c in matrix})==45
assert {kind:sum(c.kind==kind for c in matrix) for kind in ('clean','overlap','nonoverlap','other','silence')}=={'clean':8,'overlap':24,'nonoverlap':8,'other':4,'silence':1}
assert not set(S.ENROLLMENT)&(set(S.TUNING)|set(S.HELDOUT)) and not set(S.TUNING)&set(S.HELDOUT)
assert not set(S.OTHERS['tuning'])&set(S.OTHERS['heldout'])
assert all(c.owner_id not in S.ENROLLMENT for c in matrix)
assert all(c.owner_id in S.TUNING for c in matrix if c.owner_id and c.split=='tuning')
assert all(c.owner_id in S.HELDOUT for c in matrix if c.owner_id and c.split=='heldout')
assert tuple(f.name for f in fields(S.Signal))==('audio','rate'),'inference input contains grader/oracle data'
assert S.frozen_manifest()==S.frozen_manifest() and not S.frozen_manifest()['selection_policy']['oracle_stream_selection']

rate=S.RATE;t=np.arange(2*rate)/rate
owner=(np.sin(2*np.pi*197*t)*(1+.2*np.cos(2*np.pi*2*t))).astype(np.float32)
other=(np.sin(2*np.pi*431*np.arange(5*rate)/rate)*(.1+np.arange(5*rate)/(5*rate))).astype(np.float32)
for offset in (-.8,0,.8):
    for ratio in S.RATIOS:
        signal,truth=S.mix(S.Case('fake','tuning','overlap','n04','kokoro_bm_daniel.wav',ratio,offset),owner,other)
        assert signal.rate==rate and signal.audio.dtype==np.float32 and np.isfinite(signal.audio).all()
        assert abs(signal.audio).max()<=.600001 and np.array_equal(signal.audio,truth.owner_reference+truth.other_reference)
        a,b=truth.source_spans
        assert a.input_start==round((.25+max(0,-offset))*rate) and b.input_start==round((.25+max(0,offset))*rate)
        assert a.input_end-a.input_start==len(owner)==b.input_end-b.input_start and truth.owner_complete
        rms=lambda x:np.sqrt(np.mean(x.astype(np.float64)**2))
        measured=20*np.log10(rms(truth.owner_reference[a.input_start:a.input_end])/rms(truth.other_reference[b.input_start:b.input_end]))
        assert abs(measured-ratio)<.0001,(measured,ratio)
for first in (True,False):
    signal,truth=S.mix(S.Case('fake','heldout','nonoverlap','n05','kokoro_bm_fable.wav',owner_first=first),owner,other)
    a,b=truth.source_spans;assert truth.owner_complete and not np.any((truth.owner_reference!=0)&(truth.other_reference!=0))
    assert (b.input_start-a.input_end if first else a.input_start-b.input_end)==round(.4*rate)
signal,truth=S.mix(S.Case('fake','control','silence',seconds=3))
assert len(signal.audio)==3*rate and not np.any(signal.audio) and not truth.owner_present and not truth.source_spans
for case in S.performance_cases():
    signal,truth=S.mix(case,owner,other)
    assert len(signal.audio)==round(case.seconds*rate) and not truth.command_grade and truth.expected_text is None

# A miniature owned PCM corpus verifies hash-before-parse, exact resampling,
# source bounds and grader separation. These are generated fake samples.
with tempfile.TemporaryDirectory(prefix='v3-separation-corpus-') as home:
    root=Path(home);hashes={}
    def write(relative,data):
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        hashes[relative]=hashlib.sha256(data).hexdigest()
    import io
    def pcm(rate,count):
        target=io.BytesIO()
        with wave.open(target,'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
            out.writeframes((np.sin(np.arange(count)*.11)*4000).astype('<i2').tobytes())
        return target.getvalue()
    identifiers=S.ENROLLMENT+S.TUNING+S.HELDOUT
    takes=[{'id':identifier,'start':.1,'end':1.3} for identifier in identifiers]
    write('data/gold/audio/session.json',json.dumps({'sections':{'quiet':{'takes':takes}}}).encode())
    write('data/gold/audio/quiet.wav',pcm(rate,rate*2))
    write('tests/v2/prompts.json',json.dumps({'named':[{'id':identifier,'say':'FAKE '+identifier,'expect':{'fake':identifier}} for identifier in identifiers]}).encode())
    for voices in S.OTHERS.values():
        for name in voices:write('voice_samples/'+name,pcm(24000,24000*7))
    with patch.dict(S.HASHES,hashes,clear=True):
        corpus=S.Corpus(root);enrolled=S.enrollment(corpus)
        assert len(enrolled)==3 and all(len(x)>=rate for x in enrolled)
        audio=corpus.audio('data/gold/audio/quiet.wav');assert not audio.flags.writeable
        assert len(corpus.audio('voice_samples/kokoro_bm_daniel.wav'))==7*rate
        rows=list(S.cases(corpus));assert len(rows)==45
        for row in rows:
            truth=row['truth'];assert row['sample_rate']==rate and row['audio'].ndim==1
            assert np.array_equal(row['audio'],truth.owner_reference+truth.other_reference)
            if truth.owner_present:
                assert truth.owner_complete and truth.expected_text=='FAKE '+truth.owner_id and truth.expected_intent=={'fake':truth.owner_id}
                span=truth.source_spans[0];assert span.source_start==round(.1*rate) and span.source_end==round(1.3*rate)
            else:assert truth.expected_text is None
        performance=S.performance_inputs(corpus)
        assert tuple(performance)==S.PERFORMANCE_SECONDS
        assert all(len(value)==round(seconds*rate) for seconds,value in performance.items())
        try:corpus._bytes('../outside.wav');raise AssertionError('unfrozen path accepted')
        except ValueError:pass
        changed=root/'data/gold/audio/quiet.wav';changed.write_bytes(changed.read_bytes()+b'changed')
        try:S.Corpus(root).audio('data/gold/audio/quiet.wav');raise AssertionError('changed source checksum accepted')
        except ValueError as error:assert 'checksum' in str(error)

# Audit existing read-only source loading without model imports or label output.
corpus=S.Corpus();before={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in S.HASHES}
assert before==S.HASHES
assert len(corpus.enrollment())==3
for voices in S.OTHERS.values():
    for name in voices:assert len(corpus.audio('voice_samples/'+name))>=6*rate
assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in before.items())
assert 'torch' not in sys.modules and 'faster_whisper' not in sys.modules and 'sounddevice' not in sys.modules
digest=hashlib.sha256(json.dumps(S.manifest(),sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert digest==S.FROZEN_MANIFEST_SHA256,'matrix changed after it was frozen'
print('SEPARATION CASES: frozen45 +4latency, disjoint enrolment/tuning/heldout, exact SNR/spans/no-repeat, hashes/read-only PCM/resampling, grading isolation passed; manifest',digest)
