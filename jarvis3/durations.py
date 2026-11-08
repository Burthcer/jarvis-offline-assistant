"""Bounded spoken durations, shared by direct routing and model validation."""
import re,math

SMALL=dict(zip(('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split(),range(20)))
TENS=dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10)))
WORDS=set(SMALL)|set(TENS)|{'hundred','and','a','an','half','quarter','of'}
UNIT=re.compile(r'\b(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b')
TOKEN=re.compile(r'\d+(?:\.\d+)?|[a-z]+|[^\w\s]')


def number(text):
    t=text.strip()
    if re.fullmatch(r'\d+(?:\.\d+)?',t):
        value=float(t)
        return value if math.isfinite(value) else None
    if t in ('a','an'):return 1
    if t.startswith(('a ','an ')):t=t.split(' ',1)[1]
    fraction=re.fullmatch(r'(?:(.+?) and )?(?:a |one )?(half|quarter)(?: of)?(?: an?| one)?',t)
    if fraction:
        whole=number(fraction[1]) if fraction[1] else 0
        return None if whole is None else whole+{'half':.5,'quarter':.25}[fraction[2]]
    parts=t.split()
    if len(parts)==1:return SMALL.get(t,TENS.get(t))
    if len(parts)==2 and parts[0] in TENS and parts[1] in SMALL and 0<SMALL[parts[1]]<10:
        return TENS[parts[0]]+SMALL[parts[1]]
    if len(parts)>=2 and parts[0] in SMALL and 0<SMALL[parts[0]]<10 and parts[1]=='hundred':
        rest=parts[2:]
        if rest[:1]==['and']:rest=rest[1:]
        tail=number(' '.join(rest)) if rest else 0
        if tail is not None and 0<=tail<100:return 100*SMALL[parts[0]]+tail
    return None


def normalized(text):
    t=str(text).lower()
    t=re.sub(r'(?<![\w.])\.(?=\d)','0.',t)
    # Spoken hyphens / saved timer labels; a minus sign is never a separator.
    t=re.sub(r'(?<=[a-z])-(?=[a-z])|(?<=\d)-(?=[a-z])',' ',t)
    return re.sub(r'(?<=\d)(?=(?:secs?|seconds?|mins?|minutes?|hrs?|hours?)\b)',' ',t)


def components(text):
    """Return (start,end,seconds) for whole numeric runs before duration units."""
    t=normalized(text);out=[]
    for unit in UNIT.finditer(t):
        tokens=list(TOKEN.finditer(t[:unit.start()]))
        run=[]
        for token in reversed(tokens):
            word=token[0]
            if word not in WORDS and not re.fullmatch(r'\d+(?:\.\d+)?',word):break
            run.append(token)
        if not run:continue
        run.reverse()
        while run and run[0][0]=='and':run.pop(0)
        if not run:continue
        start=run[0].start()
        prefix=t[:start]
        if start and (t[start-1].isalnum() or t[start-1] in '._'):continue
        if prefix.rstrip().endswith(('-','+')) or re.search(r'\b(?:minus|negative)\s*$',prefix):continue
        value=number(t[start:unit.start()])
        if value is None:continue
        multiplier=3600 if unit[0].startswith(('h','hr')) else 60 if unit[0].startswith('m') else 1
        amount=value*multiplier
        if math.isfinite(amount):out.append((start,unit.end(),amount))
    return t,out


def seconds(text):
    t,parts=components(text)
    if not parts:return None
    cursor=0
    for start,end,_ in parts:
        if t[cursor:start].strip(' ,') not in ('','and'):return None
        cursor=end
    if t[cursor:].strip(' ,'):return None
    total=sum(p[2] for p in parts)
    return round(total) if math.isfinite(total) and total>0 else None


def evidenced(value,text):
    """Every requested length must be present, including its units."""
    want=seconds(value)
    if want is None:return False
    t,parts=components(text)
    # Group hour+minute+second into one length. Repeated units are separate
    # lengths: two timers for ten and twenty minutes cannot become thirty.
    groups=[];end=0;scale=None
    for start,next_end,amount in parts:
        unit=UNIT.search(t[start:next_end])[0]
        next_scale=3600 if unit.startswith('h') else 60 if unit.startswith('m') else 1
        if groups and t[end:start].strip(' ,') in ('','and') and next_scale<scale:
            groups[-1]+=amount
        else:groups.append(amount)
        end=next_end;scale=next_scale
    return any(abs(total-want)<.001 for total in groups)
