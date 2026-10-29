import io,json,socket,ssl,time
import pytest
import qa_transport as t

class Response:
    def __init__(self,status,data,headers=()):self.status=status;self.body=io.BytesIO(data if isinstance(data,bytes) else json.dumps(data).encode());self.headers=list(headers)
    def read1(self,n):return self.body.read(n)
    def getheaders(self):return self.headers
class Connection:
    def __init__(self,responses):self.responses=responses;self.sent=[];self.sock=None
    def connect(self):pass
    def request(self,*args,**kwargs):self.sent.append((args,kwargs))
    def getresponse(self):return self.responses.pop(0)
    def close(self):pass

def test_only_fixed_endpoints_cookie_csrf_and_no_authorization_forwarded():
    cookie='C'*43;csrf='a'*64
    conn=Connection([Response(200,{'csrf':csrf},[('Set-Cookie',t.COOKIE+'='+cookie+'; Path=/; Secure; HttpOnly; SameSite=Strict')]),Response(200,{'reply':'ACK'})])
    session=t.ChatSession(time.monotonic()+20,lambda timeout:conn)
    session.bootstrap();assert session.send('SYNTHETIC')[1]['reply']=='ACK'
    args,kwargs=conn.sent[-1]
    assert args==('POST','/api/public/chat')
    assert kwargs['headers']['Cookie']==t.COOKIE+'='+cookie
    assert kwargs['headers']['X-Merly-CSRF']==csrf and kwargs['headers']['Origin']==t.ORIGIN
    assert 'Authorization' not in kwargs['headers']
    with pytest.raises(t.TransportError) as e:session.request('GET','https://evil.invalid/')
    assert e.value.code=='endpoint_rejected'

@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','192.168.1.1','169.254.169.254','::1','fd00::1','::ffff:127.0.0.1'])
def test_private_addresses_are_never_connected(monkeypatch,ip):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',(ip,443))])
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('must not connect'))
    with pytest.raises(t.TransportError) as e:t.FixedHTTPS(1).connect()
    assert e.value.code=='destination_rejected'


def test_public_ip_is_pinned_and_tls_keeps_real_hostname(monkeypatch):
    seen=[];context=ssl.create_default_context();wrapped=[]
    class Sock:
        def close(self):pass
    monkeypatch.setattr(socket,'getaddrinfo',lambda host,port,**kw:seen.append((host,port)) or [(2,1,6,'',('1.1.1.1',443))])
    monkeypatch.setattr(socket,'create_connection',lambda address,timeout:seen.append(address) or Sock())
    monkeypatch.setattr(context,'wrap_socket',lambda sock,server_hostname:wrapped.append(server_hostname) or sock)
    monkeypatch.setattr(ssl,'create_default_context',lambda:context)
    conn=t.FixedHTTPS(2);conn.connect()
    assert seen==[(t.HOST,443),('1.1.1.1',443)] and wrapped==[t.HOST]
    assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED

@pytest.mark.parametrize('cookie',[
 t.COOKIE+'='+'C'*43+'; Path=/; HttpOnly',
 t.COOKIE+'='+'C'*43+'; Path=/; Secure; Domain=evil.invalid',
 t.COOKIE+'='+'C'*43+'; Path=/admin; Secure',
 t.COOKIE+'=malformed; Path=/; Secure'])
def test_invalid_host_cookie_is_rejected(cookie):
    conn=Connection([Response(200,{'csrf':'a'*64},[('Set-Cookie',cookie)])])
    session=t.ChatSession(time.monotonic()+5,lambda _:conn)
    with pytest.raises(t.TransportError) as e:session.bootstrap()
    assert e.value.code=='invalid_cookie'

@pytest.mark.parametrize('status,body,expected',[(302,{},'redirect_rejected'),(503,b'<html>PRIVATE_RAW_SENTINEL</html>','invalid_json'),(200,[], 'invalid_response'),(200,b'x'*(t.MAX_BODY+1),'response_too_large')])
def test_no_redirect_following_raw_errors_or_unbounded_body(status,body,expected):
    conn=Connection([Response(status,body)])
    session=t.ChatSession(time.monotonic()+5,lambda _:conn)
    with pytest.raises(t.TransportError) as e:session.request('GET','/api/public/session')
    assert e.value.code==expected and 'PRIVATE_RAW_SENTINEL' not in str(e.value)
    assert len(conn.sent)==1


def test_expired_deadline_does_not_open_connection():
    session=t.ChatSession(time.monotonic()-1,lambda _:pytest.fail('must not connect'))
    with pytest.raises(t.TransportError) as e:session.request('GET','/api/public/session')
    assert e.value.code=='run_deadline'
