"""Read-only bounded live inventory sweep for a model/size; no LLM selection."""
import time
from media_urls import picture
from datetime import datetime,timezone
MAX_PRODUCTS=20
MAX_VARIANTS=100
BATCH=10

ISSUE_CODES={'missing_access_token','haravan_unavailable','invalid_response','response_too_large','product_identity_changed','invalid_variant_identity','invalid_batch_inventory','invalid_variant_count','invalid_variants_page','invalid_variant','variant_identity_mismatch','variant_count_changed_or_incomplete','variant_lookup_budget_exceeded','variant_size_metadata_unverified','variant_color_metadata_unverified','invalid_inventory_response','unexpected_inventory_row','invalid_quantity'}
def issue(exc,stage):
    import re
    code=str(exc)
    if code not in ISSUE_CODES and not re.fullmatch(r'haravan_http_[1-5][0-9]{2}',code):code='source_unavailable'
    return {'stage':stage,'code':code}

def lookup(data,tools):
    code=data['model_code'];size=data['size'];request_id=data['stock_request_id']
    status=tools.catalog.status();rows=tools.catalog.snapshot()
    report={'schema':data.get('_stock_schema','merly-stock-options-v1'),'stock_request_id':request_id,'mode':'all_options','model_code':code,'size':size,'color_filter':data.get('color'),'quantity':1,'issues':[],'variants':[],'complete':False,'coverage':{'candidate_products':0,'products_checked':0,'variants_found':0,'variants_checked':0,'unverified_products':0,'omitted_variants':0,'unclassified_variants':0},'catalog_age_seconds':status.get('age_seconds'),'checked_at':datetime.now(timezone.utc).isoformat()}
    if rows is None:
        report['status']='catalog_loading';return {'stock_report':report}
    candidates=[p for p in rows if tools.catalog.eligible(p) and tools.matches_model(p,code)]
    coverage=report['coverage'];coverage['candidate_products']=len(candidates);coverage['unverified_products']=len(candidates)
    records=[];seen=set();deadline=time.monotonic()+15
    for candidate in candidates[:MAX_PRODUCTS]:
        if time.monotonic()>=deadline:break
        try:
            product=tools.h.get('products/'+str(candidate['id']),{}).get('product')
            if not isinstance(product,dict) or product.get('id')!=candidate['id'] or not tools.catalog.eligible(product) or not tools.matches_model(product,code):raise tools.h.HaravanError('product_identity_changed')
            variants=tools.haravan_variants.all_variants(tools.h,product['id'],deadline)
            selected=[];local=set();metadata_issue=False
            for variant in variants:
                variant_size=tools.variant_size(product,variant)
                if variant_size is None:
                    coverage['unclassified_variants']+=1;metadata_issue=True;continue
                if variant_size!=str(size):continue
                color=tools.variant_color(product,variant)
                if data.get('color') and color is None:
                    coverage['unclassified_variants']+=1;metadata_issue=True;continue
                if data.get('color') and (color is None or tools.catalog.norm(data['color'])!=tools.catalog.norm(color)):continue
                vid=variant.get('id')
                if type(vid) is not int or not 1<=vid<10**16 or vid in seen or vid in local:raise tools.h.HaravanError('invalid_variant_identity')
                local.add(vid)
                selected.append({'product_id':product['id'],'variant_id':vid,'title':product.get('title',''),'color':color,'size':str(size),'price_vnd':tools.variant_price(variant),'available':None,'known_available':0,'inventory_complete':False,'locations':[{'name':name,'available':None} for name in tools.LOCATIONS.values()],'product_url':tools.product_url(product),**picture(product,variant)})
            if metadata_issue:report['issues'].append({'stage':'product_variants','code':'variant_size_metadata_unverified'})
            seen.update(local);coverage['products_checked']+=1;coverage['unverified_products']-=1;coverage['variants_found']+=len(selected)
            room=MAX_VARIANTS-len(records);records.extend(selected[:room]);coverage['omitted_variants']+=max(0,len(selected)-room)
        except tools.h.HaravanError as exc:
            report['issues'].append(issue(exc,'product_variants'));continue
    for start in range(0,len(records),BATCH):
        if time.monotonic()>=deadline:break
        group=records[start:start+BATCH];by_id={str(r['variant_id']):{} for r in group}
        try:
            inventory=tools.h.inventory(','.join(map(str,by_id)),','.join(map(str,tools.LOCATIONS)))
            for row in inventory:
                vid=row.get('variant_id');loc=row.get('loc_id');qty=row.get('qty_available')
                if type(vid) not in (int,str) or str(vid) not in by_id or type(loc) is not int or loc not in tools.LOCATIONS or loc in by_id[str(vid)] or type(qty) not in (int,float) or not tools.math.isfinite(qty) or int(qty)!=qty:raise tools.h.HaravanError('invalid_batch_inventory')
                by_id[str(vid)][loc]=max(0,int(qty))
            for item in group:
                counts=by_id[str(item['variant_id'])];complete=set(counts)==set(tools.LOCATIONS);total=sum(counts.values())
                item.update({'known_available':total,'inventory_complete':complete,'available':True if total>0 else False if complete else None,'locations':[{'name':name,'available':counts.get(loc)} for loc,name in tools.LOCATIONS.items()]})
                if complete:coverage['variants_checked']+=1
        except tools.h.HaravanError as exc:
            report['issues'].append(issue(exc,'inventory'));continue
    age=status.get('age_seconds');fresh=status.get('ready') is True and type(age) in (int,float) and 0<=age<=300
    report['variants']=records
    report['complete']=bool(candidates) and fresh and not report['issues'] and not coverage['unverified_products'] and not coverage['omitted_variants'] and coverage['variants_checked']==len(records)
    report['status']='ok' if report['complete'] else 'partial_inventory'
    return {'stock_report':report}
