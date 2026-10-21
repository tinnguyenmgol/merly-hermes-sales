"""Current-turn tool provenance and deterministic stock presentation; no prose parsing."""
import json,re,time,logging
from datetime import datetime
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

def clean_variant(row,size):
    if not isinstance(row,dict):raise InvalidReport('invalid_variant')
    for k in ('product_id','variant_id'):
        if type(row.get(k)) is not int or not 1<=row[k]<10**16:raise InvalidReport('invalid_identity')
    if row.get('size')!=str(size):raise InvalidReport('wrong_size')
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
    result={k:row.get(k) for k in ('product_id','variant_id','color','size','price_vnd','available','known_available','inventory_complete','locations')}
    result['product_url']=safe_url(row.get('product_url'))
    return result

def validate(report,request_id,args,turn_started=None):
    if isinstance(report,dict) and report.get('schema')=='merly-product-discovery-v1':
        import product_discovery
        return product_discovery.validate(report,args,turn_started)
    if not isinstance(report,dict):raise InvalidReport('invalid_shape')
    version=report.get('schema')
    if version=='merly-stock-options-v2' or (version=='merly-stock-options-v1' and turn_started is not None):
        if version=='merly-stock-options-v1' and report.get('stock_request_id')!=args.get('stock_request_id'):raise InvalidReport('wrong_turn')
        operation_id=report.get('stock_request_id')
        if not isinstance(operation_id,str) or not re.fullmatch(r'[0-9a-f]{32}',operation_id):raise InvalidReport('invalid_operation_id')
        if type(turn_started) not in (int,float):raise InvalidReport('missing_turn_boundary')
        try:
            checked=datetime.fromisoformat(report['checked_at'].replace('Z','+00:00'))
            if checked.tzinfo is None:raise ValueError()
            timestamp=checked.timestamp()
        except (KeyError,ValueError,TypeError,AttributeError,OverflowError):raise InvalidReport('invalid_checked_at')
        if not turn_started-3<=timestamp<=time.time()+3:raise InvalidReport('stale_evidence')
    elif report.get('schema')!='merly-stock-options-v1' or report.get('stock_request_id')!=request_id:raise InvalidReport('wrong_turn')
    if report.get('model_code')!=args.get('model_code') or report.get('size')!=args.get('size'):raise InvalidReport('wrong_scope')
    if not isinstance(report.get('model_code'),str) or not 1<=len(report['model_code'])<=32 or type(report.get('size')) is not int or not 35<=report['size']<=43:raise InvalidReport('invalid_scope')
    if report.get('color_filter')!=args.get('color'):raise InvalidReport('wrong_color_scope')
    if report.get('color_filter') is not None and (not isinstance(report['color_filter'],str) or not 1<=len(report['color_filter'])<=40):raise InvalidReport('invalid_color_scope')
    rows=report.get('variants');coverage=report.get('coverage')
    if report.get('mode')!='all_options' or type(report.get('complete')) is not bool or not isinstance(rows,list) or len(rows)>100 or not isinstance(coverage,dict):raise InvalidReport('invalid_shape')
    for k in ['candidate_products','products_checked','variants_found','variants_checked','unverified_products','omitted_variants']:
        if type(coverage.get(k)) is not int or coverage[k]<0:raise InvalidReport('invalid_count')
    if 'unclassified_variants' in coverage and (type(coverage['unclassified_variants']) is not int or not 0<=coverage['unclassified_variants']<=2000):raise InvalidReport('invalid_count')
    if report['complete'] and coverage.get('unclassified_variants',0):raise InvalidReport('false_complete')
    cleaned=[];seen=set();checked=0
    for row in rows:
        item=clean_variant(row,report['size'])
        if item['variant_id'] in seen:raise InvalidReport('duplicate_variant')
        seen.add(item['variant_id']);checked+=int(item['inventory_complete']);cleaned.append(item)
    if coverage['variants_checked']!=checked or coverage['variants_found']!=len(rows)+coverage['omitted_variants'] or coverage['candidate_products']!=coverage['products_checked']+coverage['unverified_products']:raise InvalidReport('inconsistent_coverage')
    age=report.get('catalog_age_seconds')
    if report['complete'] and (not coverage['candidate_products'] or coverage['unverified_products'] or coverage['omitted_variants'] or checked!=len(rows) or type(age) not in (int,float) or not 0<=age<=300):raise InvalidReport('false_complete')
    issues=[]
    for entry in report.get('issues',[])[:30]:
        if isinstance(entry,dict) and entry.get('stage') in ('product_variants','inventory'):
            code=entry.get('code')
            allowed={'missing_access_token','haravan_unavailable','variant_count_changed_or_incomplete','variant_lookup_budget_exceeded','variant_size_metadata_unverified','variant_color_metadata_unverified'}
            if isinstance(code,str) and (code in allowed or re.fullmatch(r'haravan_http_[1-5][0-9]{2}',code)):issues.append({'stage':entry['stage'],'code':code})
            else:issues.append({'stage':entry['stage'],'code':'source_unavailable'})
    return {'mode':'all_options','model_code':report['model_code'],'size':report['size'],'color_filter':report.get('color_filter'),'complete':report['complete'],'coverage':coverage,'variants':cleaned,'checked_at':report.get('checked_at'),'issues':issues,'source_status':'catalog_loading' if report.get('status')=='catalog_loading' else 'ready'}

