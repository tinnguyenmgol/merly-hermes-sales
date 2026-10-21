"""Authenticated pilot. Explicit literal stock scope skips model; free-form uses Hermes."""
import hmac,json,os,time,secrets,logging,re
from pathlib import Path
import hermes_client,state
import explicit_stock,stock_scope_memory,fast_replies,fast_limits,conversation
import public_chat
WEB=Path(__file__).resolve().with_name('pilot-web')
SECURITY=[('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('X-Frame-Options','DENY'),('Permissions-Policy','camera=(), microphone=(), geolocation=()'),('Content-Security-Policy',"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")]
ASSETS={'/operator':('index.html','text/html; charset=utf-8'),'/':('index.html','text/html; charset=utf-8'),'/pilot.js':('pilot.js','application/javascript; charset=utf-8'),'/pilot.css':('pilot.css','text/css; charset=utf-8')}
def application(env,start):
    def result(code,data,cookie=None):
        body=json.dumps(data,ensure_ascii=False).encode();headers=[('Content-Type','application/json; charset=utf-8'),('Content-Length',str(len(body))),('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')]
        if isinstance(data.get('retry_after'),int):headers.append(('Retry-After',str(data['retry_after'])))
        if cookie:headers.append(('Set-Cookie','merly_hermes_pilot='+cookie+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=1800'))
        start(code,headers);return [body]
    public=public_chat.handle(env,start,application)
    if public is not None:return public
    asset=ASSETS.get(env.get('PATH_INFO'))
    if asset and env.get('REQUEST_METHOD')=='GET':
        body=(WEB/asset[0]).read_bytes()
        start('200 OK',[('Content-Type',asset[1]),('Content-Length',str(len(body))),('Cache-Control','no-store'),*SECURITY])
        return [body]
    key=os.getenv('PILOT_ACCESS_KEY','')
    if len(key)<32:return result('503 Service Unavailable',{'error':'pilot_key_not_configured'})
    if not hmac.compare_digest(env.get('HTTP_AUTHORIZATION','').encode(),('Bearer '+key).encode()):return result('401 Unauthorized',{'error':'unauthorized'})
    if env.get('PATH_INFO')=='/health' and env.get('REQUEST_METHOD')=='GET':return result('200 OK',{'hermes_configured':hermes_client.configured(),'pilot_only':True})
    if env.get('PATH_INFO')=='/api/readiness' and env.get('REQUEST_METHOD')=='GET':
        missing=[k for k in ('HERMES_SALES_ISOLATION_APPROVED','HERMES_CUSTOMER_DATA_APPROVED','HERMES_MODEL_COST_APPROVED') if os.getenv(k)!='1']
        if missing:return result('503 Service Unavailable',{'error':'sales_not_approved_or_configured','missing_approvals':missing})
        try:
            hermes_client.audit()
            return result('200 OK',{'ready':True,'model_inference_tested':False,'pilot_only':True})
        except hermes_client.HermesError:
            return result('503 Service Unavailable',{'error':'sales_not_approved_or_configured','ready':False})
        except Exception:return result('503 Service Unavailable',{'error':'pilot_unavailable','ready':False})
    if env.get('PATH_INFO')=='/api/logout' and env.get('REQUEST_METHOD')=='POST':
        try:
            if env.get('HTTP_COOKIE'):
                _,sid=state.identity(env['HTTP_COOKIE']);state.clear(sid);stock_scope_memory.forget(sid);fast_replies.forget(sid);conversation.forget(sid)
        except Exception:return result('503 Service Unavailable',{'error':'pilot_unavailable'})
        body=json.dumps({'status':'logged_out'}).encode()
        start('200 OK',[('Content-Type','application/json'),('Content-Length',str(len(body))),('Cache-Control','no-store'),('Set-Cookie','merly_hermes_pilot=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0'),*SECURITY])
        return [body]
    if env.get('PATH_INFO') not in ('/api/chat','/api/stock-check'):return result('404 Not Found',{'error':'not_found'})
    if env.get('REQUEST_METHOD')!='POST':return result('405 Method Not Allowed',{'error':'post_required'})
    if env.get('CONTENT_TYPE','').split(';')[0]!='application/json':return result('415 Unsupported Media Type',{'error':'json_required'})
    try:
        n=int(env.get('CONTENT_LENGTH','0'))
        if not 0<n<=8192:return result('413 Content Too Large',{'error':'body_limit'})
        data=json.loads(env['wsgi.input'].read(n))
        probe=env.get('PATH_INFO')=='/api/stock-check'
        if probe:
            if not isinstance(data,dict) or set(data)-{'model_code','size','color'} or not {'model_code','size'}<=set(data):raise ValueError()
            if not isinstance(data['model_code'],str) or not 1<=len(data['model_code'])<=32 or type(data['size']) is not int or not 35<=data['size']<=43:raise ValueError()
            if 'color' in data and (not isinstance(data['color'],str) or not 1<=len(data['color'])<=40):raise ValueError()
        elif not isinstance(data,dict) or set(data)!={'message'} or not isinstance(data['message'],str) or not 0<len(data['message'].strip())<=1000:raise ValueError()
    except (ValueError,TypeError):return result('400 Bad Request',{'error':'invalid_message'})
    if not hermes_client.configured():return result('503 Service Unavailable',{'error':'hermes_not_approved_or_configured'})
    turn_started=time.monotonic()
    diagnostic_id=secrets.token_hex(8)
    try:
        token,sid=state.identity(env.get('HTTP_COOKIE'))
        def limited(error,retry=1):
            return result('429 Too Many Requests',{'error':error,'retry_after':retry,'retry_automatically':False})
        with fast_limits.session(sid) as acquired:
            if not acquired:return limited('turn_in_progress')
            cid=state.touch(sid)
            had_context=bool(conversation.get(sid))
            decision=None if probe else conversation.prepare(sid,data['message'])
            if not had_context and cid and decision and decision.get('reason')=='missing_selection':decision={'route':'model'}
            if decision and decision['route']=='clarify':
                return result('200 OK',{'reply':decision['reply'],'engine':'clarification','model_called':False},token)
            if decision and conversation.get(sid).get('reset'):
                stock_scope_memory.forget(sid);fast_replies.forget(sid)
            if not probe:
                quick=fast_replies.policy(data['message'])
                if quick is not None:
                    topic=quick.pop('_topic')
                    fast_replies.remember(sid,{'policy_topic':topic});conversation.policy_turn(sid,topic)
                    return result('200 OK',quick,token)
            scope=data if probe else decision.get('scope') if decision['route']=='stock' else None
            shopping=decision.get('scope') if decision and decision['route']=='catalog' else None
            if probe:conversation.seed(sid,data)
            if scope is not None or shopping is not None:
                with fast_limits.slot('STOCK') as available:
                    if not available:return limited('stock_capacity')
                    rate=state.resource('STOCK')
                    if not rate['available']:return limited('stock_rate_limit',rate['retry_after'])
                    if shopping is not None:
                        answer=hermes_client.discover_products(shopping)
                        stock_scope_memory.forget(sid)
                        fast_replies.remember(sid,{'heel_cm':shopping['heel_cm'],'size':shopping['size']})
                        return result('200 OK',answer,token)
                    stock_scope_memory.remember(sid,scope)
                    direct=hermes_client.probe_stock(scope)
                    if isinstance(direct.get('stock_options'),dict):direct['stock_options']['resolution_path']='direct_haravan'
                    return result('200 OK',direct,token)
            with fast_limits.slot('AI') as available:
                if not available:return limited('ai_capacity')
                reservation=state.reserve_checked(sid)
                if not reservation['available']:return limited(reservation['reason'],reservation['retry_after'])
                try:reply=hermes_client.chat(data['message'],'merly-sales:web:'+sid,cid)
                except Exception:
                    stock_scope_memory.forget(sid);raise
                state.save(sid,reply['conversation_id'])
                body={'reply':reply['reply'],'engine':'hermes'}
                if 'stock_options' in reply:body['stock_options']=reply['stock_options']
                return result('200 OK',body,token)
    except hermes_client.HermesError as exc:
        code=str(exc)
        allowed={'stock_probe_unavailable','hermes_timeout','hermes_unavailable','turn_not_completed','response_limit','invalid_response','invalid_response_id','missing_final_message','invalid_answer','sales_not_approved_or_configured','responses_not_supported','tool_discovery_unavailable','invalid_tool_inventory','unsafe_enabled_toolset','sales_runtime_attestation_required','invalid_sales_endpoint','https_required'}
        if code not in allowed and not re.fullmatch(r'hermes_http_[1-5][0-9]{2}',code):code='unclassified_hermes_error'
        status=getattr(exc,'response_status','not_available')
        if status not in ('failed','cancelled','in_progress','incomplete','queued','unrecognized'):status='not_available'
        logging.getLogger('merly.gateway').error('MERLY_CHAT_FAILED %s',json.dumps({'diagnostic_id':diagnostic_id,'reason_code':code,'response_status':status,'elapsed_ms':round((time.monotonic()-turn_started)*1000)}))
        return result('503 Service Unavailable',{'error':'hermes_unavailable','reason_code':code,'diagnostic_id':diagnostic_id,'retry_automatically':False})
    except Exception:
        logging.getLogger('merly.gateway').error('MERLY_CHAT_FAILED %s',json.dumps({'diagnostic_id':diagnostic_id,'reason_code':'pilot_unavailable','elapsed_ms':round((time.monotonic()-turn_started)*1000)}))
        return result('503 Service Unavailable',{'error':'pilot_unavailable','diagnostic_id':diagnostic_id,'retry_automatically':False})
