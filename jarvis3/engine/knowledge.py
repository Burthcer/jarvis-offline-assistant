"""Typed views over existing facts; original records/IDs stay intact."""
import re
from urllib.parse import urlsplit

def website_url(value):
    value = value.strip()
    if re.search(r'[\s\\\x00-\x1f\x7f]', value):
        return None
    url=value if '://' in value else 'https://'+value
    try:
        parsed=urlsplit(url)
        port = parsed.port  # Reject malformed ports before handing a URL to the browser.
        if (parsed.scheme in ('http', 'https') and parsed.hostname
                and '.' in parsed.hostname and '@' not in parsed.netloc
                and (port is None or port > 0)):
            return url
    except ValueError:pass
    return None


def website_names(facts):
    """Map spoken names to saved website facts, preferring full names."""
    from .understand import norm

    exact, shorter = {}, {}
    for fact in facts:
        if fact['type'] != 'website' or fact['literal']:
            continue
        for name in (fact['label'], *fact['aliases']):
            words = norm(name).split()
            if not words:
                continue
            exact.setdefault(' '.join(words), {})[fact['id']] = fact
            for offset in range(1, len(words)):
                shorter.setdefault(' '.join(words[offset:]), {})[fact['id']] = fact
    return {**shorter, **exact}
def describe(text):
    match=re.fullmatch(r'my (.+?) (?:is|are) (.+)',text,re.I|re.S)
    label,value=(match[1],match[2]) if match else ('',text)
    secret=bool(re.search(r'password|secret|\bpin\b',re.sub(r'\b(?:postal )?pin\s*code\b','postal code',text,flags=re.I),re.I))
    kind='secret' if secret else 'email' if re.fullmatch(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}',value,re.I) else 'website' if website_url(value) else 'postal code' if re.search(r'postal|pin code|zip',label,re.I) else 'text'
    return {'label':label,'value':value,'type':kind,'secret':secret}
