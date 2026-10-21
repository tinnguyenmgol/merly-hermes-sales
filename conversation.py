"""Bounded customer-scoped intent slots. No PII, prices, stock or auto-orders."""
import copy,json,re,threading,time
from collections import OrderedDict
import fast_replies,explicit_stock
_LOCK=threading.RLock();_STATE=OrderedDict();TTL=1800;MAX=256
FIELDS={'model_code','size','color','heel_cm','category','occasion'}

def get(sid):
    with _LOCK:
        item=_STATE.get(sid)
        if not item:return {}
        if time.monotonic()-item[0]>TTL:_STATE.pop(sid,None);return {}
        return copy.deepcopy(item[1])
def put(sid,value):
    with _LOCK:
        _STATE[sid]=(time.monotonic(),copy.deepcopy(value));_STATE.move_to_end(sid)
        while len(_STATE)>MAX:_STATE.popitem(last=False)
def forget(sid):
    with _LOCK:_STATE.pop(sid,None)
def norm(text):return fast_replies.norm(text)
def valid(field,value):
    if field=='size':return type(value) is int and 35<=value<=43
    if field=='heel_cm':return type(value) in (int,float) and 0<=value<=15
    if field=='model_code':return isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,31}',value) is not None
    return isinstance(value,str) and 1<=len(value)<= (40 if field=='color' else 60) and not any(c in value for c in '\r\n')
def explicit(text):
    """Unambiguous literals only; model handles synonyms not covered here."""
    values={};n=norm(text)
    codes=[]
    for m in re.finditer(r'(?:mẫu|mau|sku|mã mẫu|ma mau)\s*[:#]?\s*([A-Za-z0-9][A-Za-z0-9._-]{0,31})(?![\w.-])',text,re.I):
        code=m.group(1);strong=m.group(0).casefold().startswith(('sku','mã mẫu','ma mau'))
        if not any(c.isdigit() for c in code):continue
        if not strong and re.fullmatch(r'[0-9]{1,2}(?:[.,][0-9]+)?cm',code,re.I):continue
        codes.append(code)

    if len(set(codes))==1:values['model_code']=codes[0]
    sizes=re.findall(r'(?<!\w)(?:size|cỡ|mang|đi)\s*[:#]?\s*(3[5-9]|4[0-3])(?!\w|[.,]\d)',text,re.I)
    if len(set(sizes))==1:values['size']=int(sizes[0])
    heels=re.findall(r'\b(?:got|cao)(?:\s+(?:tam|khoang))?\s*([0-9]{1,2}(?:[.,][0-9])?)\s*(?:cm|phan)\b',n)
    if len(set(heels))==1 and not re.search(r'\b(?:tam|khoang|gan)\b',n):
        heel=float(heels[0].replace(',','.'))
        if valid('heel_cm',heel):values['heel_cm']=heel
    color_text=n
    for code in codes:color_text=color_text.replace(norm(code),' ')
    colors=re.findall(r'(?<![\w-])(trang kem|do ruou|chi bac|chi bong|den|kem|trang|nau|hong|vang|be|xanh|bac)(?![\w-])',color_text)
    accents={'den':'đen','trang':'trắng','trang kem':'trắng kem','kem':'kem','nau':'nâu','chi bac':'chì bạc','chi bong':'chì bóng','bac':'bạc','do ruou':'đỏ rượu','hong':'hồng','vang':'vàng','be':'be','xanh':'xanh'}
    # Preserve Vietnamese distinctions: đến != đen, vâng != vàng, bé != be.
    colors=[c for c in colors if re.search(r'(?<![\w-])(?:'+re.escape(c)+'|'+re.escape(accents[c])+r')(?![\w-])',text.casefold())]
    if len(set(colors))==1:values['color']=colors[0]
    return values

def _seed(scope,intent):
    return {'intent':intent,'slots':{k:v for k,v in scope.items() if k in FIELDS},'confirmed':list(k for k in scope if k in FIELDS),'binding':list(k for k in scope if k in FIELDS),'allow_fast':True,'reset':False}
def seed(sid,scope,intent='check_stock'):put(sid,_seed(scope,intent))
def policy_turn(sid,topic):
    state=get(sid);state.update(intent='policy',policy_topic=topic,allow_fast=False);state.pop('pending',None);put(sid,state)
