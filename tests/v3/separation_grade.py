"""Grading only: expected labels never enter ASR, NLU or speaker selection.

Call agreement uses the established tests/v2/harness.py criteria. These are
bounded heuristic matches, not proof of complete semantic correctness/safety.
Prompt word distance remains the original exact token edit distance.
"""
import re
PROTOCOL='existing-v2-harness-call-ok-v1'
CANON={'google chrome':'chrome','microsoft edge':'edge','whatsapp - shortcut':'whatsapp','chat gpt':'chatgpt','gpt':'chatgpt','explorer':'file explorer','files':'file explorer',
       'whisper flow':'wispr flow','whisper no pro':'wisperno pro','wisperno':'wisperno pro','anti gravity':'antigravity','quickshare':'quick share','armory crate':'armoury crate',
       'antigravity ide':'antigravity','claude code':'claude'}
def words(text):
    text=re.sub(r'(?<=\d),(?=\d)','',text.lower())
    return re.findall(r"[a-z]+(?:'[a-z]+)?|\d+(?:\.\d+)?",text)
def word_error(reference,text):
    a,b=words(reference),words(text);previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):row.append(min(row[-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
        previous=row
    return {'edits':previous[-1],'reference_words':len(a)}
def semantic_words(value):
    value=str(value).lower().replace(' at the rate ','@')
    return set(re.findall(r'[a-z0-9@.]+',value))-{'the','a','an','my','to','for','i','that','is','of','it','at','on','by','have'}

def norm_when(value):return re.sub(r'\s+','',re.sub(r'\b(at|by|on)\b',' ',value.lower())).replace('.','')

def targets_equal(want,got):
    wanted,actual=CANON.get(want,want),CANON.get(str(got).lower(),str(got).lower())
    return wanted==actual or wanted.replace(' ','')==actual.replace(' ','')

def call_reason(want,got):
    if want['a']!=got.get('a'):return 'ability_mismatch'
    if want['a']=='timer_control' and got.get('action')=='status' and want['action']=='status':return ''
    for key,value in want.items():
        if key=='a':continue
        actual=got.get(key)
        if key in ('target','site','app'):ok=actual is not None and targets_equal(value,actual)
        elif key in ('query','text','item'):
            a,b=semantic_words(value),semantic_words(actual or '')
            ok=len(a&b)>=.6*max(len(a),1) and len(b-a)<=max(1,len(a)*.5)
        elif key=='when':ok=bool(actual) and norm_when(actual)==norm_when(value)
        elif key=='which':ok=value=='only' and actual in (None,'','only') or str(actual)==str(value)
        elif key=='count':ok=bool(actual)==bool(value)
        else:ok=actual==value or str(actual)==str(value)
        if not ok:return 'argument_mismatch'
    for key in ('site','browser','app','count','level','day'):
        if got.get(key) not in (None,'',0,1,False) and key not in want:return 'unexpected_argument'
    return ''

def call_ok(want,got):return not call_reason(want,got)

def calls_reason(expected,actual):
    remaining=list(actual)
    if len(expected)!=len(remaining):return 'call_count_mismatch'
    for wanted in expected:
        reasons=[call_reason(wanted,got) for got in remaining]
        if '' in reasons:remaining.pop(reasons.index(''))
        elif 'unexpected_argument' in reasons:return 'unexpected_argument'
        elif 'argument_mismatch' in reasons:return 'argument_mismatch'
        else:return 'ability_mismatch'
    return ''

def compare(result,expected):
    actual=result['calls']
    reason=calls_reason(expected,actual);plan=not reason
    return {'addressed':result['addressed'],'actions':len(actual),'match':bool(result['ok'] and plan),
            'wrong_action':bool(actual and not plan),'reason':reason or ('matched' if result['ok'] else 'not_completed')}
