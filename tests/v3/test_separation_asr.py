"""Owned fake-worker IPC only; never loads Whisper, CUDA, audio or live devices."""
import os,sys,time,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
import psutil
from separation_asr import ASRWorker,MAX_SAMPLES,ROOT,encode_audio,decode_audio
os.environ['JARVIS_SILENT']='1'

CODE=r'''
import base64,json,os,struct,sys,time
mode=sys.argv[1]
if mode=='readyhang':time.sleep(30)
if mode=='badready':print('{"ready":1}',flush=True);time.sleep(30)
if mode=='giantready':print('x'*2100000,flush=True);time.sleep(30)
print('{"ready":true}',flush=True)
for line in sys.stdin.buffer:
 item=json.loads(line)
 if item=={'stop':True}:sys.exit(0)
 if mode=='hang':time.sleep(30)
 if mode=='invalid':print('{"id":1,"text":{},"ms":0}',flush=True);continue
 if mode=='badid':print('{"id":true,"text":"bad","ms":0}',flush=True);continue
 if mode=='crash':sys.exit(3)
 if item.get('interpret') is True:
  if mode=='badinterpret':print(json.dumps({'id':item['id'],'calls':{},'ok':True,'addressed':True,'ms':2}),flush=True);continue
  print(json.dumps({'id':item['id'],'calls':[{'a':'timer_set','seconds':120}],'ok':True,'addressed':True,'ms':2}),flush=True);continue
 raw=base64.b64decode(item['audio'],validate=True)
 values=struct.unpack('<'+'f'*(len(raw)//4),raw)
 text=f"{len(values)}:{values[0]}:{item['rate']}:{os.environ.get('CUDA_VISIBLE_DEVICES','absent')}"
 print(json.dumps({'id':item['id'],'text':text,'ms':1.25}),flush=True)
'''
def command(mode):return [sys.executable,'-u','-c',CODE,mode]
def gone(identity):
 end=time.monotonic()+1
 while True:
  try:
   if psutil.Process(identity[0]).create_time()!=identity[1]:return True
  except psutil.NoSuchProcess:return True
  if time.monotonic()>=end:return False
  time.sleep(.01)

a=np.array([.25,-.5,1,0],dtype=np.float32)
assert np.array_equal(decode_audio(encode_audio(a)),a)
for bad in (np.array([],np.float32),np.zeros((2,3),np.float32),np.array([float('nan')],np.float32),np.array([float('inf')],np.float32),np.zeros(MAX_SAMPLES+1,np.float32),np.ones(2,np.float64)):
 try:encode_audio(bad)
 except ValueError:pass
 else:raise AssertionError('Invalid input accepted')
for bad in ('not base64!', 'AAAA', '',123):
 try:decode_audio(bad)
 except ValueError:pass
 else:raise AssertionError('Invalid wire audio accepted')

with ASRWorker({'CUDA_VISIBLE_DEVICES':'original-test-gpu'},_command=command('echo')) as client:
 identity=client.identity
 assert client.transcribe(a)=={'text':'4:0.25:16000:original-test-gpu','ms':1.25}
 assert client.transcribe(np.zeros(MAX_SAMPLES,np.float32))['text'].startswith(str(MAX_SAMPLES)+':')
 try:client.transcribe(np.array([float('nan')],np.float32))
 except ValueError:pass
 else:raise AssertionError('Invalid client audio sent')
 assert client.transcribe(a)['text'].startswith('4:')
assert client.process.returncode==0 and gone(identity),'normal close did not stop/reap the owned helper'
client.close()
try:client.transcribe(a)
except RuntimeError:pass
else:raise AssertionError('Closed helper accepted request')

with ASRWorker(interpret=True,_command=command('echo')) as client:
 identity=client.identity
 assert client.interpret('Jarvis set a timer for two minutes')=={'calls':[{'a':'timer_set','seconds':120}],'ok':True,'addressed':True,'ms':2}
 assert client.transcribe(a)['text'].startswith('4:'),'optional interpretation broke normal ASR framing'
 for bad in (123,'x'*4001,'bad\0text'):
  try:client.interpret(bad)
  except ValueError:pass
  else:raise AssertionError('Invalid interpretation input accepted')
assert gone(identity)
with ASRWorker(_command=command('echo')) as client:
 identity=client.identity
 try:client.interpret('Jarvis open notepad')
 except RuntimeError:pass
 else:raise AssertionError('Interpretation enabled implicitly')
 assert client.transcribe(a)['text'].startswith('4:')
assert gone(identity)
client=ASRWorker(interpret=True,_command=command('badinterpret'));identity=client.identity
try:client.interpret('Jarvis open notepad')
except RuntimeError:pass
else:raise AssertionError('Malformed interpretation accepted')
assert client.closed and gone(identity)

before=os.environ.get('CUDA_VISIBLE_DEVICES')
os.environ['CUDA_VISIBLE_DEVICES']='-1'
try:
 with ASRWorker({'CUDA_VISIBLE_DEVICES':None},_command=command('echo')) as client:
  identity=client.identity
  assert client.transcribe(a)['text'].endswith(':absent'),'CPU parent visibility leaked into explicit original GPU env'
 assert gone(identity)
finally:
 if before is None:os.environ.pop('CUDA_VISIBLE_DEVICES',None)
 else:os.environ['CUDA_VISIBLE_DEVICES']=before