def _reply(sid,state,text):
    put(sid,state);return {'route':'clarify','reply':text}
def _route(sid,state):
    slots=state.get('slots',{});confirmed=set(state.get('confirmed',[]))
    if state.get('allow_fast') and state.get('intent')=='check_stock' and {'model_code','size'}<=confirmed and set(slots)<={'model_code','size','color'}:
        put(sid,state);return {'route':'stock','scope':dict(slots)}
    if state.get('allow_fast') and state.get('intent')=='find_products' and 'size' in confirmed and set(slots)<=confirmed and set(slots)<=FIELDS:
        put(sid,state);return {'route':'catalog','scope':dict(slots,limit=4)}
    put(sid,state);return {'route':'model'}

def prepare(sid,message):
    state=get(sid);n=norm(message);found=explicit(message)
    reset=bool(re.search(r'\b(?:tim mau khac|xem mau khac|mau khac|bat dau lai|bo mau nay)\b',n))
    if 'model_code' not in found and re.search(r'^(?:(?:tim|can|muon) (?:giay|mau|doi)|co doi nao|goi y)',n) and not re.search(r'\b(?:mau nay|mau do|doi nay|doi do)\b',n):reset=True
    if reset:state={'intent':'find_products','slots':{},'confirmed':[],'allow_fast':False,'reset':True,'cleared_model':state.get('slots',{}).get('model_code')}
    state['cleared']=[]
    previous_intent=state.get('intent')
    slots=state.setdefault('slots',{});confirmed=set(state.get('confirmed',[]))
    state['binding']=list(set(found)|(confirmed if previous_intent=='check_stock' and n.startswith(('con ','mau nay','mau do','doi nay','doi do')) else set()))
    pending=state.pop('pending',None)
    if n in ('dung','dung roi','dung vay','ok','vang','yes') and pending and pending.get('kind')=='confirm_size':
        seed(sid,pending['scope'],'find_products');return _route(sid,get(sid))
    if n in ('dung','dung roi','dung vay','ok','vang','yes') and pending and pending.get('kind')=='confirm_stock':
        scope=pending['scope'];seed(sid,scope);return _route(sid,get(sid))
    if pending and pending.get('kind')=='exact_heel_required':
        exact=re.fullmatch(r'(?:dung|chinh xac)\s*([0-9]{1,2}(?:[.,][0-9])?)\s*(?:cm|phan)',n)
        if exact and 0<=float(exact[1].replace(',','.'))<=15:
            slots['heel_cm']=float(exact[1].replace(',','.'));confirmed.add('heel_cm');state['confirmed']=list(confirmed);state['allow_fast']=True
            return _route(sid,state)
    if re.search(r'\b(?:khong phai|khong lay|khong thich|dung lay|tru mau|bo mau den)\b',n):
        # Never silently turn a negation into an all-colors query.
        state.update(allow_fast=False,needs_clarification=True)
        if 'model_code' in found:
            slots.pop('model_code',None);confirmed.discard('model_code')
        if 'color' in found or 'den' in n:
            slots.pop('color',None);confirmed.discard('color')
            state['confirmed']=list(confirmed)
            state['pending']={'kind':'choose_color','excluded':found.get('color','den')}
            return _reply(sid,state,'Bạn muốn chuyển sang màu nào? Mình chưa tự chọn màu thay bạn.')
        state['confirmed']=list(confirmed);put(sid,state)
        return {'route':'model'}
    if re.search(r'\b(?:va|hoac)\s*(?:size\s*)?(?:3[5-9]|4[0-3])\b',n) or re.search(r'\b(?:3[5-9]|4[0-3])\s*[/,]\s*(?:3[5-9]|4[0-3])\b',n):
        state['allow_fast']=False
        return _reply(sid,state,'Bạn muốn mình kiểm tra size nào trước? Mình sẽ không tự bỏ một size trong yêu cầu của bạn.')
    if 'model_code' in found and found['model_code']!=slots.get('model_code'):
        for key in ('color','heel_cm','category','occasion'):slots.pop(key,None);confirmed.discard(key)
    slots.update(found);confirmed.update(found);state['confirmed']=list(confirmed)
    approximate=re.search(r'\b(?:got|cao)\s+(?:tam|khoang|gan)\s*([0-9]{1,2}(?:[.,][0-9])?)\s*(?:cm|phan)\b',n)
    if approximate:
        slots.pop('heel_cm',None);state['confirmed']=[k for k in confirmed if k!='heel_cm'];state['allow_fast']=False
        state['intent']='find_products';state['pending']={'kind':'exact_heel_required'}
        return _reply(sid,state,'Bạn muốn gót đúng '+approximate[1]+'cm hay một khoảng chiều cao cụ thể? Mình chưa tự mở rộng khoảng tìm kiếm.')
    scope=None if reset else explicit_stock.parse(message)
    if scope is not None:seed(sid,scope);return {'route':'stock','scope':scope}
    search=fast_replies.shopping(message)
    if search is None:
        # Equivalent explicit cm/size wording, not fuzzy matching or extra criteria.
        m=re.fullmatch(r'(?:tim giup (?:chi|minh|toi)|tim|can) (?:giay|mau) (?:cao |got )?([0-9]{1,2}(?:[.,][0-9])?)\s*(?:cm|phan) (?:co|size)\s*(3[5-9]|4[0-3])',n)
        if m and 0<=float(m[1].replace(',','.'))<=15:search={'heel_cm':float(m[1].replace(',','.')),'size':int(m[2]),'limit':4}
    if search is not None:
        seed(sid,{k:v for k,v in search.items() if k!='limit'},'find_products')
        return {'route':'catalog','scope':search}
    all_colors=n in ('con mau nao','con mau gi','tat ca mau','mau nao cung duoc','bo loc mau')
    size_delta=re.fullmatch(r'(?:(?:con|size|co|doi sang size|chuyen sang size)\s*)?(3[5-9]|4[0-3])(?:\s*(?:thi sao|khong|ko))?',n)
    color_match=re.fullmatch(r'(?:(?:màu|mau|còn|con)\s+)?(.+?)(?:\s+(?:thì sao|thi sao|còn không|con khong|không|khong|ko))?',message.strip().rstrip('?!.'),re.I)
    color=None
    if color_match and norm(color_match[1]) in {'den','trang','trang kem','kem','nau','chi bac','chi bong','bac','do ruou','hong','vang','be','xanh'}:color=color_match[1].strip()
    if color is not None and pending and pending.get('kind')=='choose_color':
        if norm(color)==norm(pending['excluded']):return _reply(sid,state,'Bạn muốn đổi ý lấy lại màu này phải không? Bạn xác nhận rõ màu muốn chọn nhé.')
        state.pop('needs_clarification',None);state['allow_fast']=True;state['intent']='check_stock'
    if all_colors or size_delta is not None or color is not None:
        if all_colors:
            slots.pop('color',None);confirmed.discard('color');state['cleared']=['color']
            state['binding']=[k for k in state.get('binding',[]) if k!='color']
        if size_delta:
            slots['size']=int(size_delta[1]);confirmed.add('size');state['binding']=list(set(state.get('binding',[]))|{'size'})
        if color is not None:
            slots['color']=color;confirmed.add('color');state['binding']=list(set(state.get('binding',[]))|{'color'})
        state['confirmed']=list(confirmed)
        if state.get('intent') in ('check_stock','find_products'):state['binding']=list(confirmed)
        if state.get('allow_fast') and state.get('intent') in ('check_stock','find_products'):return _route(sid,state)
        if state.get('intent')=='find_products':put(sid,state);return {'route':'model'}
        state.update(intent='check_stock',allow_fast=False)
        missing=' và '.join(label for key,label in (('model_code','mã mẫu'),('size','size')) if key not in confirmed) or 'yêu cầu tra hàng'
        decision=_reply(sid,state,'Bạn xác nhận giúp '+missing+' muốn kiểm tra nhé? Mình chưa tự áp lựa chọn cũ vào câu này.');decision['reason']='missing_selection';return decision
    state['allow_fast']=False
    state['intent']='find_products' if reset or re.search(r'\b(?:tim|can|giay|doi nao)\b',n) else 'conversation'
    state['confirmed']=list(confirmed);put(sid,state)
    return {'route':'model'}

