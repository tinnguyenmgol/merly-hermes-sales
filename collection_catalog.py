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
    if not _LOCK.acquire(timeout=max(0,deadline-time.monotonic())):raise h.HaravanError('collection_budget_exceeded')
    try:
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
    finally:_LOCK.release()

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

PREFER_SECONDS=2

def preferred(data,h,fields):
    """Collection is only a retrieval hint, never proof of product attributes.
    Missing/ambiguous/inaccessible hints fall back to the complete catalog.
    Explicit required `collection` continues to use resolve(), not this path.
    """
    import os,re,math
    base={'strategy':'filters','collection_status':'not_attempted','preferred_products':0}
    hint=data.get('collection_hint')
    if data.get('model_code') and not hint:return set(),base
    if not hint and not any(k in data for k in ('heel_cm','category','occasion','query','size','color')):return set(),base
    # A snapshot can exist without API credentials; do not attempt optional
    # remote discovery when this fixed transport is not configured.
    if not hint and not os.getenv('HARAVAN_ACCESS_TOKEN'):return set(),base
    deadline=time.monotonic()+PREFER_SECONDS
    try:
        rows=names(h,deadline)
        if hint:
            exact=[r for r in rows if norm(hint) in (norm(r['title']),norm(r['handle']))]
            matches=exact or [r for r in rows if phrase(r['title'],hint)]
        else:
            scores=[]
            for row in rows:
                text=row['title']+' '+row['handle'];score=0
                for field in ('query','category','occasion'):
                    if data.get(field) and phrase(text,data[field]):score+=2
                if data.get('color') and phrase(text,data['color']):score+=1
                if 'size' in data and re.search(r'\bsize\s*'+str(data['size'])+r'(?!\d)',norm(text)):score+=1
                if 'heel_cm' in data:
                    values=[float(v.replace(',','.')) for v in re.findall(r'(?<![\w.,])([0-9]+(?:[.,][0-9]+)?)\s*cm\b',norm(text))]
                    if any(math.isfinite(v) and v==data['heel_cm'] for v in values):score+=4
                if score:scores.append((score,row))
            best=max((n for n,_ in scores),default=0)
            matches=[r for n,r in scores if n==best]
        if len(matches)!=1:return set(),{**base,'collection_status':'ambiguous' if matches else 'not_found'}
        group=matches[0]
        products=_pages(h,'products','products',deadline,{'collection_id':group['id'],'fields':fields},MEMBER_PAGES)
        if len(products)>3000:raise h.HaravanError('collection_catalog_limit')
        ids={p['id'] for p in products}
        return ids,{'strategy':'collection_first_filters','collection_status':'resolved','preferred_products':len(ids)}
    except h.HaravanError as exc:
        return set(),{**base,'collection_status':'rate_limited' if str(exc)=='haravan_http_429' else 'source_unavailable'}
    except (ValueError,TypeError):
        return set(),{**base,'collection_status':'source_unavailable'}

def prioritize(rows,preferred_ids,window):
    """Preserve variant-match ranks; reserve early opportunities outside a hint.
    A large or poorly stocked collection must not consume every candidate slot.
    """
    ordered=[];batch=max(1,min(4,window//2))
    for rank in sorted({r['_candidate_rank'] for r in rows}):
        inside=[r for r in rows if r['_candidate_rank']==rank and r['product_id'] in preferred_ids]
        outside=[r for r in rows if r['_candidate_rank']==rank and r['product_id'] not in preferred_ids]
        for start in range(0,max(len(inside),len(outside)),batch):
            ordered.extend(inside[start:start+batch]);ordered.extend(outside[start:start+batch])
    return ordered
