"""Short-lived references and missing-target questions, separate from yes/no."""
import re

class Dialogue:
    def __init__(self):
        self.targets=[]; self.target_at=None; self.question=None; self.question_at=None

    def request(self,text,now):
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
        self.question=None
        targets=list(dict.fromkeys(c.args['target'] for c,r in results if r.ok and c.ability in ('open','close','focus') and c.args.get('target')))
        if targets: self.targets,self.target_at=targets,now
        if plan.kind=='ask':
            m=re.fullmatch(r'(?:please )?(open|close|focus)(?: up)?(?: (?:it|that|that app|that website))?[ .!?]*',text,re.I)
            if m: self.question,self.question_at=m[1].lower(),now
