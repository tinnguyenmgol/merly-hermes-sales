"""Current-turn tool provenance and deterministic stock presentation; no prose parsing."""
import json,re
from urllib.parse import urlsplit
class InvalidReport(ValueError):pass

def decode(value):
    for _ in range(5):
        if isinstance(value,str):
            if len(value)>220000:raise InvalidReport('too_large')
            value=json.loads(value);continue
        if isinstance(value,list):
            if len(value)!=1 or not isinstance(value[0],dict):raise InvalidReport('unsupported_blocks')
            value=value[0].get('text');continue
        if isinstance(value,dict) and 'stock_report' in value:return value['stock_report']
        if isinstance(value,dict) and 'structuredContent' in value:value=value['structuredContent'];continue
        if isinstance(value,dict) and 'result' in value:value=value['result'];continue
        raise InvalidReport('not_a_report')
    raise InvalidReport('too_deep')

def safe_url(value):
    if value is None:return None
    if not isinstance(value,str):raise InvalidReport('invalid_url')
    u=urlsplit(value)
    if u.scheme!='https' or u.netloc!='merlyshoes.com' or not re.fullmatch(r'/products/[A-Za-z0-9_-]+',u.path) or u.query or u.fragment:raise InvalidReport('invalid_product_link')
    return value

def validate(report,request_id,args):
    if not isinstance(report,dict) or report.get('schema')!='merly-stock-options-v1' or report.get('stock_request_id')!=request_id:raise InvalidReport('wrong_turn')
    if report.get('model_code')!=args.get('model_code') or report.get('size')!=args.get('size'):raise InvalidReport('wrong_scope')
    if not isinstance(report.get('model_code'),str) or not 1<=len(report['model_code'])<=32 or type(report.get('size')) is not int or not 35<=report['size']<=43:raise InvalidReport('invalid_scope')
    if report.get('color_filter')!=args.get('color'):raise InvalidReport('wrong_color_scope')
    if report.get('color_filter') is not None and (not isinstance(report['color_filter'],str) or not 1<=len(report['color_filter'])<=40):raise InvalidReport('invalid_color_scope')
    rows=report.get('variants');coverage=report.get('coverage')
    if report.get('mode')!='all_options' or type(report.get('complete')) is not bool or not isinstance(rows,list) or len(rows)>100 or not isinstance(coverage,dict):raise InvalidReport('invalid_shape')
    for k in ['candidate_products','products_checked','variants_found','variants_checked','unverified_products','omitted_variants']:
        if type(coverage.get(k)) is not int or coverage[k]<0:raise InvalidReport('invalid_count')
    cleaned=[];seen=set();checked=0
    for row in rows:
        if not isinstance(row,dict):raise InvalidReport('invalid_variant')
        for k in ['product_id','variant_id']:
            if type(row.get(k)) is not int or not 1<=row[k]<10**16:raise InvalidReport('invalid_identity')
        if row['variant_id'] in seen:raise InvalidReport('duplicate_variant')
        seen.add(row['variant_id'])
        if row.get('size')!=str(report['size']):raise InvalidReport('wrong_size')
        color=row.get('color');price=row.get('price_vnd');known=row.get('known_available');complete=row.get('inventory_complete');available=row.get('available')
        if color is not None and (not isinstance(color,str) or len(color)>255):raise InvalidReport('invalid_color')
        if price is not None and (type(price) is not int or not 0<=price<=9007199254740991):raise InvalidReport('invalid_price')
        if type(known) is not int or not 0<=known<=9007199254740991 or type(complete) is not bool or (available is not None and type(available) is not bool):raise InvalidReport('invalid_inventory')
        locations=row.get('locations')
        if not isinstance(locations,list) or len(locations)!=3:raise InvalidReport('invalid_locations')
        names=set();quantities=[]
        for loc in locations:
            if not isinstance(loc,dict) or not isinstance(loc.get('name'),str) or len(loc['name'])>120 or loc['name'] in names:raise InvalidReport('invalid_location')
            names.add(loc['name']);qty=loc.get('available')
            if qty is not None and (type(qty) is not int or not 0<=qty<=9007199254740991):raise InvalidReport('invalid_quantity')
            quantities.append(qty)
        if sum(q for q in quantities if q is not None)!=known or complete!=all(q is not None for q in quantities):raise InvalidReport('inconsistent_inventory')
        if available!=(True if known>0 else False if complete else None):raise InvalidReport('inconsistent_available')
        checked+=int(complete)
        cleaned.append({k:row.get(k) for k in ['product_id','variant_id','color','size','price_vnd','available','known_available','inventory_complete','locations']})
        cleaned[-1]['product_url']=safe_url(row.get('product_url'))
    if coverage['variants_checked']!=checked or coverage['variants_found']!=len(rows)+coverage['omitted_variants'] or coverage['candidate_products']!=coverage['products_checked']+coverage['unverified_products']:raise InvalidReport('inconsistent_coverage')
    age=report.get('catalog_age_seconds')
    if report['complete'] and (not coverage['candidate_products'] or coverage['unverified_products'] or coverage['omitted_variants'] or checked!=len(rows) or type(age) not in (int,float) or not 0<=age<=300):raise InvalidReport('false_complete')
    return {'mode':'all_options','model_code':report['model_code'],'size':report['size'],'color_filter':report.get('color_filter'),'complete':report['complete'],'coverage':coverage,'variants':cleaned}

