"""Preserve native language; gate evidence, not intent. No hidden lookup/rewrite."""
from stock_report import extract,summary
from source_links import collect
import re,unicodedata
from decimal import Decimal,InvalidOperation
FAILURE='Mình chưa xác minh được dữ liệu cho lượt này nên chưa thể kết luận còn hay hết hàng. Bạn không cần nhập lại các điều kiện đã gửi; mình có thể hướng dẫn liên hệ nhân viên Merly để kiểm tra tiếp.'

def verified(report):
    if report.get('mode')=='groups':return all(verified(r) for r in report['groups'])
    return report.get('mode') in ('all_options','discovery') and report.get('complete') is True and not report.get('recheck_failed') and report.get('operation_status') in ('complete','available','verified_zero','no_match')

def risky_stock_wording(text,report):
    # Output evidence guard, never customer-phrase routing. Exhaustive/global
    # claims are intentionally left to the bounded deterministic evidence view.
    n=''.join(c for c in unicodedata.normalize('NFD',text.casefold().replace('đ','d')) if unicodedata.category(c)!='Mn')
    if re.search(r'\b(?:only|sole|chi|duy nhat|toan he thong|toan bo|tat ca|het hang|sold out|out of stock)\b',n):return True
    reports=report.get('groups',[report])
    prices={row.get('price_vnd') for r in reports for row in r.get('variants',[]) if type(row.get('price_vnd')) is int}
    for amount,k in re.findall(r'(?<!\w)([0-9]+(?:[.,][0-9]+)*)(k)?\s*(?:đ(?:ồng)?|vnd|₫)(?!\w)',text.casefold()):
        try:
            if k and not re.fullmatch(r'[0-9]+(?:[.,][0-9]{1,2})?',amount):return True
            value=Decimal(amount.replace(',','.'))*1000 if k else Decimal(amount.replace('.','').replace(',',''))
        except InvalidOperation:return True
        if value not in prices:return True
    return False

def present(data,rid,started):
    from hermes_client import HermesError,EXPECTED
    items=data.get('output')
    if not isinstance(items,list) or len(items)>128:raise HermesError('invalid_response')
    calls={};duplicates=set();outputs={}
    for item in items:
        if not isinstance(item,dict):raise HermesError('invalid_response')
        cid=item.get('call_id')
        if item.get('type')=='function_call':
            if item.get('name') not in EXPECTED:raise HermesError('unsafe_enabled_toolset')
            if not isinstance(cid,str) or not cid:raise HermesError('invalid_response')
            if cid in calls:duplicates.add(cid)
            calls[cid]=item
        elif item.get('type')=='function_call_output':
            if not isinstance(cid,str) or not cid:raise HermesError('invalid_response')
            if cid in outputs:duplicates.add(cid)
            outputs[cid]=item
    final=[i for i in items if i.get('type')=='message' and i.get('role','assistant')=='assistant' and i.get('phase') in (None,'final_answer')]
    if not final:raise HermesError('missing_final_message')
    content=final[-1].get('content')
    if not isinstance(content,list):raise HermesError('invalid_answer')
    text=''.join(p['text'] for p in content if isinstance(p,dict) and p.get('type')=='output_text' and isinstance(p.get('text'),str))
    if not text.strip() or len(text)>12000:raise HermesError('invalid_answer')
    from tool_evidence import repaired_rejections,usable
    repaired=repaired_rejections(calls,outputs,started)
    execution=[item for item in items if item.get('call_id') not in repaired]
    report,requested=extract(execution,None,turn_started=started)
    invalid=any(not usable(call,outputs.get(cid,{}),started) for cid,call in calls.items() if cid not in repaired)

    body={'reply':text,'conversation_id':rid,'source_links':collect(items),'model_called':True,'answer_mode':'native'}
    from catalog_view import collect as catalog_cards,quotes as quote_cards
    products=catalog_cards(calls,outputs,duplicates)
    if products:body['products']=products
    quotes=quote_cards(calls,outputs,duplicates,started)
    if quotes:body['quotes']=quotes
    body['_tools_used']=list(dict.fromkeys(c['name'] for c in calls.values()))
    body['_policy_topics']=[]
    import json,policy_knowledge
    for call in calls.values():
        if call['name']!='mcp__merly__get_policy':continue
        try:
            args=json.loads(call.get('arguments','{}')) if isinstance(call.get('arguments'),str) else call.get('arguments',{})
            topic=args.get('topic')
            if topic in policy_knowledge.TOPICS:body['_policy_topics'].append(topic)
        except (ValueError,TypeError,AttributeError):pass
    missing=bool(duplicates or set(outputs)-set(calls) or set(calls)-set(outputs))
    if requested:
        body['stock_options']=report
        if missing or invalid or not verified(report) or risky_stock_wording(text,report):
            body.update(reply=summary(report) if report.get('mode')!='unverified' else FAILURE,
                        lookup_incomplete=bool(missing or invalid or not verified(report)),answer_mode='evidence_guard')
    elif quotes and not missing and not invalid and risky_stock_wording(text,{'variants':quotes}):
        body.update(reply='Mình đã gửi thông tin biến thể đã tra trong thẻ bên dưới; chưa giữ hàng.',answer_mode='evidence_guard')
    elif missing or invalid:
        body.update(reply='Mình chưa lấy được dữ liệu hợp lệ để trả lời chắc chắn lượt này. Bạn không cần nhập lại thông tin đã gửi; có thể nhờ nhân viên Merly kiểm tra tiếp.',lookup_incomplete=True,answer_mode='evidence_guard')
    return body