for mode in ('hang','invalid','badid','crash'):
 client=ASRWorker(_command=command(mode),request_timeout=.15)
 identity=client.identity;start=time.monotonic()
 try:client.transcribe(a)
 except (RuntimeError,TimeoutError):pass
 else:raise AssertionError('Bad worker output accepted: '+mode)
 assert time.monotonic()-start<4 and client.closed and gone(identity),(mode,'owned helper survived failure')

# The identity of a helper failing during __init__ is captured externally by
# a tracking Popen wrapper, not guessed/enumerated from other Python processes.
import separation_asr
original=separation_asr.subprocess.Popen
for mode in ('readyhang','badready','giantready'):
 spawned=[]
 def start(*args,**kwargs):
  child=original(*args,**kwargs);spawned.append((child.pid,psutil.Process(child.pid).create_time()));return child
 separation_asr.subprocess.Popen=start
 try:
  try:ASRWorker(_command=command(mode),ready_timeout=.15)
  except (RuntimeError,TimeoutError):pass
  else:raise AssertionError('Bad worker startup accepted')
 finally:separation_asr.subprocess.Popen=original
 assert len(spawned)==1 and gone(spawned[0]),'startup failure left owned helper running'

# Exercise canonicalisation with scripted output, never an actual AI model.
sys.path.insert(0,str(ROOT))
with tempfile.TemporaryDirectory(prefix='v3-asr-fake-nlu-') as home:
 previous=os.environ.get('JARVIS_V3_HOME');os.environ['JARVIS_V3_HOME']=home
 try:
  from jarvis3.paths import prepare
  prepare()
  from separation_asr import frozen_hint,interpret_request
  class Scripted:
   def __init__(self,line):self.line=line;self.calls=0
   def complete(self,*args,**kwargs):self.calls+=1;return self.line
  hint=frozen_hint();fake=Scripted('timer_set(duration="two minutes")')
  answer=interpret_request('Jarvis set a timer for two minutes',fake,hint)
  assert answer['addressed'] and answer['ok'] and answer['calls']==[{'a':'timer_set','seconds':120}]
  fake=Scripted('open(target="notepad")')
  answer=interpret_request('my friend said open notepad',fake,hint)
  assert not answer['addressed'] and not answer['calls'] and fake.calls==0
  answer=interpret_request('Jarvis remind me to study tomorrow',Scripted('reminder_add(text="study", when="tomorrow")'),hint)
  assert not answer['ok'] and answer['calls'][0]['a']=='reminder_add' and answer['calls'][0]['when'].startswith('2026-11-01')

  # A Fake OS is not enough: some registered abilities write outside OSAPI.
  # The lab checks every whole plan before invoking even its first function.
  from unittest.mock import patch,Mock
  from jarvis3.engine.registry import ABILITIES,Text,ability,Result
  from separation_asr import LAB_CAPABILITIES
  assert LAB_CAPABILITIES==frozenset({'open','close','media','volume','clock','search','timer_set'})
  @ability('lab_backup','back up lab files',required={'text':Text()})
  def lab_backup(args,ctx):raise AssertionError('A backup function must never run in this lab')
  before={str(p.relative_to(home)):p.read_bytes() for p in Path(home).rglob('*') if p.is_file()}
  try:
   for name,text,line in (
    ('lab_backup','Jarvis carry out the lab request','lab_backup(text="lab archive")'),
    ('wish_add','Jarvis I wish you could perform lab work','wish_add(text="perform lab work")'),
    ('event_track','Jarvis carry out the lab request','event_track(text="lab meetup on friday")'),
    ('google_read','Jarvis check my gmail','google_read(service="gmail")'),
    ('note_save','Jarvis carry out the lab request','note_save(text="lab note")'),
    ('skill_teach','Jarvis learn a skill called lab that open notepad','skill_teach(name="lab", steps="open notepad")'),
   ):
    forbidden=Mock(side_effect=AssertionError('Forbidden capability ran'))
    with patch.object(ABILITIES[name],'fn',forbidden):
     answer=interpret_request(text,Scripted(line),hint)
    assert not answer['ok'] and answer['addressed'] and answer['calls'][0]['a']==name,(name,answer)
    forbidden.assert_not_called()
   timer=Mock(side_effect=AssertionError('Part of a blocked compound ran'))
   note=Mock(side_effect=AssertionError('Forbidden capability ran'))
   with patch.object(ABILITIES['timer_set'],'fn',timer),patch.object(ABILITIES['note_save'],'fn',note):
    answer=interpret_request('Jarvis start a timer for two minutes and keep a note',Scripted('timer_set(duration="two minutes")\nnote_save(text="lab note")'),hint)
   assert not answer['ok'] and [c['a'] for c in answer['calls']]==['timer_set','note_save']
   timer.assert_not_called();note.assert_not_called()
  finally:ABILITIES.pop('lab_backup',None)
  after={str(p.relative_to(home)):p.read_bytes() for p in Path(home).rglob('*') if p.is_file()}
  assert before==after,'lab interpretation wrote files'
 finally:
  if previous is None:os.environ.pop('JARVIS_V3_HOME',None)
  else:os.environ['JARVIS_V3_HOME']=previous
print('SEPARATION ASR IPC: float32 bounds, max frame, optional interpretation framing/guards, GPU env separation, malformed/timeout cleanup, exact owned helper reaping passed; no real model loaded')
