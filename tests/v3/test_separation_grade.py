"""Expected labels score results only; no models or PC effects."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from separation_grade import word_error,compare,call_ok,PROTOCOL
assert word_error('Jarvis open chrome','Jarvis, open Chrome.')=={'edits':0,'reference_words':3}
assert word_error('open chrome','open edge')['edits']==1
result=lambda calls,ok=True:{'calls':calls,'ok':ok,'addressed':bool(calls)}
assert compare(result([{'a':'timer_set','seconds':600}]),[{'a':'timer_set','seconds':600}])['match']
assert not compare(result([],False),[{'a':'timer_set','seconds':600}])['wrong_action']
assert compare(result([{'a':'open','target':'chrome'}]),[{'a':'open','target':'edge'}])['wrong_action']
assert compare(result([{'a':'media','action':'pause'}]),[{'a':'media','action':'pause'}])['match']
assert compare(result([{'a':'open','target':'chrome'}]),[])['wrong_action']
assert not compare(result([{'a':'media','action':'pause'}],False),[{'a':'media','action':'pause'}])['match']
assert compare(result([{'a':'search','query':'the quiet study playlists'}]),[{'a':'search','query':'quiet study playlists'}])['match'],'article-only query difference failed'
assert not compare(result([{'a':'search','query':'sports tickets flights hotels concerts'}]),[{'a':'search','query':'quiet study playlists'}])['match'],'unrelated query passed bounded overlap'
expected=[{'a':'open','target':'edge'}]
assert compare(result([{'a':'open','target':'microsoft edge','count':1}]),expected)['match'],'canonical target/default count rejected'
extra=compare(result([{'a':'open','target':'edge','count':3}]),expected)
assert not extra['match'] and extra['wrong_action'] and extra['reason']=='unexpected_argument'
for key,value in (('site','amazon'),('browser','chrome'),('app','spotify'),('level',80),('day','tomorrow')):
    extra=compare(result([{'a':'search','query':'quiet study playlists',key:value}]),[{'a':'search','query':'quiet study playlists'}])
    assert not extra['match'] and extra['wrong_action'] and extra['reason']=='unexpected_argument',(key,extra)
assert compare(result([{'a':'media','action':'pause'},{'a':'open','target':'chrome'}]),[{'a':'open','target':'google chrome'},{'a':'media','action':'pause'}])['match'],'established unordered call matching changed'
assert word_error('play a quiet study playlist','play the quiet study playlist')['edits']==1,'semantic grading changed exact word distance'

# Compare the copied policy against the existing harness functions without
# importing/running its models, corpus, tests or any expected command text.
import ast
source=Path(__file__).resolve().parents[1]/'v2/harness.py'
tree=ast.parse(source.read_text(encoding='utf-8'));names={'words','norm_when','targets_equal','call_ok','calls_ok'}
nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names or isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='CANON' for target in node.targets)]
namespace={'re':__import__('re')};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
examples=[({'a':'open','target':'chrome'},{'a':'open','target':'google chrome','count':1}),
          ({'a':'open','target':'edge'},{'a':'open','target':'edge','count':3}),
          ({'a':'search','query':'quiet study playlist'},{'a':'search','query':'a quiet study playlist'}),
          ({'a':'search','query':'quiet study playlist'},{'a':'search','query':'quiet study playlist','site':'youtube'}),
          ({'a':'timer_control','action':'status'},{'a':'timer_control','action':'status','which':'all'}),
          ({'a':'tab_close','which':'only'},{'a':'tab_close','which':None}),
          ({'a':'reminder_add','when':'tomorrow at 5 pm'},{'a':'reminder_add','when':'tomorrow 5 pm'})]
for wanted,actual in examples:assert call_ok(wanted,actual)==namespace['call_ok'](wanted,actual),(wanted,actual)
assert PROTOCOL=='existing-v2-harness-call-ok-v1'
print('SEPARATION GRADING: established harness parity, article/canonical/default matches, bounded queries, invented targets/count rejection, unchanged word distance and label isolation passed')
