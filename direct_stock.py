"""Resolve only a failed, explicit stock scope through the fixed read-only API.
One bounded recovery, no new model call; never coerce IDs/size or drop criteria.
"""
import json,logging,time

def scopes(items):
    found={}
    allowed={'model_code','size','color','check_stock','stock_request_id','heel_cm','category','occasion','limit'}
    for item in items:
        if not isinstance(item,dict) or item.get('type')!='function_call' or item.get('name')!='mcp__merly__search_products':continue
        try:a=json.loads(item['arguments']) if isinstance(item.get('arguments'),str) else item['arguments']
        except (ValueError,TypeError,KeyError):continue
        if not isinstance(a,dict) or a.get('check_stock') is not True:continue
        code=a.get('model_code');size=a.get('size');color=a.get('color')
        if not isinstance(code,str) or not 1<=len(code)<=32 or type(size) is not int or not 35<=size<=43:continue
        if color is not None and (not isinstance(color,str) or not 1<=len(color)<=40):continue
        key=(code,size,color);found[key]=None
        if set(a)-allowed or any(a.get(k) is not None for k in ('heel_cm','category','occasion')):continue
        if a.get('limit') is not None and (type(a['limit']) is not int or not 1<=a['limit']<=6):continue
        # Null optional criteria express no criterion here, not a repaired tool call.
        # A non-null business criterion above MUST block narrowing to simple stock.
        found[key]={'model_code':code,'size':size,**({'color':color} if color is not None else {})}
    return found

def recover(report,items,probe,turn_started):
    if not isinstance(report,dict):return report
    candidates=scopes(items);groups=report.get('groups') if report.get('mode')=='groups' else [report]
    for i,group in enumerate(groups):
        if group.get('operation_status') not in ('failed','source_error','catalog_loading','no_match'):continue
        key=(group.get('model_code'),group.get('size'),group.get('color_filter'))
        scope=candidates.get(key)
        if scope is None:continue
        remaining=65-(time.time()-turn_started)
        if remaining<5:return report
        try:
            result=probe(scope,timeout=min(30,remaining))
            fresh=result.get('stock_options')
            if not isinstance(fresh,dict) or fresh.get('mode')!='all_options' or (fresh.get('model_code'),fresh.get('size'),fresh.get('color_filter'))!=key:raise ValueError('direct_scope_mismatch')
            fresh['resolution_path']='direct_haravan';groups[i]=fresh
            logging.getLogger('merly.stock').info('MERLY_STOCK_DIRECT_RECOVERY completed')
        except Exception:
            group['direct_read_failed']=True
            logging.getLogger('merly.stock').warning('MERLY_STOCK_DIRECT_RECOVERY failed')
        break
    if report.get('mode')=='groups':return {**report,'groups':groups}
    return groups[0]