def unverified(args):
    result={'mode':'unverified','complete':False,'variants':[]}
    if isinstance(args.get('model_code'),str) and 1<=len(args['model_code'])<=32:result['model_code']=args['model_code']
    if type(args.get('size')) is int and 35<=args['size']<=43:result['size']=args['size']
    if isinstance(args.get('color'),str) and len(args['color'])<=40:result['color_filter']=args['color']
    return result

def classify(report):
    if report.get('mode')=='discovery':
        import product_discovery
        return product_discovery.classify(report)
    status='complete' if report['complete'] else 'partial'
    if report.get('source_status')=='catalog_loading':status='catalog_loading'
    elif report.get('issues') and not any(v['available'] is True or v['inventory_complete'] for v in report['variants']):status='source_error'
    elif not report['variants'] and report['coverage']['candidate_products']==0:status='no_match'
    report['operation_status']=status
    for entry in report.get('issues',[]):logging.getLogger('merly.stock').warning('MERLY_SOURCE_ISSUE stage=%s reason=%s',entry['stage'],entry['code'])
    return report

def tool_error_code(value):
    for _ in range(8):
        if isinstance(value,str):
            if len(value)>220000:return None
            try:value=json.loads(value)
            except (ValueError,TypeError):return None
            continue
        if isinstance(value,list) and len(value)==1 and isinstance(value[0],dict):value=value[0].get('text');continue
        if isinstance(value,dict):
            status=value.get('status')
            if status in ('invalid_arguments','source_unavailable','tool_unavailable'):return 'tool_'+status
            for key in ('error','structuredContent','result'):
                if key in value:value=value[key];break
            else:return None
            continue
        return None
    return None

