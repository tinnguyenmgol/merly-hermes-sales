"""Hermes Responses API client; NEVER targets owner's default instance."""
import json,os,re,secrets,time,urllib.request,urllib.error
from pathlib import Path
from urllib.parse import urlsplit
class HermesError(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None
EXPECTED={'mcp__merly__'+name for name in ('search_products','quote_variant','size_guide','get_policy','get_promotions')}

def configured():
    return all(os.getenv(k)=='1' for k in ('HERMES_SALES_ISOLATION_APPROVED','HERMES_CUSTOMER_DATA_APPROVED','HERMES_MODEL_COST_APPROVED')) and bool(os.getenv('HERMES_SALES_API_BASE')) and bool(os.getenv('HERMES_SALES_API_KEY'))

def endpoint():
    base=os.environ.get('HERMES_SALES_API_BASE','').rstrip('/');u=urlsplit(base)
    if not u.hostname or u.username or u.password or u.query or u.fragment or not u.path.endswith('/v1') or '/p/default/' in u.path:raise HermesError('invalid_sales_endpoint')
    if u.scheme!='https' and not (u.scheme=='http' and os.getenv('HERMES_ALLOW_HTTP')=='1'):raise HermesError('https_required')
    return base

def request(path,payload=None):
    base=endpoint();headers={'Authorization':'Bearer '+os.environ['HERMES_SALES_API_KEY'],'Accept':'application/json'}
    data=None
    if payload is not None:
        payload=dict(payload);scope=payload.pop('_session_scope',None)
        if scope:headers['X-Hermes-Session-Key']=scope
        data=json.dumps(payload,ensure_ascii=False).encode();headers['Content-Type']='application/json'
    req=urllib.request.Request(base+path,data=data,headers=headers,method='POST' if data else 'GET')
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=45 if data else 8) as r:raw=r.read(262145)
        if len(raw)>262144:raise HermesError('response_limit')
        value=json.loads(raw)
        if not isinstance(value,dict):raise HermesError('invalid_response')
        return value
    except urllib.error.HTTPError as e:raise HermesError('hermes_http_'+str(e.code)) from None
    except TimeoutError:raise HermesError('hermes_timeout') from None
    except urllib.error.URLError as e:
        raise HermesError('hermes_timeout' if isinstance(e.reason,TimeoutError) else 'hermes_unavailable') from None
    except OSError:raise HermesError('hermes_unavailable') from None
    except (ValueError,TypeError):raise HermesError('invalid_response') from None

def audit():
    """Discovery is supplementary; dedicated-instance rights also need verification."""
    if not configured():raise HermesError('sales_not_approved_or_configured')
    cap=request('/capabilities')
    if cap.get('platform')!='hermes-agent' or cap.get('features',{}).get('responses_api') is not True:raise HermesError('responses_not_supported')
    rows=request('/toolsets').get('data')
    if not isinstance(rows,list):raise HermesError('tool_discovery_unavailable')
    # Hermes inventory can omit MCP rows. Startup audit verifies actual schemas.
    for row in rows:
        if not isinstance(row,dict):raise HermesError('invalid_tool_inventory')
        if row.get('enabled') is True and (row.get('name')!='merly' or not set(row.get('tools',[]))<=EXPECTED):raise HermesError('unsafe_enabled_toolset')
    from safety import verify_attestation,AuditError
    try:verify_attestation(endpoint(),os.environ['HERMES_SALES_API_KEY'])
    except AuditError:raise HermesError('sales_runtime_attestation_required') from None
    return True

