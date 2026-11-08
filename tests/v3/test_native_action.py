"""No duplicate effects after ambiguous native event errors; no real window access."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.native_action import request
class Pattern:
    DefaultAction='Press'
    def __init__(self,fail=False):self.calls=[];self.fail=fail
    def DoDefaultAction(self,waitTime):
        self.calls.append(('default',waitTime))
        if self.fail:raise RuntimeError('event delivery failed after effect')
    def Invoke(self,waitTime):self.calls.append(('invoke',waitTime))
class Control:
    def __init__(self,legacy=True,fail=False):self.pattern=Pattern(fail);self.legacy=legacy
    def GetLegacyIAccessiblePattern(self):return self.pattern if self.legacy else None
    def GetInvokePattern(self):return self.pattern
for legacy,fail,want in ((True,False,'default'),(True,True,'default'),(False,False,'invoke')):
    c=Control(legacy,fail);assert request(c) and c.pattern.calls==[(want,0)]
assert not request(object())
print('NATIVE ACTION: preferred native default, bounded fallback choice, no sleep/no replay after ambiguous effect passed')