def extract(items,request_id,turn_started=None):
    calls={};reports={};failures={};duplicates=set()
    for item in items:
        if not isinstance(item,dict):continue
        cid=item.get('call_id')
        if not isinstance(cid,str) or not cid:continue
        if item.get('type')=='function_call' and item.get('name')=='mcp__merly__search_products':
            try:args=json.loads(item.get('arguments','{}')) if isinstance(item.get('arguments'),str) else item.get('arguments')
            except (ValueError,TypeError):continue
            if isinstance(args,dict) and args.get('check_stock') is True:
                if cid in calls:duplicates.add(cid)
                calls[cid]=args
        elif item.get('type')=='function_call_output' and cid in calls:
            try:
                if item.get('status') not in (None,'completed'):raise InvalidReport('tool_not_completed')
                report=decode(item.get('output'))
                if report.get('schema')=='merly-stock-options-v1' and turn_started is None and calls[cid].get('stock_request_id')!=request_id:raise InvalidReport('wrong_turn')
                reports[cid]=validate(report,request_id,calls[cid],turn_started)
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                failures[cid]=tool_error_code(item.get('output')) or (str(exc) if isinstance(exc,InvalidReport) else 'invalid_tool_output')
    if not calls:return None,False
    grouped={}
    for cid,args in calls.items():
        good=reports.get(cid) if cid not in duplicates else None
        failed=unverified(args)
        if good and good.get('mode')=='discovery' or 'model_code' not in args or any(k in args for k in ('heel_cm','category','occasion')):
            import product_discovery
            key=('discovery',json.dumps(product_discovery.criteria(args),sort_keys=True))
        else:key=(failed.get('model_code'),failed.get('size'),failed.get('color_filter'))
        if good:
            classify(good)
            grouped[key]=good
        else:
            code=failures.get(cid,'duplicate_call_id' if cid in duplicates else 'missing_tool_output')
            allowed={'tool_invalid_arguments','tool_source_unavailable','tool_tool_unavailable','wrong_turn','stale_evidence','missing_turn_boundary','invalid_operation_id','invalid_checked_at','invalid_tool_output','tool_not_completed','missing_tool_output','duplicate_call_id','not_a_report','inconsistent_coverage','invalid_product_link','wrong_scope','wrong_size','wrong_color_scope','inconsistent_inventory','false_complete'}
            code=code if code in allowed else 'invalid_stock_contract'
            logging.getLogger('merly.stock').warning('MERLY_STOCK_REJECTED reason=%s',code)
            if key in grouped and grouped[key].get('mode') in ('all_options','discovery'):
                grouped[key].update(complete=False,recheck_failed=True,operation_status='partial',reason_code=code)
                if grouped[key]['mode']=='discovery':classify(grouped[key])
            else:
                failed.update(operation_status='failed',reason_code=code);grouped[key]=failed
    values=list(grouped.values())
    return (values[0] if len(values)==1 else {'mode':'groups','groups':values}),True

def summary(report):
    if report.get('mode')=='discovery':
        import product_discovery
        return product_discovery.summary(report)
    if report['mode']=='groups':return 'Có '+str(len(report['groups']))+' phạm vi mẫu/size trong lượt tra này. Xem từng bảng bên dưới; bảng kiểm tra chưa đủ không phải kết luận hết hàng.'
    if report.get('operation_status')=='no_match':return 'Chưa tìm thấy mẫu phù hợp trong danh mục đã đồng bộ. Cần kiểm tra lại mã mẫu; đây không phải kết luận hết hàng.'
    if report.get('operation_status')=='catalog_loading':return 'Danh mục sản phẩm đang đồng bộ từ Haravan; lượt này chưa có kết quả tra tồn. Không phải thông báo hết hàng.'
    if report.get('operation_status')=='source_error':return 'Haravan chưa trả đủ dữ liệu hợp lệ để xác nhận tồn cho lượt này. Nếu có danh sách màu bên dưới thì đó mới là thông tin biến thể, chưa xác nhận còn hàng.'
    if report['mode']=='unverified':return 'Lượt tra tồn chưa hoàn tất do lỗi công cụ hoặc dữ liệu trả về không hợp lệ. Đây không phải kết quả hết hàng; chưa xác định được các màu còn.'
    if report.get('recheck_failed'):return 'Lần kiểm tra lại chưa thành công. Bên dưới giữ kết quả đã xác minh trước đó trong lượt hỏi này, không phải xác nhận tồn mới; chưa giữ hàng.'
    positive=sum(r['available'] is True for r in report['variants'])
    scope='Mẫu '+report['model_code']+', size '+str(report['size'])
    if report.get('color_filter'):scope+=', màu '+report['color_filter']
    if report['complete']:
        if positive:return scope+': có '+str(positive)+' lựa chọn còn hàng đã xác minh. Danh sách ở bên dưới; chưa giữ hàng.'
        if not report['variants']:return scope+': không thấy biến thể phù hợp trong các sản phẩm đã kiểm tra; không phải kết luận các size khác hết hàng.'
        return scope+': các biến thể đã kiểm tra đều có tồn 0 tại các kho đã trả đủ dữ liệu. Chưa kiểm tra size khác.'
    return scope+': mới xác minh được một phần. Danh sách bên dưới có '+str(positive)+' lựa chọn còn hàng đã xác minh, nhưng chưa phải toàn bộ; không kết luận các lựa chọn chưa kiểm tra là hết hàng.'
