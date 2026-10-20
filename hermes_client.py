"""Hermes Responses API client; NEVER targets owner's default instance."""
import json,os,re,secrets,urllib.request,urllib.error
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
    audit()
    stock_request_id=secrets.token_hex(16)
    payload={'input':message,'instructions':Path(__file__).with_name('SYSTEM-PROMPT.md').read_text(),'stream':False,'store':True}
    payload['instructions']+='\nMã lượt tra tồn hiện tại: '+stock_request_id+'. Khi gọi search_products(check_stock=true), bắt buộc truyền stock_request_id đúng mã này; không dùng mã từ lịch sử. Không hiển thị mã cho khách.'
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
    from stock_report import extract,summary
    report,stock_requested=extract(data.get('output',[]),stock_request_id)
    if stock_requested:text=summary(report)
    result={'reply':text,'conversation_id':rid}
    if report is not None:result['stock_options']=report
    return result
