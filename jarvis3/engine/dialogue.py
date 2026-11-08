"""Short-lived references and missing-target questions, separate from yes/no."""
import re
from dataclasses import dataclass,replace

ORDINALS={word:index for index,word in enumerate('first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth'.split(),1)}
ORDINAL=re.compile(r'(?:the )?(last|'+ '|'.join(ORDINALS) +r'|\d+(?:st|nd|rd|th)?)(?: (?:one|timer))?[.!?]*',re.I)

def timer_pool(store,action):
    if action=='cancel':return store.all_timers()
    if action in ('pause','status'):return store.timers()
    if action=='resume':return [row for row in store.all_timers() if row['status']=='paused']
    return []

@dataclass(frozen=True)
class TimerChoice:
    action:str
    rows:tuple
    at:object
    store:object  # ephemeral identity only; never a model argument or persisted
    selected_id:int|None=None

def timer_choice_valid(choice,store,now,action):
    if not isinstance(choice,TimerChoice) or choice.store is not store or choice.action!=action:return False
    if not 0<=(now-choice.at).total_seconds()<120:return False
    try:return tuple(dict(row) for row in timer_pool(store,action))==choice.rows
    except Exception:return False

class Dialogue:
    def __init__(self):
        self.targets=[]; self.target_at=None; self.question=None; self.question_at=None
        self.timer_question=None

    def bind_timer_choices(self,action,rows,store,now):
        self.timer_question=TimerChoice(action,tuple(dict(row) for row in rows),now,store)

    def cancel_timer_choices(self):self.timer_question=None

    def request(self,text,now):
        choices=self.timer_question
        if choices:
            match=ORDINAL.fullmatch(text.strip())
            if match:
                from .understand import Plan,Call
                with choices.store.lock:valid=timer_choice_valid(choices,choices.store,now,choices.action)
                if not valid:
                    self.timer_question=None
                    return Plan('ask',say='Those timer choices changed or expired. Please ask again, sir.',source='dialogue'),None
                word=match[1].lower()
                position=len(choices.rows) if word=='last' else ORDINALS.get(word)
                if position is None:position=int(re.sub(r'\D','',word))
                if not 1<=position<=len(choices.rows):
                    plan=Plan('ask',say=f'Choose one of the {len(choices.rows)} listed timers, sir.',source='dialogue')
                    plan.timer_question=choices
                    return plan,None
                row=choices.rows[position-1]
                from jarvis3.legacy.actions import label_secs
                seconds=label_secs(row['text'])
                args={'action':choices.action,**({'which':str(seconds)} if seconds else {})}
                plan=Plan('act',calls=[Call('timer_control',args)],source='dialogue')
                plan.timer_choice=replace(choices,selected_id=row['id'])
                self.timer_question=None
                return plan,None
            self.timer_question=None  # an unrelated request replaces this question
        m=re.fullmatch(r'(open|close|focus)\s+(it|that|that app|that website)[.!]?',text.strip(),re.I)
        if m:
            if self.target_at and (now-self.target_at).total_seconds()<120 and len(self.targets)==1:
                return m[1]+' '+self.targets[0],None
            return text,'Which app or website do you mean, sir?'
        if self.question and (now-self.question_at).total_seconds()<120:
            if re.fullmatch(r"[\w .'-]{1,60}",text) and not re.search(r'\b(open|close|focus|stop|cancel|yes|no|set|play|copy|remember|search|minimize|maximize|restore)\b',text,re.I):
                return self.question+' '+text,None
        return text,None

    def remember(self,text,plan,results,now):
        choices=self.timer_question
        if choices and not (plan.kind=='ask' and (getattr(plan,'timer_question',None) is choices or (choices.at==now and any(c.ability=='timer_control' for c in plan.calls)))):
            self.timer_question=None
        self.question=None
        targets=list(dict.fromkeys(c.args['target'] for c,r in results if r.ok and c.ability in ('open','close','focus') and c.args.get('target')))
        if targets: self.targets,self.target_at=targets,now
        if plan.kind=='ask':
            m=re.fullmatch(r'(?:please )?(open|close|focus)(?: up)?(?: (?:it|that|that app|that website))?[ .!?]*',text,re.I)
            if m: self.question,self.question_at=m[1].lower(),now
