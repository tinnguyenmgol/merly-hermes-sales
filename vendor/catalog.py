"""Bounded in-memory catalog; Haravan only, no customer input to upstream URLs."""
import threading,time,unicodedata,re
import haravan_client as h
import catalog_store
FIELDS='id,title,handle,published_at,published_scope,status,variants,options,image,images,product_type'
LOCK=threading.Lock(); PRODUCTS=[]; UPDATED=0; LOADING=False; ERROR=None; ATTEMPT=0; STORE_ERROR=None; STARTED=False

def norm(text):
    text=str(text).casefold().replace('đ','d')
    return ''.join(c for c in unicodedata.normalize('NFD',text) if unicodedata.category(c)!='Mn')

def sync():
    global PRODUCTS,UPDATED,LOADING,ERROR,ATTEMPT,STORE_ERROR
    ATTEMPT=time.monotonic()
    with LOCK: LOADING=True
    products=[]; seen=set()
    try:
        for page in range(1,62):
            rows=h.get('products',{'limit':50,'page':page,'fields':FIELDS}).get('products')
            if not isinstance(rows,list): raise h.HaravanError('invalid_catalog')
            if not rows: break
            ids=[p.get('id') for p in rows if isinstance(p,dict)]
            if len(ids)!=len(rows) or any(type(i) is not int or i<=0 or i in seen for i in ids) or len(set(ids))!=len(ids): raise h.HaravanError('invalid_catalog_cursor')
            if len(seen)+len(ids)>3000: raise h.HaravanError('catalog_limit_reached')
            seen.update(ids)
            products.extend(p for p in rows if eligible(p))
            if len(rows)<50: break
        else: raise h.HaravanError('catalog_limit_reached')
        with LOCK: PRODUCTS=products; UPDATED=time.monotonic(); ERROR=None
        try: catalog_store.save(products); STORE_ERROR=None
        except (OSError,ValueError,TypeError): STORE_ERROR='snapshot_write_failed'
    except h.HaravanError as e:
        with LOCK: ERROR=str(e)
    except Exception:
        with LOCK: ERROR='invalid_catalog'
    finally:
        with LOCK: LOADING=False

def snapshot():
    global LOADING
    with LOCK:
        age=time.monotonic()-UPDATED if UPDATED else float('inf')
        if not LOADING and age>300 and time.monotonic()-ATTEMPT>60:
            LOADING=True; threading.Thread(target=sync,daemon=True).start()
        if age>86400: return None
        return list(PRODUCTS)

def colors(product,variant):
    options=product.get('options',[])
    result=[]
    for option in options:
        if not isinstance(option,dict): continue
        if any(w in norm(option.get('name','')) for w in ['mau','color','colour']):
            value=variant.get('option'+str(option.get('position')))
            if isinstance(value,str) and value: result.append(value)
    if result: return ' / '.join(result)
    title=variant.get('title','')
    parts=[p.strip() for p in title.split('/') if p.strip() and not re.fullmatch(r'(?:size\s*)?(?:3[5-9]|4[0-3])',norm(p.strip()))]
    return ' / '.join(parts) or product.get('title','')

def size(variant):
    values=[variant.get('option'+str(i),'') for i in (1,2,3)]
    for value in values:
        if re.fullmatch(r'(?:size\s*)?(3[5-9]|4[0-3])',norm(value).strip()): return re.search(r'3[5-9]|4[0-3]',str(value)).group()
    m=re.search(r'(?:^|/|size\s*)\s*(3[5-9]|4[0-3])\s*$',norm(variant.get('title','')).strip())
    return m.group(1) if m else None


def eligible(product):
    # Owner explicitly approved POS/unpublished catalog for customer advice.
    return (isinstance(product,dict) and isinstance(product.get('variants'),list)
            and str(product.get('status','')).casefold() not in ('archived','deleted'))


def restore():
    global PRODUCTS,UPDATED,STORE_ERROR
    try:
        restored=catalog_store.load()
        if restored:
            products,age=restored
            with LOCK: PRODUCTS=products;UPDATED=time.monotonic()-age
    except (OSError,ValueError,TypeError):STORE_ERROR='snapshot_read_failed'

def start():
    global STARTED
    with LOCK:
        if STARTED:return
        STARTED=True
    restore()
    def loop():
        while True:
            snapshot()
            time.sleep(10)
    threading.Thread(target=loop,daemon=True,name='catalog-warmup').start()

def status():
    with LOCK:
        age=round(time.monotonic()-UPDATED,1) if UPDATED else None
        return {'ready':UPDATED!=0 and age<=86400,'refreshing':LOADING,'age_seconds':age,'error':ERROR,'storage_error':STORE_ERROR}
