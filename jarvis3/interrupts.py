"""An early speech-only stop. No incomplete transcript may perform a PC action."""
import re
HEAD=r'(?:stop talking|stop speaking|shut up|be quiet|hold on|enough|quiet|wait|stop|no)'
START=re.compile(r'^'+HEAD+r'\b',re.I)
def begins(text):return bool(START.match(text.strip()))
def request(text,known):
    match=re.fullmatch(HEAD+r'(?:\s*[,;.!]?\s+(.*))?[.!]?',text.strip(),re.I)
    if not match:return text
    tail=(match[1] or '').strip(' ,;.!')
    if not tail:return 'stop talking'
    tail=re.sub(r'^(?:actually(?: no)?|no|instead)[, ]+','',tail,flags=re.I).strip()
    return tail if known(tail) else None
