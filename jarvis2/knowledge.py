"""Typed views over existing facts; original records/IDs stay intact."""
import re
from urllib.parse import urlsplit

def website_url(value):
    url=value if '://' in value else 'https://'+value
    try:
        parsed=urlsplit(url)
        if parsed.scheme in ('http','https') and parsed.hostname and '.' in parsed.hostname and not re.search(r'\s',url) and not parsed.username and not parsed.password:
            return url
    except ValueError:pass
    return None
def describe(text):
    match=re.fullmatch(r'my (.+?) (?:is|are) (.+)',text,re.I|re.S)
    label,value=(match[1],match[2]) if match else ('',text)
    secret=bool(re.search(r'password|secret|\bpin\b',re.sub(r'\b(?:postal )?pin\s*code\b','postal code',text,flags=re.I),re.I))
    kind='secret' if secret else 'email' if re.fullmatch(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}',value,re.I) else 'website' if website_url(value) else 'postal code' if re.search(r'postal|pin code|zip',label,re.I) else 'text'
    return {'label':label,'value':value,'type':kind,'secret':secret}
