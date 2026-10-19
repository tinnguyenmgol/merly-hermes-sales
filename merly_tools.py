"""Typed read-only tools. No routing of natural-language customer messages."""
import json,math,re,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
import catalog,haravan_client as h,promotions
ROOT=Path(__file__).parent
LOCATIONS={80371:'876 Trường Sa',80441:'561 Lũy Bán Bích',977854:'Tổng Kho'}
class Invalid(ValueError):pass

def validate(data,fields):
    if not isinstance(data,dict) or set(data)-set(fields):raise Invalid('unknown_fields')
    for key,value in data.items():
        kind,low,high=fields[key]
        if type(value) is not kind or (kind is str and not low<=len(value)<=high) or (kind in (int,float) and (not math.isfinite(value) or not low<=value<=high)):raise Invalid('invalid_'+key)

def image(p):
    images=p.get('images');item=p.get('image')
    if not isinstance(item,dict):item=images[0] if isinstance(images,list) and images else {}
    value=item.get('src') if isinstance(item,dict) else None
    if not isinstance(value,str):return None
    try:
        u=urlsplit(value)
        if u.scheme=='https' and u.hostname in ('product.hstatic.net','file.hstatic.net','cdn.hstatic.net','theme.hstatic.net') and not u.username and not u.password and u.port in (None,443):return value
    except ValueError:pass
    return None

def product_url(p):
    handle=p.get('handle')
    return 'https://merlyshoes.com/products/'+handle if p.get('published_at') and isinstance(handle,str) and re.fullmatch(r'[A-Za-z0-9_-]+',handle) else None

def enrichment():
    data=json.loads((ROOT/'catalog-enrichment.json').read_text())
    return data.get('products',{}) if data.get('approved') is True else {}

def variant_color(product,variant):
    values=[]
    for option in product.get('options',[]):
        if isinstance(option,dict) and catalog.norm(option.get('name','')) in ('mau','mau sac','color','colour'):
            value=variant.get('option'+str(option.get('position')))
            if isinstance(value,str) and value.strip():values.append(value)
    return ' / '.join(values) if values else None

def matches_model(product,code):
    return bool(re.search(r'(?<!\w)'+re.escape(catalog.norm(code))+r'(?!\w)',catalog.norm(product.get('title',''))) or any(catalog.norm(v.get('sku',''))==catalog.norm(code) for v in product['variants']))

def variant_price(variant):
    try:
        value=promotions.number(variant.get('price'))
        return int(value) if value>=0 and value==value.to_integral_value() else None
    except (ValueError,TypeError):return None

def search_products(data):
    validate(data,{'model_code':(str,1,32),'color':(str,1,40),'size':(int,35,43),'heel_cm':(float,0,15),'category':(str,1,60),'occasion':(str,1,60),'limit':(int,1,6),'check_stock':(bool,0,0),'stock_request_id':(str,32,32)})
    if data.get('check_stock'):
        if not {'model_code','size','stock_request_id'}<=set(data) or not re.fullmatch(r'[0-9a-f]{32}',data['stock_request_id']):raise Invalid('stock_scope_required')
        if any(k in data for k in ('heel_cm','category','occasion')):raise Invalid('verify_specs_before_stock_scope')
        import stock_options
        return stock_options.lookup(data,sys.modules[__name__])
    rows=catalog.snapshot()
    if rows is None:return {'status':'catalog_loading','retryable':True,'products':[]}
    metadata=enrichment();results=[];unknown=0
    for p in rows:
        if not catalog.eligible(p):continue
        code=data.get('model_code')
        if code and not (re.search(r'(?<!\w)'+re.escape(catalog.norm(code))+r'(?!\w)',catalog.norm(p.get('title',''))) or any(catalog.norm(v.get('sku',''))==catalog.norm(code) for v in p['variants'])):continue
        meta=metadata.get(str(p['id']),{})
        failed=False
        for field in ('heel_cm','category','occasion'):
            if field not in data:continue
            actual=meta.get(field)
            if actual is None:unknown+=1;failed=True;break
            if field=='heel_cm':match=type(actual) in (int,float) and actual==data[field]
            else:match=isinstance(actual,str) and catalog.norm(actual)==catalog.norm(data[field])
            if not match:failed=True;break
        if failed:continue
        variants=[]
        for v in p['variants']:
            size=catalog.size(v);color=variant_color(p,v)
            if 'size' in data and str(data['size'])!=size:continue
            if 'color' in data and (color is None or catalog.norm(data['color']) not in catalog.norm(color)):continue
            variants.append({'variant_id':v['id'],'size':size,'color':color})
        if variants:
            results.append({'product_id':p['id'],'title':p.get('title',''),'image_url':image(p),'product_url':product_url(p),'variants':variants[:12],'variants_total':len(variants),'variants_truncated':len(variants)>12,'verified_specs':{k:meta[k] for k in ('heel_cm','category','occasion') if k in meta},'availability':'not_checked'})
    return {'status':'partial_metadata' if unknown else 'ok','products':results[:data.get('limit',4)],'unknown_spec_products':unknown,'stock_checked':False,'matched_products':len(results),'products_truncated':len(results)>data.get('limit',4),'note':'No price/stock claim until quote_variant; missing metadata is not no stock.'}

