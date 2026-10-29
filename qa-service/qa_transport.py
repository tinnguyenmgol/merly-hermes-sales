"""Fixed Merly public chat only. No URL argument, proxy, redirects or private IPs."""
import http.client,ipaddress,json,re,socket,ssl,time
from http.cookies import SimpleCookie
HOST='chat.merlyshoes.com';ORIGIN='https://'+HOST
COOKIE='__Host-merly_public_session';MAX_BODY=131072
ALLOWED={('GET','/api/public/session'),('POST','/api/public/chat')}
class TransportError(Exception):
    def __init__(self,code,http_status=None):self.code=code;self.http_status=http_status

class FixedHTTPS(http.client.HTTPSConnection):
    def __init__(self,timeout):super().__init__(HOST,443,timeout=timeout,context=ssl.create_default_context())
    def connect(self):
        end=time.monotonic()+self.timeout
        answers=socket.getaddrinfo(HOST,443,type=socket.SOCK_STREAM)
        if not answers:raise TransportError('dns_failed')
        if any(not ipaddress.ip_address(row[4][0]).is_global for row in answers):raise TransportError('destination_rejected')
        for row in answers[:4]:
            remaining=end-time.monotonic()
            if remaining<=0:raise TransportError('timeout')
            try:
                self.sock=socket.create_connection((row[4][0],443),min(10,remaining))
                self.sock=self._context.wrap_socket(self.sock,server_hostname=HOST)
                return
            except OSError:
                if self.sock:self.sock.close();self.sock=None
        raise TransportError('connection_failed')

class ChatSession:
    def __init__(self,deadline,connection=FixedHTTPS):
        self.deadline=deadline;self.connection=connection;self.cookie=None;self.csrf=None
    def request(self,method,path,body=None):
        if (method,path) not in ALLOWED:raise TransportError('endpoint_rejected')
        remaining=self.deadline-time.monotonic()
        if remaining<=0:raise TransportError('run_deadline')
        conn=self.connection(min(60,remaining))
        headers={'Accept':'application/json','User-Agent':'Merly-QA/1','Origin':ORIGIN}
        if self.cookie:headers['Cookie']=COOKIE+'='+self.cookie
        if self.csrf:headers['X-Merly-CSRF']=self.csrf
        if body is not None:headers['Content-Type']='application/json'
        try:
            conn.connect()
            if time.monotonic()>=self.deadline:raise TransportError('run_deadline')
            if conn.sock:conn.sock.settimeout(min(60,self.deadline-time.monotonic()))
            conn.request(method,path,body=json.dumps(body).encode() if body is not None else None,headers=headers)
            response=conn.getresponse();status=response.status;chunks=[];length=0
            while True:
                remaining=self.deadline-time.monotonic()
                if remaining<=0:raise TransportError('run_deadline')
                if conn.sock:conn.sock.settimeout(min(60,remaining))
                part=response.read1(min(8192,MAX_BODY+1-length))
                if not part:break
                chunks.append(part);length+=len(part)
                if length>MAX_BODY:raise TransportError('response_too_large',status)
            raw=b''.join(chunks)
            if 300<=status<400:raise TransportError('redirect_rejected',status)
            if len(raw)>MAX_BODY:raise TransportError('response_too_large',status)
            try:data=json.loads(raw)
            except (ValueError,UnicodeError):raise TransportError('invalid_json',status) from None
            if not isinstance(data,dict):raise TransportError('invalid_response',status)
            return status,data,response.getheaders()
        except TransportError:raise
        except (TimeoutError,socket.timeout):raise TransportError('timeout') from None
        except (OSError,ssl.SSLError,http.client.HTTPException):raise TransportError('connection_failed') from None
        finally:conn.close()
    def bootstrap(self):
        status,data,headers=self.request('GET','/api/public/session')
        if status!=200:raise TransportError('session_http_error',status)
        token=data.get('csrf')
        if not isinstance(token,str) or not re.fullmatch('[0-9a-f]{64}',token):raise TransportError('invalid_session')
        for key,value in headers:
            if key.lower()!='set-cookie':continue
            jar=SimpleCookie();jar.load(value)
            if COOKIE not in jar:continue
            c=jar[COOKIE]
            if c['domain'] or c['path']!='/' or not c['secure'] or not re.fullmatch('[A-Za-z0-9_-]{43}',c.value):raise TransportError('invalid_cookie')
            self.cookie=c.value
        if not self.cookie:raise TransportError('missing_cookie')
        self.csrf=token
    def send(self,message):return self.request('POST','/api/public/chat',{'message':message})[:2]
