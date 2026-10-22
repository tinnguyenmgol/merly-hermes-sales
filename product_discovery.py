"""Generic criteria -> fresh products/variants -> live inventory. No phrases/LLM."""
import math,secrets,time
import catalog_query
from media_urls import picture,safe_image
from datetime import datetime,timezone
KEYS=('query','collection','model_code','size','color','heel_cm','category','occasion')
MAX_PRODUCTS=4;MAX_VARIANTS=40;BATCH=10;SECONDS=15

def criteria(data):return {k:data[k] for k in KEYS if k in data}
def matching_specs(product,data,tools,meta):
    specs=catalog_query.specs(product,meta.get(str(product['id']),{}),data,tools.verified_product_specs)
    if 'query' in data and not catalog_query.name_matches(product,data['query']):return specs,'changed'
    for field in ('heel_cm','category','occasion'):
        if field not in data:continue
        value=specs.get(field)
        if value is None:return specs,'metadata_unverified'
        same=value==data[field] if field=='heel_cm' else tools.catalog.norm(value)==tools.catalog.norm(data[field])
        if not same:return specs,'changed'
    if data.get('model_code') and not tools.matches_model(product,data['model_code']):return specs,'changed'
    return specs,None

def lookup(data,tools):
    deadline=time.monotonic()+SECONDS
    # Color checked EXACTLY against fresh variants, not merged by substring.
    query={k:v for k,v in data.items() if k in ('query','collection','model_code','size','heel_cm','category','occasion')}
    query['limit']=min(data.get('limit',MAX_PRODUCTS),MAX_PRODUCTS)
    found=tools.search_products(query,candidate_only=True);source={'ready':True,'age_seconds':0} if found.get('catalog_fresh') else tools.catalog.status();meta=tools.enrichment()
    report={'schema':'merly-product-discovery-v1','operation_id':secrets.token_hex(16),'mode':'discovery','criteria':criteria(data),'complete':False,'products':[],'variants':[],'issues':[],
      'coverage':{'catalog_matches':found.get('matched_products',0),'unknown_spec_products':found.get('unknown_spec_products',0),'omitted_products':max(0,found.get('matched_products',0)-len(found['products'])),'omitted_variants':0},
      'catalog_age_seconds':source.get('age_seconds'),'source_status':found['status'],'checked_at':datetime.now(timezone.utc).isoformat()}
    if 'collection' in data:
        report['collection_status']=found.get('collection_status','source_unavailable')
        if found.get('collection_evidence'):report['collection_evidence']=found['collection_evidence']
        report['collection_choices']=found.get('collection_choices',[])
    records=[];seen=set()
    for candidate in found['products']:
        item={'product_id':candidate['product_id'],'title':candidate.get('title','')[:300],'product_url':candidate.get('product_url'),'image_url':candidate.get('image_url'),'image_scope':'product','product_type':candidate.get('product_type'),'verified_specs':candidate.get('verified_specs',{}),'status':'unchecked'}
        report['products'].append(item)
        if time.monotonic()>=deadline:continue
        try:
            product=tools.h.get('products/'+str(item['product_id']),{}).get('product')
            if not isinstance(product,dict) or product.get('id')!=item['product_id'] or not tools.catalog.eligible(product):raise tools.h.HaravanError('product_identity_changed')
            item.update(title=product.get('title','')[:300],product_url=tools.product_url(product),image_url=tools.image(product),product_type=product.get('product_type'))
            specs,error=matching_specs(product,data,tools,meta);item['verified_specs']={k:specs[k] for k in ('heel_cm','category','occasion') if k in specs}
            if error:item['status']=error;continue
            variants=tools.haravan_variants.all_variants(tools.h,product['id'],deadline)
            selected=[];unclassified=False
            for v in variants:
                size=tools.variant_size(product,v);color=tools.variant_color(product,v)
                if size is None:unclassified=True;continue
                if size!=str(data['size']):continue
                if data.get('color') and color is None:unclassified=True;continue
                if data.get('color') and tools.catalog.norm(color)!=tools.catalog.norm(data['color']):continue
                vid=v.get('id')
                if type(vid) is not int or not 1<=vid<10**16 or vid in seen:raise tools.h.HaravanError('invalid_variant_identity')
                seen.add(vid)
                selected.append({'product_id':product['id'],'variant_id':vid,'title':item['title'],'color':color,'size':size,'price_vnd':tools.variant_price(v),'available':None,'known_available':0,'inventory_complete':False,'locations':[{'name':name,'available':None} for name in tools.LOCATIONS.values()],'product_url':item['product_url'],**picture(product,v)})
            item['status']='metadata_unverified' if unclassified else 'matched' if selected else 'no_matching_variants'
            room=MAX_VARIANTS-len(records);records.extend(selected[:room]);report['coverage']['omitted_variants']+=max(0,len(selected)-room)
        except tools.h.HaravanError:
            item['status']='source_unavailable';report['issues'].append({'stage':'product','product_id':item['product_id']})
    for start in range(0,len(records),BATCH):
        if time.monotonic()>=deadline:break
        group=records[start:start+BATCH];counts={str(r['variant_id']):{} for r in group}
        try:
            rows=tools.h.inventory(','.join(counts),','.join(map(str,tools.LOCATIONS)))
            for row in rows:
                vid=str(row.get('variant_id'));loc=row.get('loc_id');qty=row.get('qty_available')
                if vid not in counts or type(loc) is not int or loc not in tools.LOCATIONS or loc in counts[vid] or type(qty) not in (int,float) or not math.isfinite(qty) or int(qty)!=qty:raise tools.h.HaravanError('invalid_batch_inventory')
                counts[vid][loc]=max(0,int(qty))
            for r in group:
                values=counts[str(r['variant_id'])];known=sum(values.values());complete=set(values)==set(tools.LOCATIONS)
                r.update(known_available=known,inventory_complete=complete,available=True if known>0 else False if complete else None,locations=[{'name':name,'available':values.get(loc)} for loc,name in tools.LOCATIONS.items()])
        except tools.h.HaravanError:report['issues'].append({'stage':'inventory'})
    report['variants']=records
    age=report['catalog_age_seconds']
    report['complete']=bool(source.get('ready') and type(age) in (int,float) and 0<=age<=300 and not report['issues'] and not report['coverage']['unknown_spec_products'] and not report['coverage']['omitted_products'] and not report['coverage']['omitted_variants'] and all(p['status'] in ('matched','no_matching_variants','changed') for p in report['products']) and all(r['inventory_complete'] for r in records))
    report['checked_at']=datetime.now(timezone.utc).isoformat()
    return {'stock_report':report}

