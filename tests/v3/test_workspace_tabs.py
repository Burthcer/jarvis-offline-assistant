"""Injected adapters only: never touch a browser or enumerate user windows."""
import os,sys
from pathlib import Path
from contextlib import contextmanager
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.workspace_tabs import WorkspaceTabs,_SameWindow

class UnsafeFocus:
 def _front(self,hwnd):raise AssertionError('Workspace called a global focus/key recovery')
guard=_SameWindow(UnsafeFocus(),foreground=lambda:123)
assert guard._front(123) and not guard._front(456)

class Tabs:
    def __init__(self):
        self.rows=[{'id':(1,), 'title':'Project A','selected':True},{'id':(2,),'title':'Project B','selected':False}]
        self.urls={(1,):'https://example.com/a',(2,):'https://example.com/b'}
        self.log=[];self.window=(10,20,30.);self.cancel=False;self.after_read=None
    def list_tabs(self):return [dict(r) for r in self.rows]
    def select(self,ident):
        self.log.append(('select',ident))
        for row in self.rows:row['selected']=row['id']==ident
        return True
    def read(self):
        value=self.urls[next(r['id'] for r in self.rows if r['selected'])]
        if self.after_read:self.after_read()
        return value

t=Tabs()
@contextmanager
def session(browser):yield t
receipts=WorkspaceTabs(session=session,identity=lambda _:t.window,read=lambda _:t.read(),cancelled=lambda:t.cancel)
a,b='https://example.com/a','https://example.com/b'
assert not receipts.present('edge',a) and not t.log,'unknown tab was selected'
assert not receipts.remember('edge',b),'mismatched URL was recorded'
assert receipts.remember('edge',a)
t.select((2,));assert receipts.remember('edge',b);t.log.clear()
assert receipts.present('edge',a) and t.log==[('select',(1,))]
assert receipts.present('edge',b) and t.log[-1]==('select',(2,))
# Same tab identity can navigate: it cannot retain URL authorisation.
t.urls[(1,)]='https://example.com/changed'
assert not receipts.present('edge',a) and ('edge',a) not in receipts.receipts
t.urls[(1,)]=a;t.select((1,));assert receipts.remember('edge',a)
t.window=(10,20,31.);t.log.clear()
assert not receipts.present('edge',a) and not t.log,'reused HWND/process identity selected a tab'
t.window=(10,20,30.);assert receipts.remember('edge',a)
t.rows[0]['title']='Sign in';t.select((2,));t.log.clear()
assert not receipts.present('edge',a) and not t.log,'protected target selected'
t.rows[0]['title']='Project A';t.select((1,));assert receipts.remember('edge',a)
t.cancel=True;t.log.clear()
assert not receipts.present('edge',a) and not t.log
t.cancel=False
# A protected current tab cannot be used to focus another receipt either.
t.rows[1]['title']='Account password';t.select((2,));t.log.clear()
assert not receipts.present('edge',a) and not t.log
t.rows[1]['title']='Project B';t.select((1,))
# Focus/page changes while a URL is read invalidate the receipt.
t.after_read=lambda:setattr(t,'window',(11,21,31.))
assert not receipts.remember('edge',a)
t.after_read=None;t.window=(10,20,30.)
def navigate():t.urls[(1,)]='https://example.com/changed'
t.after_read=navigate
assert not receipts.remember('edge',a),'same-ID navigation during read was recorded'
t.after_read=None;t.urls[(1,)]=a
assert not receipts.remember('edge','https://example.com/a?token=secret')
# A same-window tab switch during the final URL read must not record the old ID.
t.select((1,));reads=[0]
def late_switch():
 reads[0]+=1
 if reads[0]==2:t.select((2,))
t.after_read=late_switch
assert not receipts.remember('edge',a),'final URL read raced a different selected tab'
t.after_read=None
print('WORKSPACE TAB RECEIPTS: exact tab/window/process/URL, same-window reuse, stale navigation/focus, protected target, cancellation and private URL refusal passed')
