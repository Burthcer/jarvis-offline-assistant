"""Bounded same-utterance replacements; never execute a superseded first action."""
import re
def corrected_request(text,catalog=None):
    markers=list(re.finditer(r'\s*[,.;]?\s+actually(?:\s+(no)\b)?\s*[,;:]?\s*',text,flags=re.I))
    if not markers:return text
    original=text[:markers[0].start()].strip();tail=text[markers[-1].end():].strip(' .!?')
    explicit=any(m[1] or re.search(r'[,;.]',m[0]) for m in markers)
    data=bool(re.match(r'^(?:remind|remember|note|save (?:a )?note)\b',original,re.I))
    if data:
        # A note/reminder's words cannot pivot into PC commands accidentally.
        if not explicit and not re.match(r'^(?:make (?:it|that)|set (?:it|that)|i meant)\b',tail,re.I):return text
        return tail if re.match(r'^(?:remind|remember|note|save (?:a )?note)\b',tail,re.I) else None
    # Resolve each correction against the last understood request. Otherwise
    # "10 minutes, actually 20 seconds, actually 30" inherits minutes again.
    for index,marker in enumerate(markers):
        end=markers[index+1].start() if index+1<len(markers) else len(text)
        tail=text[marker.end():end].strip(' .!?')
        explicit=bool(marker[1] or re.search(r'[,;.]',marker[0]))
        if re.match(r'^(?:remind|remember|note|save (?:a )?note)\b',original,re.I):return None
        original=_replace(original,tail,explicit,catalog)
        if not original:return original
    return original

def _replace(original,tail,explicit,catalog):
    if not tail:return '' if explicit else None
    from .legacy.timeparse import _words_to_numbers
    amount=re.sub(r'^(?:make (?:it|that)|set (?:it|that)(?: to)?|change (?:it|that) to|(?:i )?(?:meant|mean))\s+','',tail,flags=re.I)
    spoken_amount=amount.lower().replace('-',' ')
    amount=_words_to_numbers('for '+spoken_amount).removeprefix('for ')
    if re.search(r'\btimer\b',original,re.I):
        units=re.findall(r'\b(seconds?|minutes?|hours?)\b',original,re.I)
        if re.fullmatch(r'\d+(?:\.\d+)?',amount) and units:amount+=' '+units[-1]
        if re.fullmatch(r'\d+(?:\.\d+)? (?:seconds?|minutes?|hours?)(?: (?:and )?\d+(?:\.\d+)? (?:seconds?|minutes?|hours?))*',amount):
            from .engine.registry import to_seconds
            if to_seconds(amount):
                spoken=spoken_amount+(' '+units[-1] if units and re.fullmatch(r'[a-z]+',spoken_amount) else '')
                if re.fullmatch(r'[a-z]+ (?:seconds?|minutes?|hours?)',spoken) and to_seconds(spoken)==to_seconds(amount):amount=spoken
                return 'set a timer for '+amount
    if re.search(r'\bvolume\b',original,re.I):
        match=re.fullmatch(r'(\d{1,3})(?: percent)?',amount)
        if match and 0<=int(match[1])<=100:return 'volume '+str(int(match[1]))
    if re.match(r'^(?:open|close|focus|set|remind|remember|play|pause|volume)\b',tail,re.I):return tail
    action=re.fullmatch(r'(open|close|focus|launch|start|switch to)\s+[^,;]+',original,re.I)
    if action and catalog and tail.lower() in catalog:return action[1]+' '+tail
    return None