def validate(report,args,turn_started):
    import re
    from stock_report import InvalidReport,clean_variant,safe_url
    from merly_tools import catalog,LOCATIONS,enrichment
    def bad(code):raise InvalidReport(code)
    if not isinstance(report,dict) or report.get('schema')!='merly-product-discovery-v1' or report.get('mode')!='discovery':bad('invalid_shape')
    if report.get('criteria')!=criteria(args):bad('wrong_scope')
    for k,v in criteria(args).items():
        if k=='heel_cm':
            if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=15:bad('invalid_scope')
        elif k!='size' and (not isinstance(v,str) or not 1<=len(v)<=(120 if k in ('query','collection') else 32 if k=='model_code' else 40 if k=='color' else 60)):bad('invalid_scope')
    if type(args.get('size')) is not int or not 35<=args['size']<=43:bad('invalid_scope')
    if not isinstance(report.get('operation_id'),str) or not re.fullmatch(r'[0-9a-f]{32}',report['operation_id']):bad('invalid_operation_id')
    try:
        stamp=datetime.fromisoformat(report['checked_at'].replace('Z','+00:00'))
    except (KeyError,ValueError,TypeError,AttributeError):bad('invalid_checked_at')
    if stamp.tzinfo is None:bad('invalid_checked_at')
    if type(turn_started) not in (int,float):bad('missing_turn_boundary')
    if not turn_started-3<=stamp.timestamp()<=time.time()+3:bad('stale_evidence')
    cov=report.get('coverage');products=report.get('products');rows=report.get('variants')
    if type(report.get('complete')) is not bool or not isinstance(cov,dict) or not isinstance(products,list) or len(products)>MAX_PRODUCTS or not isinstance(rows,list) or len(rows)>MAX_VARIANTS:bad('invalid_shape')
    for key in ('catalog_matches','unknown_spec_products','omitted_products','omitted_variants'):
        if type(cov.get(key)) is not int or not 0<=cov[key]<=100000:bad('invalid_count')
    if cov['catalog_matches']!=len(products)+cov['omitted_products']:bad('inconsistent_coverage')
    parents={};clean_products=[]
    states={'unchecked','matched','no_matching_variants','metadata_unverified','changed','source_unavailable'}
    for p in products:
        if not isinstance(p,dict) or type(p.get('product_id')) is not int or not 1<=p['product_id']<10**16 or p['product_id'] in parents:bad('invalid_identity')
        if not isinstance(p.get('title'),str) or len(p['title'])>300 or p.get('status') not in states or not isinstance(p.get('verified_specs'),dict):bad('invalid_product')
        specs=p['verified_specs']
        for k,v in specs.items():
            if k=='heel_cm':
                if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=15:bad('invalid_specs')
            elif k not in ('category','occasion') or not isinstance(v,str) or not 1<=len(v)<=60:bad('invalid_specs')
        parent={'product_id':p['product_id'],'title':p['title'],'product_url':safe_url(p.get('product_url')),'image_url':safe_image(p.get('image_url')),'image_scope':'product','product_type':p.get('product_type') if isinstance(p.get('product_type'),str) and len(p['product_type'])<=255 else None,'verified_specs':dict(specs),'status':p['status']}
        parents[p['product_id']]=parent;clean_products.append(parent)
    collection_info={}
    if 'collection' in args:
        status=report.get('collection_status')
        if status not in ('resolved','ambiguous','not_found','source_unavailable'):bad('invalid_collection')
        collection_info['collection_status']=status
        choices=report.get('collection_choices',[])
        if not isinstance(choices,list) or len(choices)>8:bad('invalid_collection')
        cleaned_choices=[]
        for choice in choices:
            if not isinstance(choice,dict) or type(choice.get('id')) is not int or not 0<choice['id']<10**16:bad('invalid_collection')
            if any(not isinstance(choice.get(k),str) or not 1<=len(choice[k])<=255 for k in ('title','handle')):bad('invalid_collection')
            cleaned_choices.append({k:choice[k] for k in ('id','title','handle')})
        collection_info['collection_choices']=cleaned_choices
        if status=='resolved':
            proof=report.get('collection_evidence')
            if not isinstance(proof,dict) or type(proof.get('id')) is not int or not 0<proof['id']<10**16:bad('invalid_collection')
            if any(not isinstance(proof.get(k),str) or not 1<=len(proof[k])<=255 for k in ('title','handle')):bad('invalid_collection')
            if catalog_query.norm(args['collection']) not in (catalog_query.norm(proof['title']),catalog_query.norm(proof['handle'])) and not catalog_query.phrase(proof['title'],args['collection']):bad('wrong_scope')
            ids=proof.get('product_ids')
            if not isinstance(ids,list) or any(type(i) is not int for i in ids) or len(set(ids))!=len(ids) or set(ids)!=set(parents):bad('invalid_collection_membership')
            collection_info['collection_evidence']={k:proof[k] for k in ('id','title','handle','product_ids')}
        elif products or rows or report['complete']:bad('false_complete')
    clean=[];seen=set()
    for row in rows:
        item=clean_variant(row,args['size']);parent=parents.get(item['product_id'])
        if parent is None or item['variant_id'] in seen or parent['status'] not in ('matched','metadata_unverified'):bad('invalid_variant')
        seen.add(item['variant_id'])
        if {loc['name'] for loc in item['locations']}!=set(LOCATIONS.values()):bad('invalid_locations')
        if item['product_url']!=parent['product_url']:bad('invalid_product_link')
        if args.get('color') and catalog.norm(item.get('color'))!=catalog.norm(args['color']):bad('wrong_color_scope')
        for k in ('heel_cm','category','occasion'):
            if k not in args:continue
            value=parent['verified_specs'].get(k)
            if value is None or (value!=args[k] if k=='heel_cm' else catalog.norm(value)!=catalog.norm(args[k])):bad('wrong_scope')
        if 'query' in args and not catalog_query.name_matches(parent,args['query']):bad('wrong_scope')
        if 'category' in args and not catalog_query.category_evidence(parent,args['category'],enrichment().get(str(parent['product_id']),{})):bad('wrong_scope')
        item['title']=parent['title'];item['product_type']=parent.get('product_type');clean.append(item)
    source=report.get('source_status');age=report.get('catalog_age_seconds')
    if source not in ('ok','partial_metadata','catalog_loading'):bad('invalid_source_status')
    if report['complete'] and (source=='catalog_loading' or type(age) not in (int,float) or not 0<=age<=300 or any(cov[k] for k in ('unknown_spec_products','omitted_products','omitted_variants')) or any(p['status'] not in ('matched','changed','no_matching_variants') for p in clean_products) or not all(r['inventory_complete'] for r in clean) or report.get('issues')):bad('false_complete')
    result={'mode':'discovery','criteria':criteria(args),'complete':report['complete'],'products':clean_products,'variants':clean,'coverage':dict(cov),'checked_at':report['checked_at'],'source_status':source}
    result.update(collection_info)
    return classify(result)

