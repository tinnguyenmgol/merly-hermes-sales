"""Public catalog-only disk snapshot. No inventory, tokens or conversations."""
import json,os,time,tempfile
from pathlib import Path
MAX_BYTES=25*1024*1024
PRODUCT=('id','title','handle','published_at','published_scope','status','options','image','images','product_type')
VARIANT=('image_id','id','sku','title','option1','option2','option3')

def path():
    value=os.getenv('CATALOG_CACHE_PATH','').strip()
    return Path(value) if value else None

def clean(products):
    output=[]
    for p in products:
        item={k:p[k] for k in PRODUCT if k in p}
        item['variants']=[{k:v[k] for k in VARIANT if k in v} for v in p.get('variants',[]) if isinstance(v,dict)]
        output.append(item)
    return output

def save(products):
    target=path()
    if target is None:return
    payload=json.dumps({'version':1,'saved_at':time.time(),'products':clean(products)},ensure_ascii=False).encode()
    if len(payload)>MAX_BYTES: raise ValueError('snapshot_too_large')
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        fd,temporary=tempfile.mkstemp(prefix='.catalog-',dir=target.parent)
        with os.fdopen(fd,'wb') as out:
            out.write(payload);out.flush();os.fsync(out.fileno())
        os.replace(temporary,target);temporary=None
    finally:
        if temporary is not None:Path(temporary).unlink(missing_ok=True)

def load():
    target=path()
    if target is None or not target.is_file():return None
    if target.stat().st_size>MAX_BYTES:raise ValueError('snapshot_too_large')
    data=json.loads(target.read_text())
    if not isinstance(data,dict) or data.get('version')!=1:raise ValueError('invalid_snapshot')
    saved=data.get('saved_at')
    if isinstance(saved,bool) or not isinstance(saved,(int,float)):raise ValueError('invalid_snapshot')
    age=time.time()-saved
    if not 0<=age<=86400:return None
    products=data.get('products')
    if not isinstance(products,list) or len(products)>3000:raise ValueError('invalid_snapshot')
    for p in products:
        if not isinstance(p,dict) or type(p.get('id')) is not int or not isinstance(p.get('variants'),list):raise ValueError('invalid_snapshot')
    return clean(products),age
