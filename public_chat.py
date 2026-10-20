"""Public visitor adapter; existing private gateway remains server-only."""
import hashlib,hmac,io,json,os,re,secrets
from http.cookies import SimpleCookie
from pathlib import Path
COOKIE='__Host-merly_public_session'
ROOT=Path(__file__).with_name('public-web')

def enabled():return os.getenv('MERLY_PUBLIC_CHAT_ENABLED','0')=='1'
def csrf(token):return hmac.new(os.environ['PILOT_SESSION_SECRET'].encode(),('public-csrf:'+token).encode(),hashlib.sha256).hexdigest()
def visitor(env):
    try:
        c=SimpleCookie();c.load(env.get('HTTP_COOKIE',''));value=c[COOKIE].value
        return value if re.fullmatch(r'[A-Za-z0-9_-]{43}',value) else None
    except Exception:return None

def handle(env,start,forward):
    path=env.get('PATH_INFO','')
    if not enabled() or path not in ('/','/public.js','/public.css','/api/public/session','/api/public/chat'):return None
    def result(status,data,cookie=None):
        raw=json.dumps(data,ensure_ascii=False).encode();headers=[('Content-Type','application/json; charset=utf-8'),('Content-Length',str(len(raw))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]
        if cookie:headers.append(('Set-Cookie',COOKIE+'='+cookie+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=1800'))
        start(status,headers);return [raw]
    if path in ('/','/public.js','/public.css'):
        if env.get('REQUEST_METHOD')!='GET':return result('405 Method Not Allowed',{'error':'method'})
        name,mime={'/':('index.html','text/html; charset=utf-8'),'/public.js':('public.js','application/javascript'),'/public.css':('public.css','text/css')}[path]
        body=(ROOT/name).read_bytes()
        csp="default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors https://merlyshoes.com https://www.merlyshoes.com"
        start('200 OK',[('Content-Type',mime),('Content-Length',str(len(body))),('Cache-Control','no-store'),('Content-Security-Policy',csp),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer')]);return [body]
    if len(os.getenv('PILOT_SESSION_SECRET',''))<32 or len(os.getenv('PILOT_ACCESS_KEY',''))<32:return result('503 Service Unavailable',{'error':'unavailable'})
    if path=='/api/public/session':
        if env.get('REQUEST_METHOD')!='GET':return result('405 Method Not Allowed',{'error':'method'})
        token=visitor(env) or secrets.token_urlsafe(32)
        return result('200 OK',{'csrf':csrf(token)},token)
    if env.get('REQUEST_METHOD')!='POST':return result('405 Method Not Allowed',{'error':'method'})
    expected=os.getenv('MERLY_PUBLIC_ORIGIN','https://chat.merlyshoes.com')
    if env.get('HTTP_ORIGIN')!=expected:return result('403 Forbidden',{'error':'origin'})
    token=visitor(env)
    if not token or not hmac.compare_digest(env.get('HTTP_X_MERLY_CSRF','').encode(),csrf(token).encode()):return result('403 Forbidden',{'error':'session'})
    try:
        if env.get('CONTENT_TYPE','').split(';')[0]!='application/json':raise ValueError()
        size=int(env.get('CONTENT_LENGTH','0'))
        if not 0<size<=8192:raise ValueError()
        data=json.loads(env['wsgi.input'].read(size))
        if not isinstance(data,dict) or set(data)!={'message','consent'} or data['consent'] is not True:raise ValueError()
        if not isinstance(data['message'],str) or not 1<=len(data['message'].strip())<=1000:raise ValueError()
    except (ValueError,TypeError,KeyError):return result('400 Bad Request',{'error':'invalid_message_or_consent'})
    if not allow_turn(token):return result('429 Too Many Requests',{'error':'busy'})
    raw=json.dumps({'message':data['message']}).encode()
    internal=dict(env,PATH_INFO='/api/chat',HTTP_AUTHORIZATION='Bearer '+os.environ['PILOT_ACCESS_KEY'],HTTP_COOKIE='merly_hermes_pilot='+token,CONTENT_LENGTH=str(len(raw)))
    internal['wsgi.input']=io.BytesIO(raw)
    captured={}
    def capture(status,headers):captured.update(status=status,headers=headers)
    body=b''.join(forward(internal,capture))
    if not captured['status'].startswith('200'):
        try:trace=json.loads(body).get('diagnostic_id')
        except Exception:trace=None
        error={'error':'busy' if captured['status'].startswith('429') else 'unavailable'}
        if isinstance(trace,str) and re.fullmatch(r'[0-9a-f]{16}',trace):error['diagnostic_id']=trace
        return result(captured['status'],error)
    headers=[(k,v.replace('merly_hermes_pilot=',COOKIE+'=',1) if k.lower()=='set-cookie' else v) for k,v in captured['headers']]
    start(captured['status'],headers);return [body]

# Ephemeral visitor throttle; forwarded gateway keeps persistent global caps.
import threading,time
from collections import OrderedDict,deque
_LOCK=threading.Lock();_RATE=OrderedDict()
def allow_turn(token):
    key=hashlib.sha256(token.encode()).digest();now=time.monotonic()
    with _LOCK:
        bucket=_RATE.setdefault(key,deque());_RATE.move_to_end(key)
        while bucket and now-bucket[0]>=60:bucket.popleft()
        if len(bucket)>=4:return False
        bucket.append(now)
        while len(_RATE)>256:_RATE.popitem(last=False)
        return True
