"""Documented GET-only variant pagination and product option interpretation."""
import re,time
SIZE_NAMES={'size','kich thuoc','co giay','so giay'}
COLOR_NAMES={'mau','mau sac','color','colour'}

def option_value(product,variant,names,norm):
    positions=[];seen=set()
    options=product.get('options')
    if not isinstance(options,list):return None
    for option in options:
        if not isinstance(option,dict):return None
        pos=option.get('position')
        if type(pos) is not int or not 1<=pos<=3 or pos in seen:return None
        seen.add(pos)
        if norm(option.get('name','')).strip() in names:positions.append(pos)
    if len(positions)!=1:return None
    value=variant.get('option'+str(positions[0]))
    return value if isinstance(value,str) and value.strip() and len(value)<=255 else None

def size(product,variant,norm):
    value=option_value(product,variant,SIZE_NAMES,norm)
    if value is None:return None
    match=re.fullmatch(r'(?:size\s*)?(3[5-9]|4[0-3])',norm(value).strip())
    return match.group(1) if match else None

def all_variants(h,product_id,deadline=None):
    """Count+50/page, max100 per documented product. No silent truncation/fallback."""
    if type(product_id) is not int or not 1<=product_id<10**16:raise h.HaravanError('invalid_product_id')
    def get(resource,params):
        if deadline is not None and time.monotonic()>=deadline:raise h.HaravanError('variant_lookup_budget_exceeded')
        return h.get(resource,params)
    root='products/'+str(product_id)+'/variants'
    count=get(root+'/count',{}).get('count')
    if type(count) is not int or not 0<=count<=100:raise h.HaravanError('invalid_variant_count')
    rows=[];seen=set()
    for page in range(1,max(1,(count+49)//50)+1):
        values=get(root,{'limit':50,'page':page}).get('variants')
        if not isinstance(values,list) or len(values)>50:raise h.HaravanError('invalid_variants_page')
        for variant in values:
            if not isinstance(variant,dict):raise h.HaravanError('invalid_variant')
            vid=variant.get('id')
            if type(vid) is not int or not 1<=vid<10**16 or vid in seen or variant.get('product_id')!=product_id:raise h.HaravanError('variant_identity_mismatch')
            seen.add(vid);rows.append(variant)
    if len(rows)!=count:raise h.HaravanError('variant_count_changed_or_incomplete')
    return rows