def classify(report):
    if report.get('source_status')=='catalog_loading':state='catalog_loading'
    elif any(r.get('available') is True for r in report['variants']):state='available' if report['complete'] else 'partial_available'
    elif report['variants']:state='verified_zero' if report['complete'] else 'partial'
    elif report['coverage']['unknown_spec_products'] or any(p['status']=='metadata_unverified' for p in report['products']):state='metadata_missing'
    elif any(p['status'] in ('source_unavailable','unchecked') for p in report['products']):state='source_error'
    else:state='no_match'
    report['operation_status']=state;return report

def summary(report):
    state=report['operation_status']
    if report.get('collection_status')=='ambiguous' and report.get('collection_choices'):
        names='; '.join(c['title'] for c in report['collection_choices'])
        return 'Có nhiều nhóm phù hợp tên bạn hỏi: '+names+'. Bạn muốn xem nhóm nào? Mình chưa tra tồn và vẫn giữ các điều kiện bạn đã gửi.'
    if state in ('available','partial_available'):
        n=len({r['product_id'] for r in report['variants'] if r['available'] is True})
        return 'Đã kiểm tra theo tiêu chí bạn hỏi: có '+str(n)+' mẫu còn hàng đã xác minh ở bên dưới. '+('Phạm vi tra chưa đầy đủ; không kết luận các mẫu khác hết hàng. ' if not report['complete'] else '')+'Chưa giữ hàng.'
    if state=='catalog_loading':return 'Danh mục đang đồng bộ. Chưa có kết quả tìm mẫu và tồn; không phải thông báo hết hàng.'
    if state=='metadata_missing':
        labels={'collection':'nhóm sản phẩm','heel_cm':'chiều cao gót','category':'kiểu giày','occasion':'dịp sử dụng'}
        missing={k for p in report['products'] if p['status']=='metadata_unverified' for k in labels if k in report['criteria'] and k not in p['verified_specs']}
        if report['coverage']['unknown_spec_products']:missing.update(k for k in labels if k in report['criteria'])
        if report.get('collection_status')=='resolved':missing.discard('collection')
        subject=', '.join(labels[k] for k in labels if k in missing) or 'size/màu của biến thể'
        return 'Merly chưa đủ dữ liệu đã xác minh về '+subject+' để chọn đúng yêu cầu. Các điều kiện bạn đã nói vẫn được giữ, mình chưa kết luận hết hàng. Bạn muốn [nhắn nhân viên Merly](https://oa.zalo.me/2969822963244380594) để được kiểm tra tiếp không?'
    if state=='source_error':return 'Đã tìm được ứng viên trong danh mục nhưng chưa kiểm tra xong dữ liệu hoặc tồn. Các mẫu chưa xác minh được ghi rõ bên dưới; không phải kết luận hết hàng.'
    if state=='verified_zero':return 'Các biến thể khớp yêu cầu đã kiểm tra có tồn 0 tại các kho trả đủ dữ liệu. Không kết luận toàn bộ website hoặc các mẫu chưa kiểm tra đều hết hàng.'
    if state=='partial':return 'Đã tìm được biến thể phù hợp nhưng tồn chưa được xác minh đầy đủ. Xem trạng thái từng mẫu bên dưới; chưa thể kết luận hết hàng.'
    return 'Chưa tìm thấy biến thể khớp yêu cầu trong danh mục và phạm vi đã kiểm tra. Không tự bỏ tiêu chí, không phải khẳng định toàn hệ thống hết hàng.'
