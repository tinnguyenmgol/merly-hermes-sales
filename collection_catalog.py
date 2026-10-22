"""On-demand public custom/smart collections via documented fixed-host GETs.
No rule emulation, collect creation or bulk prefetch of every collection's products.
"""
import threading,time
from catalog_query import norm,phrase
_LOCK=threading.Lock();_CACHE=None
SECONDS=8;PAGES=4;MEMBER_PAGES=61

def clear():
    global _CACHE
    with _LOCK:_CACHE=None

def _pages(h,resource,key,deadline,extra,max_pages):
    result=[];seen=set()
    for page in range(1,max_pages+1):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise h.HaravanError('collection_budget_exceeded')
        body=h.get(resource,dict(extra,limit=50,page=page),timeout=min(3,remaining))
        rows=body.get(key)
        if not isinstance(rows,list) or len(rows)>50:raise h.HaravanError('invalid_collection_page')
        for row in rows:
            if not isinstance(row,dict) or type(row.get('id')) is not int or not 0<row['id']<10**16 or row['id'] in seen:raise h.HaravanError('invalid_collection_identity')
            seen.add(row['id']);result.append(row)
        if len(rows)<50:return result
    raise h.HaravanError('collection_paging_incomplete')

def names(h,deadline):
    global _CACHE
    with _LOCK:
        if _CACHE and _CACHE[0]==id(h.get) and time.monotonic()-_CACHE[1]<300:return list(_CACHE[2])
        result=[];seen=set()
        for resource in ('custom_collections','smart_collections'):
            rows=_pages(h,resource,resource,deadline,{'fields':'id,title,handle,published,published_at'},PAGES)
            for row in rows:
                if 'published' in row and type(row['published']) is not bool:continue
                if row.get('published') is False or not isinstance(row.get('published_at'),str) or not row['published_at']:continue
                if not isinstance(row.get('title'),str) or not 1<=len(row['title'])<=255:continue
                if not isinstance(row.get('handle'),str) or not 1<=len(row['handle'])<=255:continue
                if row['id'] in seen:raise h.HaravanError('ambiguous_collection_identity')
                seen.add(row['id']);result.append({k:row[k] for k in ('id','title','handle')})
        _CACHE=(id(h.get),time.monotonic(),result)
        return list(result)

def resolve(query,h,fields):
    deadline=time.monotonic()+SECONDS
    try:
        rows=names(h,deadline)
        exact=[r for r in rows if norm(query) in (norm(r['title']),norm(r['handle']))]
        matches=exact or [r for r in rows if phrase(r['title'],query)]
        if len(matches)!=1:return {'status':'ambiguous' if matches else 'not_found','choices':matches[:8],'products':[]}
        group=matches[0]
        products=_pages(h,'products','products',deadline,{'collection_id':group['id'],'fields':fields},MEMBER_PAGES)
        if len(products)>3000:raise h.HaravanError('collection_catalog_limit')
        return {'status':'resolved','collection':group,'products':products}
    except h.HaravanError:
        return {'status':'source_unavailable','choices':[],'products':[]}