def unverified(args):
    result={'mode':'unverified','complete':False,'variants':[]}
    if isinstance(args.get('model_code'),str) and 1<=len(args['model_code'])<=32:result['model_code']=args['model_code']
    if type(args.get('size')) is int and 35<=args['size']<=43:result['size']=args['size']
    if isinstance(args.get('color'),str) and len(args['color'])<=40:result['color_filter']=args['color']
    return result

def extract(items,request_id):
    calls={};reports={}
    for item in items:
        if not isinstance(item,dict):continue
        call_id=item.get('call_id')
        if not isinstance(call_id,str):continue
        if item.get('type')=='function_call' and item.get('name')=='mcp__merly__search_products':
            try:args=json.loads(item.get('arguments','{}')) if isinstance(item.get('arguments'),str) else item.get('arguments')
            except (ValueError,TypeError):continue
            if isinstance(args,dict) and args.get('check_stock') is True:calls[call_id]=args
        elif item.get('type')=='function_call_output' and item.get('status') in (None,'completed') and call_id in calls and calls[call_id].get('stock_request_id')==request_id:
            try:reports[call_id]=validate(decode(item.get('output')),request_id,calls[call_id])
            except (ValueError,TypeError,KeyError):continue
    if not calls:return None,False
    grouped={}
    for call_id,args in calls.items():
        report=reports.get(call_id) or unverified(args)
        grouped[(report.get('model_code'),report.get('size'),report.get('color_filter'))]=report
    values=list(grouped.values())
    return (values[0] if len(values)==1 else {'mode':'groups','groups':values}),True

def summary(report):
    if report['mode']=='groups':return 'Có '+str(len(report['groups']))+' phạm vi mẫu/size trong lượt tra này. Xem từng bảng bên dưới; bảng kiểm tra chưa đủ không phải kết luận hết hàng.'
    if report['mode']=='unverified':return 'Chưa nhận được bảng tồn đầy đủ đã xác minh cho lượt hỏi này. Em chưa thể kết luận mẫu hết hàng hoặc chỉ còn một số màu.'
    positive=sum(r['available'] is True for r in report['variants'])
    scope='Mẫu '+report['model_code']+', size '+str(report['size'])
    if report.get('color_filter'):scope+=', màu '+report['color_filter']
    if report['complete']:
        if positive:return scope+': có '+str(positive)+' lựa chọn còn hàng đã xác minh. Danh sách ở bên dưới; chưa giữ hàng.'
        if not report['variants']:return scope+': không thấy biến thể phù hợp trong các sản phẩm đã kiểm tra; không phải kết luận các size khác hết hàng.'
        return scope+': các biến thể đã kiểm tra đều có tồn 0 tại các kho đã trả đủ dữ liệu. Chưa kiểm tra size khác.'
    return scope+': mới xác minh được một phần. Danh sách bên dưới có '+str(positive)+' lựa chọn còn hàng đã xác minh, nhưng chưa phải toàn bộ; không kết luận các lựa chọn chưa kiểm tra là hết hàng.'
