"""Native address scope with fake controls; never reads a real window or clipboard."""
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from contextlib import nullcontext
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.reference import safe_url,front_url
from jarvis3.engine import uia
for unsafe in ('javascript:alert(1)','file:///private/report','https://x:y@example.com/report','https://example.com/?access_token=secret','https://example.com/#token=secret','https://example.com/#code=secret','https://example.com/#/callback?auth=secret','https://bank.example.com/','https://example.com/login','https://example.com/?api_key=secret'):
    assert safe_url(unsafe) is None,unsafe
assert safe_url('example.com/report?id=7')=='https://example.com/report?id=7'
class Node:
    def __init__(self,kind,children=(),name='',url='',password=False):self.ControlTypeName=kind;self.children=children;self.Name=name;self.url=url;self.IsPassword=password
    def GetChildren(self):
        assert self.ControlTypeName!='DocumentControl','Page/DOM content was read'
        return self.children
    def GetValuePattern(self):
        assert not self.IsPassword,'Password read'
        return NS(Value=self.url)
edit=Node('EditControl',name='Address and search bar',url='https://example.com/article')
root=Node('WindowControl',[Node('DocumentControl',[Node('EditControl',name='Address and search bar',url='https://evil.example/')]),Node('EditControl',password=True),edit])
backend=NS(_browsers=lambda:[123],_title=lambda h:'Project - Microsoft Edge')
auto=NS(UIAutomationInitializerInThread=nullcontext,ControlFromHandle=lambda h:root)
with patch.object(uia,'_auto',return_value=auto),patch.object(uia,'bound_client'),patch('jarvis3.reference.ctypes.windll.user32.GetForegroundWindow',lambda:123):
    assert front_url(backend)=='https://example.com/article'
    root.children.append(edit);assert front_url(backend) is None,'ambiguous native address accepted';root.children.pop()
    backend._title=lambda h:'Password manager login';assert front_url(backend) is None
print('REFERENCE: native-only address, no document/password reads, URL secret/credential/protected/ambiguity guards passed')
