"""Native API shim and timeout path. Never touches the user's clipboard."""
import os,sys,ctypes,json,subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
os.environ['JARVIS_SILENT']='1';sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.clipboard_capture import native_read,read
class Fn:
    def __init__(self,fn):self.fn=fn
    def __call__(self,*a):return self.fn(*a)
def shim(text='literal 🙂 text',exclude=False,history=None,available=True,raw=None,change=False,busy=False):
    buffers={13:ctypes.create_string_buffer(raw if raw is not None else (text+'\0').encode('utf-16-le'))}
    if history is not None:buffers[102]=ctypes.create_string_buffer(int(history).to_bytes(4,'little'))
    calls=[];sequence=[4,5] if change else [4,4]
    def fetch(fmt):calls.append(fmt);return fmt if fmt in buffers else None
    u=NS(OpenClipboard=Fn(lambda owner:not busy),CloseClipboard=Fn(lambda:calls.append('close')),
         GetClipboardData=Fn(fetch),RegisterClipboardFormatW=Fn(lambda name:101 if name.startswith('Exclude') else 102),
         IsClipboardFormatAvailable=Fn(lambda fmt:exclude if fmt==101 else history is not None if fmt==102 else available),
         GetClipboardSequenceNumber=Fn(lambda:sequence.pop(0)))
    # create_string_buffer adds a byte; report only the intended payload's length.
    sizes={key:len(bytes(buffer))-1 for key,buffer in buffers.items()}
    k=NS(GlobalSize=Fn(lambda h:sizes[h]),GlobalLock=Fn(lambda h:ctypes.addressof(buffers[h])),GlobalUnlock=Fn(lambda h:True))
    return u,k,calls
u,k,calls=shim();assert native_read(u,k)=={'text':'literal 🙂 text','sequence':4} and calls==[13,'close']
for text in ('🙂'*2000,'x'*2000):
    raw=(text+'\0').encode('utf-16-le')
    raw+=b'\0'*((-len(raw))%4096)  # Windows may round the allocation up.
    u,k,calls=shim(raw=raw)
    assert native_read(u,k)['text']==text,'valid Unicode/padded allocation was rejected'
for options in ({'exclude':True},{'history':0},{'available':False},{'raw':b'a\0b\0'},{'text':'x'*2001},{'change':True}):
    u,k,calls=shim(**options)
    try:native_read(u,k);raise AssertionError(options)
    except ValueError:pass
    assert calls[-1]=='close',options
    if options.get('exclude') or options.get('history')==0 or options.get('available') is False:assert 13 not in calls,'private/nontext CF_UNICODETEXT fetched'
u,k,calls=shim(history=1);assert native_read(u,k)['text']=='literal 🙂 text'
with patch('jarvis3.clipboard_capture.subprocess.run',side_effect=subprocess.TimeoutExpired('owned helper',1.5)):
    try:read();raise AssertionError('timeout accepted')
    except ValueError:pass
with patch('jarvis3.clipboard_capture.subprocess.run',return_value=NS(stdout=json.dumps({'ok':True,'text':'short literal text','sequence':5}))):
    assert read()=={'text':'short literal text','sequence':5}
original_run=subprocess.run;original_popen=subprocess.Popen;children=[]
def own_process(*a,**k):
    p=original_popen(*a,**k);children.append(p);return p
def sleeping_fixture(*a,**k):return original_run([sys.executable,'-c','import time;time.sleep(30)'],**k)
with patch('jarvis3.clipboard_capture.subprocess.run',side_effect=sleeping_fixture),patch('subprocess.Popen',side_effect=own_process):
    try:read();raise AssertionError('hung fixture accepted')
    except ValueError:pass
assert len(children)==1 and children[0].poll() is not None,'timed-out owned helper was not killed/reaped'
print('CLIPBOARD CAPTURE: bounded UTF16/emoji/terminator/size, privacy flags before text, lock cleanup/change detection and isolated timeout checks passed')
