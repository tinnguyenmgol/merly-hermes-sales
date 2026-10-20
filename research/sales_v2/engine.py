"""OFFLINE LAB ONLY; not wired to gateway, Docker or MCP.
Model supplies business scope, not freshness/provenance secrets. Reuse the stock
reader/validator unchanged to isolate orchestration from inventory semantics.
"""
import json,secrets
import stock_report
FIELDS={'model_code':(str,1,32),'size':(int,35,43),'color':(str,1,40)}
def scope_key(scope):return scope.get('model_code'),scope.get('size'),scope.get('color')

def execute(scope,tools):
    operation=secrets.token_hex(16)
    result={'contract':'merly-stock-evidence-lab-v2','operation_id':operation,'scope':{},'outcome':'input_error','data':None,'reason':'invalid_scope'}
    try:
        tools.validate(scope,FIELDS)
        if not {'model_code','size'}<=set(scope):raise tools.Invalid('missing_model_or_size')
    except tools.Invalid as exc:
        known={'unknown_fields','missing_model_or_size'}|{'invalid_'+k for k in FIELDS}
        result['reason']=str(exc) if str(exc) in known else 'invalid_scope'
        return result
    result['scope']=dict(scope)
    # Application creates correlation metadata; no nonce is copied by the model.
    try:
        raw=tools.dispatch('search_products',{**scope,'check_stock':True,'stock_request_id':operation})['stock_report']
        data=stock_report.validate(raw,operation,scope)
    except (stock_report.InvalidReport,KeyError,TypeError,ValueError):
        result.update(outcome='contract_error',reason='invalid_source_contract');return result
    except tools.h.HaravanError:
        result.update(outcome='source_error',reason='source_unavailable');return result
    result.update(outcome='complete' if data['complete'] else 'partial',reason=raw.get('status','unknown'),data=data,checked_at=raw.get('checked_at'))
    return result

def decode(value):
    for _ in range(8):
        if isinstance(value,str):
            if len(value)>220000:raise ValueError('oversize')
            value=json.loads(value);continue
        if isinstance(value,list) and len(value)==1 and isinstance(value[0],dict):value=value[0].get('text');continue
        if isinstance(value,dict):
            if 'stock_evidence' in value:return value['stock_evidence']
            if 'structuredContent' in value:value=value['structuredContent'];continue
            if 'result' in value:value=value['result'];continue
        raise ValueError('unsupported_envelope')
    raise ValueError('too_deep')

def collect(items):
    """LAB collector assumes execute() produced events; NOT deployable validation.
    Consume only current-turn tool messages, never user/assistant prose.
    """
    calls={};groups={}
    for item in items:
        cid=item.get('call_id')
        if not isinstance(cid,str):continue
        if item.get('type')=='function_call' and item.get('name')=='mcp__merly__search_products':
            try:args=json.loads(item['arguments']) if isinstance(item['arguments'],str) else item['arguments']
            except (ValueError,TypeError,KeyError):continue
            if not isinstance(args,dict) or args.get('check_stock') is not True:continue
            scope={k:v for k,v in args.items() if k!='check_stock'}
            if set(scope)-set(FIELDS):continue
            if not isinstance(scope.get('model_code'),str) or type(scope.get('size')) is not int:continue
            if 'color' in scope and not isinstance(scope['color'],str):continue
            calls[cid]=scope
            groups.setdefault(scope_key(scope),{'scope':scope,'evidence':None,'failures':[]})
        elif item.get('type')=='function_call_output' and cid in calls:
            group=groups[scope_key(calls[cid])]
            try:
                event=decode(item.get('output'))
                if event.get('contract')!='merly-stock-evidence-lab-v2' or event.get('scope')!=calls[cid]:raise ValueError('scope_mismatch')
                if event.get('outcome') not in ('complete','partial') or not isinstance(event.get('data'),dict):raise ValueError('lookup_failed')
                group['evidence']=event;group['recheck_failed']=False
            except (ValueError,KeyError,TypeError,AttributeError):
                group['failures'].append({'call_id':cid,'reason':'lookup_failed_or_invalid_contract'})
                group['recheck_failed']=True
    # Retain earlier evidence on retry failure, explicitly not a fresh success.
    return list(groups.values())
