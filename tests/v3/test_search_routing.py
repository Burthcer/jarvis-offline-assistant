"""Whole-command exact search scopes, fake URL effects and hostile boundaries.

Only the two approved even-index families were used as diagnostic examples.
Other examples are new synthetic grammar/safety checks, not held-out labels.
"""
import json,os,sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus
os.environ['JARVIS_SILENT']='1'
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from jarvis3.engine.abilities.web import search_route,search,SITES
from jarvis3.engine.osapi import Fake
catalog=json.loads((ROOT/'data/gold/catalog.json').read_text(encoding='utf-8'))

for text,wanted in (
 ('Open YouTube and search lo-fi music',{'query':'lo-fi music','site':'youtube'}),
 ('search Royal Renderings on Patreon',{'query':'Royal Renderings','site':'patreon'}),
 ('search C++ & memory safety on YouTube with Chrome',{'query':'C++ & memory safety','site':'youtube','browser':'chrome'}),
 ('search train times using Chrome on YouTube',{'query':'train times','site':'youtube','browser':'chrome'}),
 ('search using Chrome type annotations on Patreon',{'query':'type annotations','site':'patreon','browser':'chrome'}),
 ('look up css grid with Chrome',{'query':'css grid','browser':'chrome'}),
 ('search on the Edge browser type annotations',{'query':'type annotations','browser':'edge'}),
 ('search museum opening times on Chrome',{'query':'museum opening times','browser':'chrome'}),
 ('search coastal birds on YouTube using the Chrome browser',{'query':'coastal birds','site':'youtube','browser':'chrome'}),
 ('search YouTube for quiet piano',{'query':'quiet piano','site':'youtube'}),
 ('search on Amazon for desk lamps',{'query':'desk lamps','site':'amazon'}),
 ('look up in YouTube Music for acoustic guitar',{'query':'acoustic guitar','site':'youtube music'}),
 ('search for YouTube tutorials',{'query':'YouTube tutorials'}),
 ('google meetings on Mars',{'query':'meetings on Mars'}),
 ('search books on amazon river',{'query':'books on amazon river'}),
 ('search with Chrome papers on an unknown site',{'query':'papers on an unknown site','browser':'chrome'}),
 ('search on Chrome type annotations',{'query':'type annotations','browser':'chrome'}),
 ('open up YouTube Music and then search rock and roll',{'query':'rock and roll','site':'youtube music'}),
 ('search design jobs on LinkedIn',{'query':'design jobs','site':'linkedin'}),
):
 calls=search_route(text,catalog)
 assert calls==[('search',wanted)],(text,calls)
 pc=Fake();result=search(wanted,SimpleNamespace(os=pc,catalog=catalog))
 assert result.ok and len(pc.log)==1 and pc.log[0][0]=='url'
 site=wanted.get('site','google');query=wanted['query']
 if catalog.get(site)=='site' and site in SITES and SITES[site][2]:
  expected=(wanted.get('browser') or SITES[site][0],SITES[site][2]+quote_plus(query))
 else:expected=(wanted.get('browser','edge'),SITES['google'][2]+quote_plus(query if site=='google' else query+' '+site))
 assert pc.log[0]==('url',*expected),(text,pc.log,expected)

# Empty/ambiguous catalog names must never become invented site scope.
assert search_route('search loops on YouTube',{})==[('search',{'query':'loops on YouTube'})]
ambiguous={'youtube':'site','YOUTUBE':'site'}
assert search_route('search loops on YouTube',ambiguous)==[('search',{'query':'loops on YouTube'})]
assert search_route('open YouTube and search loops',ambiguous) is None
assert search_route('search A with Chrome',{'chrome':'app'})==[('search',{'query':'A','browser':'chrome'})]

for text in (
 'how do I search on YouTube',
 'could you tell me how to search on Patreon',
 'do not search private notes on YouTube',
 'never search that on Patreon',
 'search cats on YouTube and close Chrome',
 'search cats on YouTube; close Chrome',
 'search cats on YouTube. open Chrome',
 'search cats on YouTube and do not open Chrome',
 'search cats on YouTube but close Chrome',
 'search cats with Edge using Chrome',
 'search cats on YouTube on Patreon',
 'open YouTube and search cats on Patreon',
 'open unknown site and search cats',
 'open YouTube and search cats and search dogs',
 'search '+('x'*201),
 'search',
):assert search_route(text,catalog) is None,(text,search_route(text,catalog))
print('SEARCH ROUTING: exact site/browser scopes, open+search, default browser, literal unknown-on text, full URL encoding and no dropped compound/question/negation passed')
