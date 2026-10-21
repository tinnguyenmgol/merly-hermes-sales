"""One safe structured-query recovery; never parse prose, coerce bad IDs or retry AI."""
import json,re,time,logging,secrets,sqlite3
from conversation import get,valid,norm
FIELDS={'model_code','size','color','heel_cm','category','occasion'}

def resolve(user,items):
    prefix='merly-sales:web:'
    if not isinstance(user,str) or not user.startswith(prefix):return None
    state=get(user[len(prefix):])
    if not state or state.get('pending') or state.get('needs_clarification'):return None
    confirmed={k:v for k,v in state.get('slots',{}).items() if k in state.get('binding',[]) and k in FIELDS and valid(k,v)}
    scopes={}
    for item in items:
        if not isinstance(item,dict) or item.get('type')!='function_call' or item.get('name')!='mcp__merly__search_products':continue
        try:
            a=item.get('arguments',{})
            if isinstance(a,str):a=json.loads(a)
        except (ValueError,TypeError):return None
        if not isinstance(a,dict):return None
        if 'check_stock' in a and type(a['check_stock']) is not bool:return None
        if a.get('check_stock') is not True and not (a.get('check_stock') in (None,False) and state.get('intent')=='find_products' and 'size' in confirmed):continue
        if set(a)-FIELDS-{'check_stock','limit','stock_request_id'}:return None
        if 'limit' in a and (type(a['limit']) is not int or not 1<=a['limit']<=4):return None
        if 'stock_request_id' in a and (not isinstance(a['stock_request_id'],str) or not re.fullmatch(r'[0-9a-f]{32}',a['stock_request_id'])):return None
        scope={k:v for k,v in a.items() if k in FIELDS}
        if any(not valid(k,v) for k,v in scope.items()):return None
        # Authoritative customer fields override a conflicting model proposal.
        scope.update(confirmed)
        for k in state.get('cleared',[]):scope.pop(k,None)
        if 'model_code' in scope and scope['model_code']!=confirmed.get('model_code'):return None
        scopes[json.dumps(scope,sort_keys=True)]=scope
    if len(scopes)!=1:return None
    scope=next(iter(scopes.values()))
    if 'size' not in scope:return {'reply':'Bạn muốn mình tìm size nào, từ 35 đến 43?'}
    if 'size' not in confirmed:return None
    return {'scope':scope}

def known_request(user):
    prefix='merly-sales:web:'
    if not isinstance(user,str) or not user.startswith(prefix):return ''
    state=get(user[len(prefix):]);slots=state.get('slots',{});bound=state.get('binding',[])
    parts=[]
    for k,label in (('model_code','mẫu'),('size','size'),('color','màu'),('heel_cm','gót')):
        if k in bound and k in slots:
            value=slots[k]
            if k=='color':value={'den':'đen','trang':'trắng','trang kem':'trắng kem','nau':'nâu','chi bac':'chì bạc','chi bong':'chì bóng','bac':'bạc','do ruou':'đỏ rượu','hong':'hồng','vang':'vàng'}.get(norm(value),value)
            if k=='heel_cm':value=format(value,'g')
            parts.append(label+' '+str(value)+('cm' if k=='heel_cm' else ''))
    return ', '.join(parts)


def failure_reply(user):
    state=get(user.split('merly-sales:web:',1)[-1])
    if state and 'size' not in state.get('confirmed',[]):return 'Bạn muốn mình tìm size nào, từ 35 đến 43?'
    known=known_request(user)
    return ('Mình đã ghi nhận '+known+'. ' if known else '')+'Lượt này Merly chưa xác minh được kết quả từ hệ thống. Bạn không cần nhập lại các điều kiện đã nói. Bạn có thể [nhắn nhân viên Merly](https://oa.zalo.me/2969822963244380594) để được kiểm tra tiếp; mình chưa kết luận hết hàng.'

def recover(user,items,discover,started):
    plan=resolve(user,items)
    if not plan:return None
    if plan.get('reply'):return {'reply':plan['reply'],'needs_clarification':True}
    if 65-(time.time()-started)<32:return None
    import fast_limits,state
    with fast_limits.slot('STOCK') as available:
        if not available:return None
        try:
            if not state.resource('STOCK')['available']:return None
        except (OSError,ValueError,sqlite3.Error):return None
        reference=secrets.token_hex(8)
        try:
            result=discover(plan['scope'])
            result['stock_options']['resolution_path']='validated-criteria-recovery'
            logging.getLogger('merly.resolution').info('MERLY_RESOLUTION id=%s outcome=completed',reference)
            return result
        except Exception:
            logging.getLogger('merly.resolution').warning('MERLY_RESOLUTION id=%s outcome=source_unavailable',reference)
            return None
