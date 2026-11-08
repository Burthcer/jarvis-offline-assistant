"""Frozen offline CPU-separation cases, not a production feature or voice profile.

Inference receives Signal(audio, rate) ONLY. Truth/reference audio/command labels
are returned separately for grading and must never select a separator stream.
No source audio, mixtures or enrolment profile are written/exported here.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,io,json,math,wave
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
RATE=16000
VERSION='quiet-owner-synthetic-interference-2026-11-07-v1'
FROZEN_MANIFEST_SHA256='a89855eabca9273cce5efb5449457281612b09dd2057b515b9b046b8be0774bf'
ENROLLMENT=('n01','n02','n03')  # same existing, approved voice-check enrolment
TUNING=('n04','n06','n08','n10')
HELDOUT=('n05','n07','n09','n11')
OTHERS={'tuning':('kokoro_bm_daniel.wav','kokoro_bm_george.wav'),
        'heldout':('kokoro_bm_fable.wav','kokoro_bm_lewis.wav')}
RATIOS=(-6,0,6)  # owner-to-other RMS dB, before common peak scaling
OFFSETS=(-0.8,0.0,0.8,0.0)  # other onset relative to owner; frozen by owner index
PERFORMANCE_SECONDS=(0.8,1.6,3.0,6.0)
VOICE_THRESHOLD=0.25  # existing voice-check example, not tuned on these cases
VOICE_MARGIN=0.05  # experimental abstention margin, not authentication
HASHES={
    'data/gold/audio/session.json':'1482841de3181d1acb0761e75af8ddc67044cc304e6fe5d8c88ae26fcd5cb659',
    'tests/v2/prompts.json':'c20fdd98ddf44dfd901a4190ac81a1027f4f86d194cac2adfd8bdd47da2a148e',
    'data/gold/audio/quiet.wav':'9ecea1e4f7e53598e47c2a76c9afec62be56509cb51470888b93fbfc9d35d0c8',
    'voice_samples/kokoro_bm_daniel.wav':'79fe565ab40c4ba6b6face811b7293080730c4e8caa1f576f6ec01409e4351b6',
    'voice_samples/kokoro_bm_george.wav':'3eb430e0ff57fc79783a6fe9cb2d73e99e260f43a10930b5adbb23a195ad3d29',
    'voice_samples/kokoro_bm_fable.wav':'269424c41ab5d49cea118376c9c6fae0063e851ed3eb3c25a0d9ca5e128ff0ac',
    'voice_samples/kokoro_bm_lewis.wav':'65eef41d8cd9fee8c7167e62242c3d7bc5407114cb5f453315b3709730396bb5',
}
LIMITATIONS=(
    'All other-speaker sources are synthetic TTS; no real other-human/phone-room recording is available.',
    'Same owner/recording session throughout; speaker- and room-population generalisation is unproven.',
    'Recordings were already used in earlier development; heldout here means disjoint from this trial tuning/enrolment, not globally unseen.',
    'No tired-speech, live-room, microphone or phone loudspeaker/acoustic replay test.',
    'Other TTS voice aliases are excluded; four canonical voices do not establish a population false-accept rate.',
    'Non-overlap and overlap mixtures retain whole owner commands; latency-only crops never count as command acceptance.',
)

@dataclass(frozen=True)
class Case:
    id:str
    split:str
    kind:str
    owner_id:str|None=None
    other:str|None=None
    ratio_db:int=0
    offset:float=0.0
    owner_first:bool=True
    seconds:float|None=None

@dataclass(frozen=True)
class Signal:
    audio:np.ndarray
    rate:int=RATE

@dataclass(frozen=True)
class Span:
    """All offsets are samples at RATE, after source resampling if needed."""
    source:str
    source_start:int
    source_end:int
    input_start:int
    input_end:int

@dataclass(frozen=True)
class Truth:
    owner_reference:np.ndarray
    other_reference:np.ndarray
    owner_present:bool
    owner_complete:bool
    owner_id:str|None
    source_spans:tuple[Span,...]
    expected_text:str|None=None
    expected_intent:object=None
    command_grade:bool=True

def primary_cases():
    result=[]
    for split,owners in (('tuning',TUNING),('heldout',HELDOUT)):
        for index,owner in enumerate(owners):
            other=OTHERS[split][index%2];prefix=f'{split}-{owner}'
            result.append(Case(prefix+'-clean',split,'clean',owner))
            for ratio in RATIOS:
                result.append(Case(prefix+f'-overlap-{ratio:+d}',split,'overlap',owner,other,ratio,OFFSETS[index]))
            result.append(Case(prefix+'-nonoverlap',split,'nonoverlap',owner,other,owner_first=index%2==0))
        for other in OTHERS[split]:result.append(Case(split+'-other-'+other[:-4],split,'other',other=other,seconds=4.0))
    result.append(Case('control-silence-3s','control','silence',seconds=3.0))
    return tuple(result)

def performance_cases():
    return tuple(Case(f'latency-{seconds:g}s','latency','latency',TUNING[0],OTHERS['tuning'][0],seconds=seconds) for seconds in PERFORMANCE_SECONDS)

def frozen_manifest():
    return {'version':VERSION,'rate':RATE,'enrolment':ENROLLMENT,'tuning':TUNING,'heldout':HELDOUT,
            'other_voices':dict(OTHERS),'source_sha256':dict(HASHES),'cases':[asdict(c) for c in primary_cases()],
            'latency_only':[asdict(c) for c in performance_cases()],
            'selection_policy':{'id':'voice-0.25-margin-0.05-abstain-v1','threshold':VOICE_THRESHOLD,'runner_up_margin':VOICE_MARGIN,
                                'oracle_stream_selection':False},'limitations':LIMITATIONS}

def _normal(audio):
    audio=np.asarray(audio,dtype=np.float32)
    if audio.ndim!=1 or not len(audio) or not np.isfinite(audio).all():raise ValueError('Expected finite mono source audio.')
    level=float(np.sqrt(np.mean(audio.astype(np.float64)**2)))
    if level<1e-7:raise ValueError('Speech source is empty or silent.')
    return audio/level

def mix(case,owner=None,other=None,owner_source='',owner_start=0):
    """Pure deterministic mixing; no repetition/time-stretching of any source."""
    if case.kind not in ('clean','overlap','nonoverlap','other','silence','latency'):raise ValueError('Unknown frozen case kind.')
    own=_normal(owner) if case.owner_id is not None else np.zeros(0,np.float32)
    foreign=_normal(other) if case.other is not None else np.zeros(0,np.float32)
    lead=round(.25*RATE);tail=lead;own_at=lead;other_at=lead
    if case.kind=='overlap':
        foreign=_normal(foreign[:min(len(foreign),len(own))])
        own_at+=round(max(0,-case.offset)*RATE);other_at+=round(max(0,case.offset)*RATE)
        foreign=foreign*10**(-case.ratio_db/20)
    elif case.kind=='nonoverlap':
        foreign=_normal(foreign[:min(len(foreign),round(2.4*RATE),len(own))])
        if case.owner_first:other_at=own_at+len(own)+round(.4*RATE)
        else:own_at=other_at+len(foreign)+round(.4*RATE)
    elif case.kind=='other':foreign=foreign[:round(case.seconds*RATE)]
    elif case.kind=='latency':own_at=other_at=0;tail=0
    size=round(case.seconds*RATE) if case.kind in ('latency','silence') else max(own_at+len(own) if len(own) else 0,other_at+len(foreign) if len(foreign) else 0)+tail
    own_count=max(0,min(len(own),size-own_at));other_count=max(0,min(len(foreign),size-other_at))
    own_ref=np.zeros(size,np.float32);other_ref=np.zeros(size,np.float32);spans=[]
    if own_count:
        own_ref[own_at:own_at+own_count]=own[:own_count]
        spans.append(Span(owner_source or 'quiet:'+case.owner_id,owner_start,owner_start+own_count,own_at,own_at+own_count))
    if other_count:
        other_ref[other_at:other_at+other_count]=foreign[:other_count]
        spans.append(Span('voice_samples/'+case.other,0,other_count,other_at,other_at+other_count))
    audio=own_ref+other_ref;peak=float(np.max(np.abs(audio))) if len(audio) else 0
    gain=.6/peak if peak else 1.0
    own_ref*=gain;other_ref*=gain;audio=own_ref+other_ref
    truth=Truth(own_ref,other_ref,bool(own_count),own_count==len(own) and bool(own_count),case.owner_id,tuple(spans),command_grade=case.kind!='latency')
    return Signal(audio),truth

class Corpus:
    """Pinned, read-only source loading. Labels are grader-only, never Signal."""
    def __init__(self,root=ROOT):
        self.root=Path(root);self._audio={};self._labels=None
        session=json.loads(self._bytes('data/gold/audio/session.json'))['sections']['quiet']['takes']
        self.takes={row['id']:row for row in session}
        for key in ENROLLMENT+TUNING+HELDOUT:
            row=self.takes[key]
            if not 0<=row['start']<row['end']:raise ValueError('Invalid frozen source span.')

    def _bytes(self,relative):
        if relative not in HASHES:raise ValueError('Source is outside the frozen corpus.')
        data=(self.root/relative).read_bytes()
        if hashlib.sha256(data).hexdigest()!=HASHES[relative]:raise ValueError('Frozen source checksum changed: '+relative)
        return data

    def audio(self,relative):
        if relative not in self._audio:
            with wave.open(io.BytesIO(self._bytes(relative)),'rb') as source:
                if source.getsampwidth()!=2 or source.getnchannels()!=1 or source.getcomptype()!='NONE':raise ValueError('Expected PCM16 mono source.')
                rate=source.getframerate();frames=source.getnframes()
                audio=np.frombuffer(source.readframes(frames),dtype='<i2').astype(np.float32)/32768
            if rate!=RATE:
                from scipy.signal import resample_poly
                divisor=math.gcd(rate,RATE);audio=resample_poly(audio,RATE//divisor,rate//divisor).astype(np.float32)
                expected=round(frames*RATE/rate);audio=np.pad(audio[:expected],(0,max(0,expected-len(audio))))
            audio.flags.writeable=False;self._audio[relative]=audio
        return self._audio[relative]

    def owner(self,identifier):
        if identifier not in ENROLLMENT+TUNING+HELDOUT:raise ValueError('Owner take is outside the frozen split.')
        take=self.takes[identifier];audio=self.audio('data/gold/audio/quiet.wav')
        start,end=round(take['start']*RATE),round(take['end']*RATE)
        if not 0<=start<end<=len(audio):raise ValueError('Owner take extends beyond its source.')
        return audio[start:end]

    def enrolment(self):return tuple(self.owner(identifier).copy() for identifier in ENROLLMENT)
    def enrollment(self):return self.enrolment()

    def grading_labels(self,identifier):
        """For scoring only; do not pass this result into stream selection."""
        if self._labels is None:
            rows=json.loads(self._bytes('tests/v2/prompts.json'))['named']
            self._labels={row['id']:(row['say'],row['expect']) for row in rows}
        return self._labels[identifier]

    def materialize(self,case):
        if case not in primary_cases()+performance_cases():raise ValueError('Case is outside the frozen matrix.')
        owner=self.owner(case.owner_id) if case.owner_id else None
        other=self.audio('voice_samples/'+case.other) if case.other else None
        start=round(self.takes[case.owner_id]['start']*RATE) if case.owner_id else 0
        signal,truth=mix(case,owner,other,'data/gold/audio/quiet.wav',start)
        if case.owner_id and truth.command_grade:
            text,intent=self.grading_labels(case.owner_id)
            truth=Truth(**{**truth.__dict__,'expected_text':text,'expected_intent':intent})
        return signal,truth

def enrollment(corpus=None):return (corpus or Corpus()).enrolment()
def manifest():return frozen_manifest()
def cases(corpus=None):
    corpus=corpus or Corpus()
    for case in primary_cases():
        signal,truth=corpus.materialize(case)
        yield {'id':case.id,'split':case.split,'kind':case.kind,'audio':signal.audio,'sample_rate':signal.rate,'truth':truth}
def performance_inputs(corpus=None):
    corpus=corpus or Corpus()
    return {case.seconds:corpus.materialize(case)[0].audio for case in performance_cases()}
