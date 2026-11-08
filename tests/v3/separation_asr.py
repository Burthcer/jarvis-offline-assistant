"""Isolated current-Whisper comparison for the separate CPU separation lab.

No microphone, speaker, models download, account or production setting access.
Audio crosses only owned local pipes, as bounded little-endian mono float32.
"""
import base64,contextlib,json,math,os,queue,subprocess,sys,tempfile,threading,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
RATE=16000
MAX_SAMPLES=16*RATE
MAX_LINE=2*1024*1024
# Fixed for the whole lab, never selected by a case's expected answer.
LAB_CAPABILITIES=frozenset({'open','close','media','volume','clock','search','timer_set'})


class LabBlocked(Exception):
    def __init__(self,plan):self.plan=plan


def canonical_calls(calls):
    result=[]
    for call in calls:
        args=dict(call.args)
        if call.ability=='timer_set' and 'duration' in args:args['seconds']=args.pop('duration')
        result.append({'a':call.ability,**args})
    return json.loads(json.dumps(result,default=lambda value:value.isoformat() if hasattr(value,'isoformat') else str(value)))


def encode_audio(audio):
    import numpy as np
    a=np.asarray(audio)
    if a.ndim!=1 or a.dtype!=np.float32 or not 0<len(a)<=MAX_SAMPLES or not np.isfinite(a).all():
        raise ValueError('ASR needs finite mono float32 audio, up to sixteen seconds.')
    return base64.b64encode(a.astype('<f4',copy=False).tobytes()).decode('ascii')


