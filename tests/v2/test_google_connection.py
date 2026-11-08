"""Google OAuth is mocked; callback uses only a local test server. No accounts."""
import os,sys,time,threading,base64,hashlib
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,urlencode
from urllib.request import urlopen
os.environ['JARVIS_SILENT']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis2.google_connection import GoogleConnection,SCOPES,TOKEN
class Vault:
    value=None
    def get(self):return self.value
    def put(self,value):self.value=value
    def remove(self):self.value=None
vault=Vault(); calls=[]; captured={}
def request(url,form=None,token=None):
    calls.append((url,form,token))
    if url==TOKEN:
        if form['grant_type']=='authorization_code':
            challenge=base64.urlsafe_b64encode(hashlib.sha256(form['code_verifier'].encode()).digest()).decode().rstrip('=')
            assert challenge==captured['code_challenge'][0] and form['code']=='mock-code'
        return {'refresh_token':'mock-refresh','access_token':'mock-access','expires_in':3600,'scope':' '.join(SCOPES)}
    if '/calendar/' in url:return {'items':[{'summary':'Exam','start':{'date':'2026-11-23'}}]}
    if '/messages?' in url:return {'messages':[{'id':'abc123'}]}
    return {'payload':{'headers':[{'name':'Subject','value':'Lab assignment'},{'name':'From','value':'teacher@example.test'}]}}
connection=GoogleConnection(vault,request)
assert not connection.status()['connected']
def browser(url):
    captured.update(parse_qs(urlsplit(url).query))
    assert set(captured['scope'][0].split())==set(SCOPES)
    assert captured['code_challenge_method']==['S256']
    def callback():
        bad=captured['redirect_uri'][0]+'?'+urlencode({'state':'wrong','code':'bad'})
        try:urlopen(bad,timeout=3)
        except Exception:pass
        good=captured['redirect_uri'][0]+'?'+urlencode({'state':captured['state'][0],'code':'mock-code'})
        with urlopen(good,timeout=3) as response:assert response.status==200
    threading.Thread(target=callback,daemon=True).start()
connection.connect({'installed':{'client_id':'mock.apps.googleusercontent.com'}},browser)
end=time.monotonic()+5
while connection.busy and time.monotonic()<end:time.sleep(.02)
assert connection.status()['connected'],connection.status()
assert 'access_token' not in vault.value and vault.value['refresh_token']=='mock-refresh'
assert connection.read('gmail')[0]['title']=='Lab assignment'
assert connection.read('calendar')[0]['title']=='Exam'
connection.expires=0
assert connection.read('calendar')
assert any(form and form['grant_type']=='refresh_token' for url,form,token in calls)
connection.disconnect();assert not connection.status()['connected']
try:connection.connect({'web':{'client_id':'wrong'}},browser)
except ValueError:pass
else:raise AssertionError('web credentials accepted as Desktop client')
print('GOOGLE MOCK OAUTH/READ-ONLY CONNECTION PASSED')
