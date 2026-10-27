"""Typed read-only tools. No routing of natural-language customer messages."""
import json,math,re,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
import catalog,haravan_client as h,promotions
import haravan_variants,catalog_query
from media_urls import picture
ROOT=Path(__file__).parent
LOCATIONS={80371:'876 Trường Sa',80441:'561 Lũy Bán Bích',977854:'Tổng Kho'}
class Invalid(ValueError):pass

def validate(data,fields):
    if not isinstance(data,dict) or set(data)-set(fields):raise Invalid('unknown_fields')
    for key,value in data.items():
        kind,low,high=fields[key]
        number_type=type(value) in (int,float) if kind is float else type(value) is kind
        if not number_type or (kind is str and not low<=len(value)<=high) or (kind in (int,float) and (not low<=value<=high or not math.isfinite(value))):raise Invalid('invalid_'+key)

def image(p):
    return picture(p)['image_url']

def product_url(p):
    handle=p.get('handle')
    return 'https://merlyshoes.com/products/'+handle if p.get('published_at') and isinstance(handle,str) and re.fullmatch(r'[A-Za-z0-9_-]+',handle) else None

def enrichment():
    data=json.loads((ROOT/'catalog-enrichment.json').read_text())
    return data.get('products',{}) if data.get('approved') is True else {}

def variant_color(product,variant):
    return haravan_variants.option_value(product,variant,haravan_variants.COLOR_NAMES,catalog.norm)

def variant_size(product,variant):
    return haravan_variants.size(product,variant,catalog.norm)


def matches_model(product,code):
    return bool(re.search(r'(?<!\w)'+re.escape(catalog.norm(code))+r'(?!\w)',catalog.norm(product.get('title',''))) or any(catalog.norm(v.get('sku',''))==catalog.norm(code) for v in product['variants']))

def variant_price(variant):
    try:
        value=promotions.number(variant.get('price'))
        return int(value) if value>=0 and value==value.to_integral_value() else None
    except (ValueError,TypeError):return None

def verified_product_specs(product,approved):
    """Explicit heel measurement from Haravan title, not an LLM or SKU guess."""
    meta=dict(approved)
    title=catalog.norm(product.get('title',''))
    values={float(m.replace(',','.')) for m in re.findall(r'(?<![a-z])(?:chieu cao got|cao got|got)(?:\s+(?:cao|vuong|nhon|tru))?\s*[:(]?\s*([0-9]{1,2}(?:[.,][0-9])?)\s*cm(?![a-z0-9_])',title)}
    # Source-title measurement, including names with words between heel and cm.
    # Never interpret SKU/foot dimensions or approximate bounds as exact heels.
    context=title+' '+catalog.norm(product.get('product_type',''))
    if re.search(r'\b(?:cao got|got nhon|got vuong|got tru)\b',context):
        measures=list(re.finditer(r'(?<![a-z0-9_.-])([0-9]{1,2}(?:[.,][0-9])?)\s*cm(?![a-z0-9_])',title))
        safe=[]
        for match in measures:
            before=title[max(0,match.start()-25):match.start()]
            if re.search(r'(?:chan|chieu dai|vong|ngang|sku|ma|khoang|tam|tu|den)\s*[:#]?\s*$|[<>~]\s*$',before):continue
            safe.append(float(match.group(1).replace(',','.')))
        if len(measures)==len(safe):values.update(safe)
    if any(not 0<=v<=15 for v in values):
        meta.pop('heel_cm',None);return meta
    if len(values)==1 and not re.search(r'\bkhong(?: (?:phai|co))? (?:cao )?got\b',title):
        value=next(iter(values))
        if 'heel_cm' not in meta:meta['heel_cm']=value
        elif meta['heel_cm']!=value:meta.pop('heel_cm',None)
    elif len(values)>1:meta.pop('heel_cm',None)
    return meta

