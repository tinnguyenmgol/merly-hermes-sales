"""Fixed-host GET-only Haravan probe. Not exposed through public webchat."""
import json,os,re,time,urllib.request,urllib.error
from urllib.parse import urlencode
class HaravanError(Exception): pass
from contextvars import ContextVar
from contextlib import contextmanager
_REQUEST_DEADLINE=ContextVar('haravan_request_deadline',default=None)
@contextmanager
def request_deadline(deadline):
    import math
    if type(deadline) not in (int,float) or not math.isfinite(deadline):raise HaravanError('invalid_request_deadline')
    previous=_REQUEST_DEADLINE.get()
    token=_REQUEST_DEADLINE.set(min(previous,deadline) if previous is not None else deadline)
    try:yield
    finally:_REQUEST_DEADLINE.reset(token)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def get(resource,params,timeout=12):
    if resource not in ('products','inventory_locations','promotions','discounts','custom_collections','smart_collections') and not re.fullmatch(r'(?:(?:products|promotions|discounts|variants)/[1-9][0-9]{0,15}|products/[1-9][0-9]{0,15}/variants(?:/count)?)',resource): raise HaravanError('resource_not_allowed')
    deadline=_REQUEST_DEADLINE.get()
    if deadline is not None:
        remaining=deadline-time.monotonic()
        if remaining<=0:raise HaravanError('request_budget_exceeded')
        timeout=min(timeout,remaining)
    token=os.getenv('HARAVAN_ACCESS_TOKEN','').strip()
    if not token: raise HaravanError('missing_access_token')
    req=urllib.request.Request('https://apis.haravan.com/com/'+resource+'.json?'+urlencode(params),headers={'Authorization':'Bearer '+token,'Accept':'application/json'},method='GET')
    started=time.monotonic(); success=False
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=timeout) as r: raw=r.read(1048577)
        if len(raw)>1048576: raise HaravanError('response_too_large')
        data=json.loads(raw)
        if not isinstance(data,dict): raise HaravanError('invalid_response')
        success=True
        return data
    except urllib.error.HTTPError as e: raise HaravanError('haravan_http_'+str(e.code)) from None
    except (urllib.error.URLError,TimeoutError,OSError): raise HaravanError('haravan_unavailable') from None
    except (ValueError,TypeError): raise HaravanError('invalid_response') from None
    finally:
        print(json.dumps({'event':'haravan_latency','resource':resource.split('/')[0],'success':success,'duration_ms':round((time.monotonic()-started)*1000,1)}),flush=True)

def ids(value):
    if not isinstance(value,str) or not re.fullmatch(r'[1-9][0-9]*(,[1-9][0-9]*){0,19}',value): raise HaravanError('invalid_ids')
    return value

def inventory(variant,locations):
    variant=ids(variant); locations=ids(locations)
    data=get('inventory_locations',{'variant_ids':variant,'location_ids':locations})
    rows=data.get('inventory_locations')
    if not isinstance(rows,list): raise HaravanError('invalid_inventory_response')
    output=[]
    for row in rows:
        if not isinstance(row,dict) or str(row.get('variant_id')) not in variant.split(',') or str(row.get('loc_id')) not in locations.split(','): raise HaravanError('unexpected_inventory_row')
        qty=row.get('qty_available')
        if isinstance(qty,bool) or not isinstance(qty,(int,float)) or not __import__('math').isfinite(qty): raise HaravanError('invalid_quantity')
        output.append({k:row.get(k) for k in ('variant_id','loc_id','qty_available','updated_at')})
    return output

if __name__=='__main__':
    try:
        variant=os.getenv('HARAVAN_TEST_VARIANT_ID',''); locations=os.getenv('HARAVAN_TEST_LOCATION_IDS','')
        if variant and locations:
            rows=inventory(variant,locations)
            print('HARAVAN_INVENTORY_OK — raw read-only rows; missing rows do not mean zero stock')
            print(json.dumps(rows,ensure_ascii=False,indent=2))
        elif variant or locations: raise HaravanError('need_both_variant_and_location_ids')
        else:
            products=get('products',{'limit':1}).get('products')
            if not isinstance(products,list): raise HaravanError('invalid_products_response')
            print('HARAVAN_PRODUCTS_OK — inventory permission not yet verified')
            for p in products:
                print(json.dumps({'product_id':p.get('id'),'title':p.get('title'),'variants':[{'variant_id':v.get('id'),'sku':v.get('sku'),'title':v.get('title')} for v in p.get('variants',[])[:10]]},ensure_ascii=False))
    except HaravanError as e:
        print('HARAVAN_FAILED:',str(e)); raise SystemExit(1)
