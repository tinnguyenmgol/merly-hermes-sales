"""Authenticated pilot gateway. All accepted messages use Hermes, not regex."""
import hmac,json,os,threading
import hermes_client,state
LOCKS=[threading.Lock() for _ in range(128)]
def application(env,start):
    def result(code,data,cookie=None):
        body=json.dumps(data,ensure_ascii=False).encode();headers=[('Content-Type','application/json; charset=utf-8'),('Content-Length',str(len(body))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]
        if cookie:headers.append(('Set-Cookie','merly_hermes_pilot='+cookie+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=1800'))
        start(code,headers);return [body]
    key=os.getenv('PILOT_ACCESS_KEY','')
    if len(key)<32:return result('503 Service Unavailable',{'error':'pilot_key_not_configured'})
    if not hmac.compare_digest(env.get('HTTP_AUTHORIZATION','').encode(),('Bearer '+key).encode()):return result('401 Unauthorized',{'error':'unauthorized'})
    if env.get('PATH_INFO')=='/health' and env.get('REQUEST_METHOD')=='GET':return result('200 OK',{'hermes_configured':hermes_client.configured(),'pilot_only':True})
    if env.get('PATH_INFO')!='/api/chat':return result('404 Not Found',{'error':'not_found'})
    if env.get('REQUEST_METHOD')!='POST':return result('405 Method Not Allowed',{'error':'post_required'})
    if env.get('CONTENT_TYPE','').split(';')[0]!='application/json':return result('415 Unsupported Media Type',{'error':'json_required'})
    try:
        n=int(env.get('CONTENT_LENGTH','0'))
        if not 0<n<=8192:return result('413 Content Too Large',{'error':'body_limit'})
        data=json.loads(env['wsgi.input'].read(n))
        if not isinstance(data,dict) or set(data)!={'message'} or not isinstance(data['message'],str) or not 0<len(data['message'].strip())<=1000:raise ValueError()
    except (ValueError,TypeError):return result('400 Bad Request',{'error':'invalid_message'})
    if not hermes_client.configured():return result('503 Service Unavailable',{'error':'hermes_not_approved_or_configured'})
    try:
        token,sid=state.identity(env.get('HTTP_COOKIE'));lock=LOCKS[int(sid[:8],16)%len(LOCKS)]
        if not lock.acquire(blocking=False):return result('429 Too Many Requests',{'error':'turn_in_progress'})
        try:
            cid=state.reserve(sid)
            if cid is None:return result('429 Too Many Requests',{'error':'pilot_budget_limit'})
            reply=hermes_client.chat(data['message'],'merly-sales:web:'+sid,cid)
            state.save(sid,reply['conversation_id'])
            return result('200 OK',{'reply':reply['reply'],'engine':'hermes'},token)
        finally:lock.release()
    except hermes_client.HermesError:return result('503 Service Unavailable',{'error':'hermes_unavailable','retry_automatically':False})
    except Exception:return result('503 Service Unavailable',{'error':'pilot_unavailable'})