def chat(message,user,previous_response_id=''):
    turn_started=time.time()
    audit()
    stock_request_id=secrets.token_hex(16)
    payload={'input':message,'instructions':Path(__file__).with_name('SYSTEM-PROMPT.md').read_text(),'stream':False,'store':True}

    import stock_scope_memory,fast_replies,conversation
    structured=conversation.instructions(user)
    if structured:payload['instructions']+=structured
    else:
        payload['instructions']+=stock_scope_memory.instructions(user)
        payload['instructions']+=fast_replies.instructions(user)
    model=os.getenv('HERMES_SALES_MODEL_ALIAS','')
    if model:payload['model']=model
    if previous_response_id:payload['previous_response_id']=previous_response_id
    payload['_session_scope']=user
    data=request('/responses',payload)
    if data.get('status')!='completed':
        exc=HermesError('turn_not_completed')
        exc.response_status=data.get('status') if data.get('status') in ('failed','cancelled','in_progress','incomplete','queued') else 'unrecognized'
        raise exc
    rid=data.get('id')
    if not isinstance(rid,str) or not re.fullmatch(r'resp_[A-Za-z0-9_-]{1,120}',rid):raise HermesError('invalid_response_id')
    final=[item for item in data.get('output',[]) if isinstance(item,dict) and item.get('type')=='message' and item.get('role','assistant')=='assistant' and item.get('phase')!='commentary']
    if not final:raise HermesError('missing_final_message')
    text=''.join(part.get('text','') for part in final[-1].get('content',[]) if isinstance(part,dict) and part.get('type')=='output_text' and isinstance(part.get('text'),str))
    if not text.strip() or len(text)>12000:raise HermesError('invalid_answer')
    clarification=conversation.observe(user,data.get('output',[]))
    if clarification is not None:return {'reply':clarification,'conversation_id':rid,'needs_clarification':True}
    from stock_report import extract,summary
    report,stock_requested=extract(data.get('output',[]),stock_request_id,turn_started=turn_started)
    stock_scope_memory.after_model_turn(user,data.get('output',[]))
    if stock_requested:
        from direct_stock import recover
        report=recover(report,data.get('output',[]),probe_stock,turn_started)
        text=summary(report)
    result={'reply':text,'conversation_id':rid}
    if report is not None:result['stock_options']=report
    return result

def probe_stock(scope,timeout=30):
    """Compose-only private endpoint, authenticated; no inference request."""
    if not configured():raise HermesError('sales_not_approved_or_configured')
    started=time.time()
    req=urllib.request.Request('http://hermes-sales:8644/stock',data=json.dumps(scope).encode(),headers={'Authorization':'Bearer '+os.environ['HERMES_SALES_API_KEY'],'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=timeout) as r:raw=r.read(262145)
        if len(raw)>262144:raise HermesError('response_limit')
        body=json.loads(raw)
        from stock_report import validate,summary,classify
        report=validate(body['stock_report'],None,scope,turn_started=started)
        classify(report)
        return {'reply':summary(report),'stock_options':report,'engine':'haravan-readonly','model_called':False}
    except HermesError:raise
    except Exception:raise HermesError('stock_probe_unavailable') from None


def search_catalog(scope):
    """Fixed authenticated catalog-only endpoint; never an inference call."""
    if not configured():raise HermesError('sales_not_approved_or_configured')
    req=urllib.request.Request('http://hermes-sales:8644/catalog-search',data=json.dumps(scope).encode(),headers={'Authorization':'Bearer '+os.environ['HERMES_SALES_API_KEY'],'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=8) as r:raw=r.read(262145)
        if len(raw)>262144:raise ValueError()
        data=json.loads(raw)
        if not isinstance(data,dict) or data.get('status') not in ('ok','partial_metadata','catalog_loading') or not isinstance(data.get('products'),list):raise ValueError()
        rows=data['products'][:4]
        if rows:reply='Các mẫu có thuộc tính phù hợp ở dưới; có biến thể size này chưa có nghĩa còn hàng. Bạn chọn mã mẫu để Merly kiểm tra tồn mới.'
        elif data['status']=='catalog_loading':reply='Danh mục đang cập nhật. Bạn gửi mã mẫu để Merly kiểm tra trực tiếp; chưa thể kết luận hết hàng.'
        elif data['status']=='partial_metadata':reply='Merly chưa đủ dữ liệu đã xác minh về chiều cao gót để chọn đúng mẫu theo yêu cầu này. Bạn gửi mã mẫu hoặc ảnh mẫu muốn tìm nhé; đây không phải kết luận hết hàng.'
        else:reply='Chưa tìm thấy mẫu khớp trong danh mục đã kiểm tra. Đây không phải kết luận hết hàng; bạn có mã mẫu muốn Merly tra giúp không?'
        return {'reply':reply,'products':rows,'engine':'catalog-readonly','model_called':False,'stock_checked':False}
    except HermesError:raise
    except Exception:raise HermesError('stock_probe_unavailable') from None


def discover_products(scope):
    """Execute structured product criteria -> live inventory; no model call."""
    if not configured():raise HermesError('sales_not_approved_or_configured')
    started=time.time()
    req=urllib.request.Request('http://hermes-sales:8644/discover',data=json.dumps(scope).encode(),headers={'Authorization':'Bearer '+os.environ['HERMES_SALES_API_KEY'],'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=30) as r:raw=r.read(262145)
        if len(raw)>262144:raise ValueError()
        from stock_report import summary
        import product_discovery
        report=product_discovery.validate(json.loads(raw)['stock_report'],scope,started)
        return {'reply':summary(report),'stock_options':report,'engine':'criteria-live-inventory','model_called':False}
    except HermesError:raise
    except Exception:raise HermesError('stock_probe_unavailable') from None