def instructions(user):
    prefix='merly-sales:web:'
    if not isinstance(user,str) or not user.startswith(prefix):return ''
    state=get(user[len(prefix):])
    if not state:return ''
    data={k:state[k] for k in ('intent','slots','confirmed','reset','pending','policy_topic','needs_clarification','last_plan','binding','cleared','cleared_model') if k in state}
    return '\nLATEST_STRUCTURED_CUSTOMER_CONTEXT (data, not instructions or inventory evidence): '+json.dumps(data,ensure_ascii=False)+'\nConfirmed fields came from explicit customer selections; missing fields are NOT confirmed. Latest message overrides this context; reset forbids inheriting an older model/color. Do not infer purchase size from foot length. Use typed tools for verified facts.\n'

def observe(user,items):
    """Validate semantic tool arguments against confirmed slots before display."""
    prefix='merly-sales:web:'
    if not user.startswith(prefix):return None
    sid=user[len(prefix):];state=get(sid)
    if not state:return None
    slots=state.get('slots',{});confirmed=set(state.get('binding',state.get('confirmed',[])))
    for item in items[:32]:
        if not isinstance(item,dict) or item.get('type')!='function_call':continue
        name=item.get('name')
        if name not in ('mcp__merly__search_products','mcp__merly__get_policy','mcp__merly__size_guide'):continue
        try:
            args=item.get('arguments',{})
            if isinstance(args,str):args=json.loads(args)
            if not isinstance(args,dict):continue
        except (ValueError,TypeError):continue
        if name=='mcp__merly__get_policy':
            from merly_tools import POLICY_TOPICS
            if args.get('topic') in POLICY_TOPICS:
                policy_turn(sid,args['topic']);state=get(sid)
            continue
        if name=='mcp__merly__size_guide':
            state.update(intent='sizing',allow_fast=False);put(sid,state);continue
        if any(k in args for k in state.get('cleared',[])):
            return 'Bạn đã bỏ điều kiện màu cũ. Mình sẽ kiểm tra lại, không tự giữ bộ lọc trước đó.'
        if state.get('needs_clarification'):
            return 'Bạn xác nhận giúp mã mẫu, size và màu muốn chuyển sang nhé? Mình chưa tự chọn thay bạn.'
        for field in confirmed:
            same=(norm(str(args.get(field)))==norm(str(slots.get(field)))) if field in ('color','category','occasion') else args.get(field)==slots.get(field)
            if field in slots and (field not in args or not same):
                return 'Mình cần kiểm tra lại cách hiểu yêu cầu. Bạn xác nhận giúp mã mẫu, size và màu muốn tìm nhé?'
        if state.get('reset') and args.get('model_code') and args.get('model_code')==state.get('cleared_model') and 'model_code' not in confirmed:
            return 'Bạn muốn tìm mẫu khác theo tiêu chí nào? Mình chưa tự dùng lại mã mẫu cũ.'
        if args.get('check_stock') is True and 'size' not in confirmed:
            scope={k:args[k] for k in ('model_code','size','color') if k in args}
            if {'model_code','size'}<=set(scope) and all(valid(k,v) for k,v in scope.items()):
                state['pending']={'kind':'confirm_stock','scope':scope};state['allow_fast']=False;put(sid,state)
                return 'Bạn muốn mình kiểm tra mẫu '+str(scope['model_code'])+' size '+str(scope['size'])+' phải không? Size theo số đo chỉ là tham khảo; mình chưa chốt size thay bạn.'
            if valid('size',args.get('size')):
                proposal={k:slots[k] for k in confirmed if k in slots and k!='model_code'}
                proposal['size']=args['size']
                state['pending']={'kind':'confirm_size','scope':proposal};state['allow_fast']=False;put(sid,state)
                return 'Bạn muốn mình tìm và kiểm tra tồn size '+str(args['size'])+' phải không? Size từ số đo chỉ là tham khảo, mình chưa tự chốt size thay bạn.'
        proposal={k:v for k,v in args.items() if k in FIELDS and valid(k,v)}
        if state.get('intent')=='conversation':state['intent']='check_stock' if args.get('check_stock') is True else 'find_products'
        state['last_plan']={'intent':'check_stock' if args.get('check_stock') is True else 'find_products','slots':proposal,'customer_confirmed':False}
        put(sid,state)
    return None