def search_products(data,candidate_only=False,candidate_limit=None):
    validate(data,{'model_code':(str,1,32),'query':(str,1,120),'collection':(str,1,120),'color':(str,1,40),'size':(int,35,43),'heel_cm':(float,0,15),'category':(str,1,60),'occasion':(str,1,60),'limit':(int,1,6),'check_stock':(bool,0,0),'stock_request_id':(str,32,32)})
    if candidate_limit is not None and (not candidate_only or type(candidate_limit) is not int or not 1<=candidate_limit<=catalog_query.MAX_SCAN_PRODUCTS):raise Invalid('invalid_internal_candidate_limit')
    if data.get('check_stock'):
        if 'size' not in data:raise Invalid('stock_scope_required')
        if 'stock_request_id' in data and not re.fullmatch(r'[0-9a-f]{32}',data['stock_request_id']):raise Invalid('stock_scope_required')
        if 'model_code' not in data or any(k in data for k in ('query','collection','heel_cm','category','occasion')):
            import product_discovery
            return product_discovery.lookup(data,sys.modules[__name__])
        import stock_options
        if 'stock_request_id' not in data:
            import secrets
            data=dict(data,stock_request_id=secrets.token_hex(16),_stock_schema='merly-stock-options-v2')
        return stock_options.lookup(data,sys.modules[__name__])
    import collection_catalog
    group=None
    if 'collection' in data:
        group=collection_catalog.resolve(data['collection'],h,catalog.FIELDS)
        if group['status']!='resolved':
            return {'status':'partial_metadata','products':[],'unknown_spec_products':1,'matched_products':0,'stock_checked':False,'collection_status':group['status'],'collection_choices':group.get('choices',[])}
        rows=group['products']
    else:rows=catalog.snapshot()
    if rows is None:return {'status':'catalog_loading','retryable':True,'products':[]}
    metadata=enrichment();results=[];unknown=0;unverified=set()
    for p in rows:
        if not catalog.eligible(p):continue
        code=data.get('model_code')
        if code and not matches_model(p,code):continue
        if 'query' in data and not catalog_query.name_matches(p,data['query']):continue
        approved=metadata.get(str(p['id']),{})
        meta=catalog_query.specs(p,approved,data,verified_product_specs)
        missing=set();mismatch=False
        for field in ('heel_cm','category','occasion'):
            if field not in data:continue
            actual=meta.get(field)
            if actual is None:
                if field=='category' and (p.get('product_type') or approved.get('category')):mismatch=True
                else:missing.add(field)
                continue
            match=actual==data[field] if field=='heel_cm' else catalog.norm(actual)==catalog.norm(data[field])
            if not match:mismatch=True
        if mismatch:continue
        if missing:
            unknown+=1;unverified.update(missing);continue
        variants=[]
        for v in p['variants']:
            size=variant_size(p,v);color=variant_color(p,v)
            if not candidate_only and 'size' in data and str(data['size'])!=size:continue
            if not candidate_only and 'color' in data and (color is None or catalog.norm(data['color'])!=catalog.norm(color)):continue
            variants.append({'variant_id':v['id'],'size':size,'color':color})
        if variants or candidate_only:
            evidence={}
            if 'category' in data:evidence['category']=catalog_query.category_evidence(p,data['category'],approved)
            if 'query' in data:evidence['query']={'field':'title/product_type','value':data['query']}
            hint=any(('size' not in data or v['size']==str(data['size'])) and ('color' not in data or v['color'] is not None and catalog.norm(v['color'])==catalog.norm(data['color'])) for v in variants)
            unknown_hint=any(v['size'] is None or ('color' in data and v['color'] is None) for v in variants)
            results.append({'_candidate_rank':0 if hint else 1 if unknown_hint else 2,'product_id':p['id'],'title':p.get('title',''),'product_type':p.get('product_type'),'image_url':image(p),'image_scope':'product','product_url':product_url(p),'variants':variants[:12],'variants_total':len(variants),'variants_truncated':len(variants)>12,'verified_specs':{k:meta[k] for k in ('heel_cm','category','occasion') if k in meta},'match_evidence':evidence,'availability':'not_checked'})
    if candidate_only:results.sort(key=lambda p:p['_candidate_rank'])
    for p in results:p.pop('_candidate_rank',None)
    limit=candidate_limit if candidate_limit is not None else data.get('limit',4)
    result={'status':'partial_metadata' if unknown else 'ok','products':results[:limit],'unknown_spec_products':unknown,'unverified_criteria':sorted(unverified),'stock_checked':False,'matched_products':len(results),'products_truncated':len(results)>limit,'note':'Names/types are retrieval evidence, not stock, fit or comfort. Fetch fresh inventory before claiming availability.'}
    types=sorted({p['product_type'] for p in rows if isinstance(p.get('product_type'),str) and 1<=len(p['product_type'])<=255 and catalog.eligible(p)})
    result.update(available_product_types=types[:30],product_types_truncated=len(types)>30)
    if group:
        result.update(collection_status='resolved',collection_evidence={**group['collection'],'product_ids':[p['product_id'] for p in results[:limit]]},catalog_fresh=True)
    return result

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
    return {'status':'ok' if complete else 'partial_inventory','product_id':p['id'],'variant_id':v['id'],'title':p.get('title',''),'size':variant_size(p,v),'color':variant_color(p,v),'price_vnd':price,'quantity':quantity,'subtotal_vnd':price*quantity if price is not None else None,'available':available,'known_available':total,'inventory_complete':complete,'locations':[{'name':name,'available':counts.get(loc)} for loc,name in LOCATIONS.items()],'checked_at':datetime.now(timezone.utc).isoformat(),'product_url':product_url(p),**picture(p,v),'reserved':False,'discounts_applied':False}

def size_guide(data):
    validate(data,{'size':(int,35,43),'length_cm':(float,15,35),'girth_cm':(float,10,40)})
    k=json.loads((ROOT/'vendor/knowledge-public-draft.json').read_text()).get('sizing',{})
    if k.get('approved') is not True:return {'status':'unverified'}
    rows=k['rows']
    if 'size' in data:rows=[r for r in rows if r['size']==data['size']]
    if 'length_cm' in data:rows=[r for r in rows if r['length_cm']==data['length_cm']]
    return {'status':'reference_only' if rows else 'needs_staff_review','chart':rows,'source':k['source_url'],'girth_provided':data.get('girth_cm'),'fit_confirmed':False,'note':'Exact reference points only. Do not round or infer fit; ask for model and foot circumference.'}

from policy_knowledge import TOPICS as POLICY_TOPICS,source_date as _policy_date

def get_policy(data):
    validate(data,{'topic':(str,1,40)})
    topic=data.get('topic')
    if topic not in POLICY_TOPICS:raise Invalid('unknown_topic')
    import policy_knowledge
    return policy_knowledge.get(ROOT,topic)


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
    if isinstance(data,dict):data=dict(data)
    return TOOLS[name](data)