def decode_audio(value):
    import numpy as np
    if not isinstance(value,str) or len(value)>4*((MAX_SAMPLES*4+2)//3):raise ValueError('Invalid audio frame.')
    try:raw=base64.b64decode(value,validate=True)
    except (ValueError,TypeError):raise ValueError('Invalid audio frame.') from None
    if not raw or len(raw)%4 or len(raw)>MAX_SAMPLES*4:raise ValueError('Invalid audio frame.')
    a=np.frombuffer(raw,dtype='<f4')
    if not np.isfinite(a).all():raise ValueError('Invalid audio frame.')
    return a


def frozen_hint():
    """Same no-usage/no-live-catalog hint for every baseline/separated case."""
    from jarvis3.engine.names import Names
    catalog=json.loads((ROOT/'data/gold/catalog.json').read_text(encoding='utf-8'))
    return Names(catalog,usage=lambda _:0).hint()


class ASRWorker:
    def __init__(self,gpu_env=None,*,interpret=False,request_timeout=30,ready_timeout=60,_command=None):
        import psutil
        self.process=None;self.identity=None;self.closed=False;self.reader=None
        self.messages=queue.Queue();self.lock=threading.Lock();self.serial=0
        self.request_timeout=float(request_timeout)
        self.interpret_enabled=bool(interpret)
        env=dict(os.environ)
        for key,value in (gpu_env or {}).items():
            if value is None:env.pop(key,None)
            else:env[key]=str(value)
        env.update(JARVIS_SILENT='1',HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
        command=_command or [str(Path(sys.base_prefix)/'python.exe'),'-u',str(Path(__file__).resolve()),'--worker',*(['--interpret'] if interpret else [])]
        try:
            self.process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:self.identity=(self.process.pid,psutil.Process(self.process.pid).create_time())
            except psutil.NoSuchProcess:raise RuntimeError('ASR helper exited before starting.') from None
            self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()
            ready=self._receive(float(ready_timeout))
            if not isinstance(ready,dict) or set(ready)!={'ready'} or ready['ready'] is not True:raise RuntimeError('ASR helper could not load the existing speech model.')
        except Exception:
            self.close(force=True)
            raise

    def _read(self):
        try:
            while True:
                raw=self.process.stdout.readline(MAX_LINE+1)
                if not raw:
                    self.messages.put(RuntimeError('ASR helper closed its pipe.'));return
                if len(raw)>MAX_LINE or not raw.endswith(b'\n'):
                    self.messages.put(RuntimeError('ASR helper returned an invalid frame.'));return
                try:message=json.loads(raw.decode('utf-8'))
                except (ValueError,UnicodeError):
                    self.messages.put(RuntimeError('ASR helper returned an invalid frame.'));return
                self.messages.put(message)
        except (OSError,ValueError):self.messages.put(RuntimeError('ASR helper pipe failed.'))

    def _receive(self,timeout):
        try:result=self.messages.get(timeout=max(0,timeout))
        except queue.Empty:raise TimeoutError('ASR helper exceeded its time bound.') from None
        if isinstance(result,Exception):raise result
        return result

    def _send(self,message,timeout):
        raw=(json.dumps(message,separators=(',',':'),ensure_ascii=True)+'\n').encode('ascii')
        if len(raw)>MAX_LINE:raise ValueError('ASR request is too large.')
        done=queue.Queue(maxsize=1)
        def write():
            try:self.process.stdin.write(raw);self.process.stdin.flush();done.put(None)
            except (OSError,ValueError) as error:done.put(error)
        writer=threading.Thread(target=write,daemon=True);writer.start()
        try:error=done.get(timeout=max(0,timeout))
        except queue.Empty:raise TimeoutError('ASR helper stopped accepting input.') from None
        if error:raise RuntimeError('ASR helper input pipe failed.') from None

    def transcribe(self,audio):
        encoded=encode_audio(audio)
        with self.lock:
            if self.closed:raise RuntimeError('ASR helper is closed.')
            self.serial+=1;deadline=time.monotonic()+self.request_timeout
            try:
                self._send({'id':self.serial,'rate':RATE,'audio':encoded},deadline-time.monotonic())
                result=self._receive(deadline-time.monotonic())
                if (not isinstance(result,dict) or set(result)!={'id','text','ms'} or type(result['id']) is not int or result['id']!=self.serial
                        or not isinstance(result['text'],str) or len(result['text'])>4000
                        or type(result['ms']) not in (int,float) or not math.isfinite(result['ms']) or result['ms']<0):
                    raise RuntimeError('ASR helper returned an invalid result.')
                return {'text':result['text'],'ms':result['ms']}
            except Exception:
                self.close(force=True)
                raise

    def _owned(self):
        import psutil
        if not self.identity:return False
        try:return psutil.Process(self.identity[0]).create_time()==self.identity[1]
        except (psutil.NoSuchProcess,psutil.AccessDenied):return False

    def interpret(self,text):
        if not self.interpret_enabled:raise RuntimeError('Interpretation was not enabled for this helper.')
        if not isinstance(text,str) or len(text)>4000 or '\0' in text:raise ValueError('Invalid transcription text.')
        with self.lock:
            if self.closed:raise RuntimeError('ASR helper is closed.')
            self.serial+=1;deadline=time.monotonic()+self.request_timeout
            try:
                self._send({'id':self.serial,'interpret':True,'text':text},deadline-time.monotonic())
                result=self._receive(deadline-time.monotonic())
                if (not isinstance(result,dict) or set(result)!={'id','calls','ok','addressed','ms'}
                        or type(result['id']) is not int or result['id']!=self.serial
                        or type(result['ok']) is not bool or type(result['addressed']) is not bool
                        or type(result['ms']) not in (int,float) or not math.isfinite(result['ms']) or result['ms']<0
                        or not isinstance(result['calls'],list) or len(result['calls'])>64
                        or any(not isinstance(c,dict) or not isinstance(c.get('a'),str) or len(c['a'])>80 for c in result['calls'])
                        or len(json.dumps(result['calls']))>24000):
                    raise RuntimeError('ASR helper returned an invalid interpretation.')
                return {k:result[k] for k in ('calls','ok','addressed','ms')}
            except Exception:
                self.close(force=True)
                raise

    def close(self,force=False):
        if self.closed:return
        self.closed=True
        child=self.process
        if child is None:return
        if child.poll() is None and not force:
            try:self._send({'stop':True},.5);child.wait(timeout=2)
            except (OSError,ValueError,RuntimeError,TimeoutError,subprocess.TimeoutExpired):pass
        if child.poll() is None and self._owned():
            child.terminate()
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                if self._owned():child.kill()
        try:child.wait(timeout=3)
        except subprocess.TimeoutExpired:raise RuntimeError('Owned ASR helper could not be reaped.') from None
        for stream in (child.stdin,child.stdout):
            if stream:
                try:stream.close()
                except OSError:pass
        if self.reader:self.reader.join(1)

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def interpret_request(text,ai,hint):
    """Run only allowlisted effects on a fresh fake PC; receives no case truth."""
    from datetime import datetime
    from jarvis3.engine.app import App
    from jarvis3.engine.ears import Ears
    from jarvis3.engine.memory import Memory
    from jarvis3.engine.osapi import Fake
    from jarvis3.engine.names import Names
    from jarvis3.legacy.store import Store
    class FrozenFake(Fake):
        def catalog(self):return json.loads((ROOT/'data/gold/catalog.json').read_text(encoding='utf-8'))
    class LabApp(App):
        def _run(self,plan,*args,**kwargs):
            # Check the entire proposed compound before the first ability,
            # ledger hook or account/filesystem helper can be invoked.
            if any(c.ability not in LAB_CAPABILITIES for c in plan.calls):raise LabBlocked(plan)
            return super()._run(plan,*args,**kwargs)
    start=time.perf_counter();ear=Ears(None,None,None,lambda _:None,hint=lambda:hint)
    store=Store(':memory:');memory=Memory(':memory:')
    try:
        out=ear.decide(text)
        if not out or not out[0]:return {'calls':[],'ok':False,'addressed':bool(out),'ms':round((time.perf_counter()-start)*1000,3)}
        app=LabApp(FrozenFake(),store,ai,memory=memory,clock=lambda:datetime(2026,10,31,10),natural=False)
        # Ignore all usage/log preference data in this controlled comparison.
        app.names=Names(app.catalog,usage=lambda _:0,memory=memory)
        app.set_mic=lambda _:True
        try:
            reply=app.handle(out[0],trigger=out[1])
            calls=canonical_calls(c for c,_ in reply.results);ok=bool(reply.ok)
        except LabBlocked as blocked:
            # Preserve attempted wrong intents for grading without running them.
            calls=canonical_calls(blocked.plan.calls);ok=False
        return {'calls':calls,'ok':ok,'addressed':True,'ms':round((time.perf_counter()-start)*1000,3)}
    finally:ear.shutdown();store.db.close();memory.db.close()


def worker(interpret=False):
    sys.path.insert(0,str(ROOT))
    # Use installed dependencies only; never install/modify the other tool.
    extra=ROOT.parent/'Wisperno-pro/.venv/Lib/site-packages'
    if extra.is_dir():sys.path.append(str(extra))
    os.environ.update(JARVIS_SILENT='1',HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    stt=None;ai=None
    home=tempfile.TemporaryDirectory(prefix='v3-asr-helper-')
    os.environ['JARVIS_V3_HOME']=home.name
    def emit(message):
        sys.stdout.write(json.dumps(message,ensure_ascii=True,separators=(',',':'))+'\n');sys.stdout.flush()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            import numpy as np
            from jarvis3.engine.ears import Transcriber
            from jarvis3.paths import prepare
            prepare()
            hint=frozen_hint();stt=Transcriber();stt.load()
            if stt.device!='GPU':raise RuntimeError('Existing GPU speech model was not available.')
        emit({'ready':True})
        while True:
            line=sys.stdin.buffer.readline(MAX_LINE+1)
            if not line:return
            if len(line)>MAX_LINE or not line.endswith(b'\n'):raise ValueError('Invalid request frame.')
            item=json.loads(line)
            if item=={'stop':True}:return
            if interpret and isinstance(item,dict) and set(item)=={'id','interpret','text'} and item['interpret'] is True:
                if type(item['id']) is not int or item['id']<1 or not isinstance(item['text'],str) or len(item['text'])>4000 or '\0' in item['text']:raise ValueError('Invalid interpretation frame.')
                with contextlib.redirect_stdout(sys.stderr):
                    if ai is None:
                        from jarvis3.engine.ai import AI
                        ai=AI()
                    result=interpret_request(item['text'],ai,hint)
                emit({'id':item['id'],**result});continue
            if not isinstance(item,dict) or set(item)!={'id','rate','audio'} or type(item['id']) is not int or item['id']<1 or item['rate']!=RATE:raise ValueError('Invalid request frame.')
            audio=decode_audio(item['audio'])
            # The unchanged Transcriber accepts int16 microphone units.
            pcm=np.clip(np.rint(audio*32768),-32768,32767).astype(np.int16)
            start=time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr):text=stt(pcm,hint)
            emit({'id':item['id'],'text':text,'ms':round((time.perf_counter()-start)*1000,3)})
    except Exception:
        emit({'error':'ASR helper unavailable or request invalid.'})
    finally:
        if ai is not None:
            with contextlib.redirect_stdout(sys.stderr):ai.unload()
        if stt is not None:
            with contextlib.redirect_stdout(sys.stderr):stt.unload()
        home.cleanup()


if __name__=='__main__' and sys.argv[1:] in (['--worker'],['--worker','--interpret']):worker(interpret='--interpret' in sys.argv)