def quote_variant(data):
    validate(data,{'product_id':(int,1,10**16-1),'variant_id':(int,1,10**16-1),'quantity':(int,1,20)})
    if not {'product_id','variant_id'}<=set(data):raise Invalid('required_ids')
    p=h.get('products/'+str(data['product_id']),{}).get('product')
    if not isinstance(p,dict) or p.get('id')!=data['product_id'] or not catalog.eligible(p):return {'status':'product_unavailable'}
    variants=[v for v in p['variants'] if v.get('id')==data['variant_id']]
    if len(variants)!=1:return {'status':'variant_mismatch'}
    v=variants[0];quantity=data.get('quantity',1)
    rows=h.inventory(str(v['id']),','.join(map(str,LOCATIONS)))
    counts={}
    for row in rows:
        loc=row['loc_id'];qty=row['qty_available']
        if loc not in LOCATIONS or loc in counts or type(qty) not in (int,float) or not math.isfinite(qty) or int(qty)!=qty:raise h.HaravanError('invalid_inventory')
        counts[loc]=max(0,int(qty))
    total=sum(counts.values());complete=set(counts)==set(LOCATIONS)
    available=True if total>=quantity else False if complete else None
    try:
        price=promotions.number(v.get('price'))
        price=int(price) if price==price.to_integral_value() else None
    except ValueError:price=None
    return {'status':'ok' if complete else 'partial_inventory','product_id':p['id'],'variant_id':v['id'],'title':p.get('title',''),'size':catalog.size(v),'color':variant_color(p,v),'price_vnd':price,'quantity':quantity,'subtotal_vnd':price*quantity if price is not None else None,'available':available,'known_available':total,'inventory_complete':complete,'locations':[{'name':name,'available':counts.get(loc)} for loc,name in LOCATIONS.items()],'checked_at':datetime.now(timezone.utc).isoformat(),'product_url':product_url(p),'image_url':image(p),'reserved':False,'discounts_applied':False}

def size_guide(data):
    validate(data,{'size':(int,35,43),'length_cm':(float,15,35),'girth_cm':(float,10,40)})
    k=json.loads((ROOT/'vendor/knowledge-public-draft.json').read_text()).get('sizing',{})
    if k.get('approved') is not True:return {'status':'unverified'}
    rows=k['rows']
    if 'size' in data:rows=[r for r in rows if r['size']==data['size']]
    if 'length_cm' in data:rows=[r for r in rows if r['length_cm']==data['length_cm']]
    return {'status':'reference_only' if rows else 'needs_staff_review','chart':rows,'source':k['source_url'],'girth_provided':data.get('girth_cm'),'fit_confirmed':False,'note':'Exact reference points only. Do not round or infer fit; ask for model and foot circumference.'}

def get_policy(data):
    validate(data,{'topic':(str,1,40)})
    if data.get('topic') not in ('shipping','size_exchange','warranty','store_hours','store_address'):raise Invalid('unknown_topic')
    k=json.loads((ROOT/'vendor/knowledge-public-draft.json').read_text())
    if k.get('approved') is not True:return {'status':'unverified','topic':data['topic']}
    return {'status':'approved','topic':data['topic'],'text':k.get(data['topic']),'sources':k.get('sources',[])}

def get_promotions(data):
    validate(data,{})
    pairs=promotions.config()
    if not pairs:return {'status':'publication_not_configured','offers':[],'shop_has_no_offers':False}
    rows=promotions.load(pairs);now=datetime.now(timezone.utc)
    items=[promotions.summary(row,resource,identity,now) for resource,identity,row in rows]
    return {'status':'reference_only','offers':[item for item in items if item],'eligibility_confirmed':False,'stacking_confirmed':False}

TOOLS={f.__name__:f for f in [search_products,quote_variant,size_guide,get_policy,get_promotions]}
def dispatch(name,data):
    if name not in TOOLS:raise Invalid('unknown_tool')
    if isinstance(data,dict):
        data=dict(data)
        for field in ('heel_cm','length_cm','girth_cm'):
            if type(data.get(field)) is int:data[field]=float(data[field])
    return TOOLS[name](data)
