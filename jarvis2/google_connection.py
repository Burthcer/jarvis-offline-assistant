"""Explicit Google desktop OAuth+PKCE, read-only Gmail/Calendar. No auto sync."""
import base64,hashlib,json,secrets,threading,time
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,HTTPServer
from urllib.parse import urlencode,urlsplit,parse_qs,quote
from urllib.request import Request,urlopen
from . import credential_store

SCOPES=('https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/calendar.events.readonly')
TOKEN='https://oauth2.googleapis.com/token'
def exchange(url,form=None,token=None):
    data=urlencode(form).encode() if form is not None else None
    headers={'Content-Type':'application/x-www-form-urlencoded'} if form is not None else {}
    if token:headers['Authorization']='Bearer '+token
    with urlopen(Request(url,data=data,headers=headers),timeout=15) as response:
        content=response.read(1024*1024+1)
    if len(content)>1024*1024:raise ValueError('Google response was too large.')
    return json.loads(content)

class GoogleConnection:
    def __init__(self,vault=credential_store,request=exchange):
        self.vault,self.request=vault,request
        self.message='Not connected';self.busy=False;self.access=None;self.expires=0;self.lock=threading.RLock();self.cancel=threading.Event()
    def status(self):
        connected=bool(self.vault.get())
        return {'connected':connected,'busy':self.busy,'message':'Connected: Gmail and Google Calendar, read-only.' if connected and self.message=='Not connected' else self.message}
    def disconnect(self):
        self.cancel.set()
        with self.lock:self.vault.remove();self.access=None;self.expires=0;self.message='Disconnected locally. You can also revoke Jarvis in your Google account.'
    def connect(self,configuration,open_browser):
        client=configuration.get('installed',{})
        if not isinstance(client,dict) or not str(client.get('client_id','')).endswith('.apps.googleusercontent.com'):
            raise ValueError('Choose a Google Desktop OAuth client JSON file. Jarvis needs its own registered client, not your password.')
        with self.lock:
            if self.busy:return
            self.busy=True;self.cancel.clear();self.message='Waiting for Google sign-in in your browser.'
        def work():
            state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
            challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
            answer={}
            class Callback(BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_GET(handler):
                    parsed=urlsplit(handler.path); values=parse_qs(parsed.query)
                    valid=parsed.path=='/callback' and secrets.compare_digest(values.get('state',[''])[0].encode(),state.encode())
                    if valid:
                        if values.get('code'):answer['code']=values['code'][0]
                        elif values.get('error'):answer['error']=True
                    handler.send_response(200 if valid else 400);handler.end_headers();handler.wfile.write(b'You may return to Jarvis.' if valid else b'Invalid sign-in callback.')
            try:
                with HTTPServer(('127.0.0.1',0),Callback) as server:
                    server.timeout=.3; redirect=f'http://127.0.0.1:{server.server_port}/callback'
                    url='https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':client['client_id'],'redirect_uri':redirect,'response_type':'code','scope':' '.join(SCOPES),'state':state,'code_challenge':challenge,'code_challenge_method':'S256','access_type':'offline','prompt':'consent'})
                    open_browser(url)
                    end=time.monotonic()+180
                    while not answer and time.monotonic()<end and not self.cancel.is_set():server.handle_request()
                    if not answer.get('code') or self.cancel.is_set():raise ValueError('Google sign-in was cancelled or timed out.')
                    token=self.request(TOKEN,{'grant_type':'authorization_code','client_id':client['client_id'],'client_secret':client.get('client_secret',''),'code':answer['code'],'code_verifier':verifier,'redirect_uri':redirect})
                    if not token.get('refresh_token'):raise ValueError('Google did not return offline permission. Please reconnect.')
                    granted=set(token.get('scope',' '.join(SCOPES)).split())
                    if not set(SCOPES)<=granted:raise ValueError('Both read permissions are required for this connection.')
                    with self.lock:
                        if self.cancel.is_set():return
                        self.vault.put({'client_id':client['client_id'],'client_secret':client.get('client_secret',''),'refresh_token':token['refresh_token']})
                        self.access=token.get('access_token');self.expires=time.time()+int(token.get('expires_in',3600))-60
                        self.message='Connected: Gmail and Google Calendar, read-only.'
            except ValueError as error:self.message=str(error)
            except Exception:self.message='Google connection failed. Check that Gmail and Calendar APIs are enabled for the Desktop client.'
            finally:self.busy=False
        threading.Thread(target=work,daemon=True).start()
    def _token(self):
        with self.lock:
            if self.access and time.time()<self.expires:return self.access
            saved=self.vault.get()
            if not saved:raise ValueError('Connect Google in Settings first.')
            response=self.request(TOKEN,{'grant_type':'refresh_token',**saved})
            self.access=response['access_token'];self.expires=time.time()+int(response.get('expires_in',3600))-60
            return self.access
    def read(self,what):
        token=self._token()
        if what=='calendar':
            now=datetime.now(timezone.utc)
            params=urlencode({'timeMin':now.isoformat(),'timeMax':(now+timedelta(days=7)).isoformat(),'maxResults':20,'singleEvents':'true','orderBy':'startTime'})
            data=self.request('https://www.googleapis.com/calendar/v3/calendars/primary/events?'+params,token=token)
            return [{'title':item.get('summary','Untitled event'),'when':item.get('start',{}).get('dateTime',item.get('start',{}).get('date',''))} for item in data.get('items',[]) if item.get('status')!='cancelled']
        if what!='gmail':raise ValueError('Unsupported connection request.')
        data=self.request('https://gmail.googleapis.com/gmail/v1/users/me/messages?'+urlencode({'q':'is:unread','maxResults':5}),token=token)
        out=[]
        for item in data.get('messages',[])[:5]:
            message=self.request('https://gmail.googleapis.com/gmail/v1/users/me/messages/'+quote(str(item['id']),safe='')+'?format=metadata&metadataHeaders=Subject&metadataHeaders=From',token=token)
            headers={h.get('name','').lower():h.get('value','') for h in message.get('payload',{}).get('headers',[])}
            out.append({'title':headers.get('subject','No subject'),'from':headers.get('from','Unknown sender')})
        return out
