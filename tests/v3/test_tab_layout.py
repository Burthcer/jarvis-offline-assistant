"""Native tab tree shapes; content tabs excluded, no screen/app access."""
import os,sys
from pathlib import Path
os.environ['JARVIS_SILENT']='1';sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis3.engine.browser_tabs import discover_tab_controls
class Node:
    serial=0
    def __init__(self,kind,*children):
        self.ControlTypeName=kind;self.children=list(children);Node.serial+=1;self.id=Node.serial
    def GetChildren(self):return self.children
    def GetRuntimeId(self):return (self.id,)
def wrapped(node,n):
    for _ in range(n):node=Node('PaneControl',node)
    return node
tabs=[Node('TabItemControl') for _ in range(6)]
bar=Node('TabControl',wrapped(Node('TabControl',*tabs),10))
root=Node('WindowControl',wrapped(bar,4),Node('DocumentControl',Node('TabControl',Node('TabItemControl'))))
assert discover_tab_controls(root)==tabs,'Vertical tree not read or page controls included'
pinned=Node('TabItemControl');grouped=Node('TabItemControl')
root=Node('WindowControl',Node('TabControl',Node('PaneControl',pinned),Node('GroupControl',grouped)))
assert discover_tab_controls(root)==[pinned,grouped]
try:discover_tab_controls(Node('WindowControl',Node('TabControl',tabs[0]),Node('TabControl',tabs[1])));raise AssertionError('ambiguous native bars accepted')
except ValueError:pass
try:discover_tab_controls(Node('TabControl',*([Node('PaneControl')]*1300),tabs[0]));raise AssertionError('partial tree accepted')
except ValueError:pass
print('TAB LAYOUT: deep vertical/pinned/grouped nodes, page exclusion, ambiguity and bounded-completeness checks passed')
from jarvis3.engine.abilities.web import tab_route
for words in ('close this tab','close this fucking tab','shut down this tab'):
    assert tab_route(words)==[('tab_close',{'which':'this'})],words
assert tab_route('close tabs 2 and 3')==[('browser_tabs',{'action':'close','selector':'2 and 3'})]
assert tab_route('closed the second and third youtube tabs')==[('tab_group_close',{'selector':'second and third','site':'youtube'})]
assert tab_route('close all youtube tabs')==[('tab_close',{'which':'all','site':'youtube'})]
