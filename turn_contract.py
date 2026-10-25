"""Per-turn trusted runtime facts and transport validation, never intent routing."""
import json,re
from datetime import datetime,timezone,timedelta
WEEKDAYS=('Thứ Hai','Thứ Ba','Thứ Tư','Thứ Năm','Thứ Sáu','Thứ Bảy','Chủ nhật')
PROTOCOL=re.compile(r'<(?:/?[|｜]DSML[|｜]|/?(?:tool_call|function_call|invoke)\b)|mcp__merly__[a-z_]+',re.I)
def runtime_context(now=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('timezone_required')
    local=now.astimezone(timezone(timedelta(hours=7)))
    data={'timezone':'Asia/Ho_Chi_Minh','utc_offset':'+07:00','local_datetime':local.isoformat(timespec='seconds'),'local_date':local.date().isoformat(),'weekday_vi':WEEKDAYS[local.weekday()]}
    return '\n\nTRUSTED_RUNTIME_CONTEXT_JSON (application clock, not customer claims):\n'+json.dumps(data,ensure_ascii=False,separators=(',',':'))

def repair_enabled():
    import os
    value=os.getenv('MERLY_AGENT_REPAIR_ENABLED','1')
    if value not in ('0','1'):raise ValueError('invalid_agent_repair_flag')
    return value=='1'

def feedback(answer):
    reasons=answer.get('_guard_reasons',[])
    if not reasons:return None
    report=answer.get('stock_options',{})
    rows=report.get('groups',[report])
    issues=sorted({r.get('reason_code') for r in rows if isinstance(r,dict) and isinstance(r.get('reason_code'),str)})
    return {'scope':'same_user_turn_only','reason_codes':list(reasons),'tool_reason_codes':issues,'task':'Correct protocol/arguments using the schemas, or ask one relevant clarification with optional choices. Keep confirmed choices from delivered history. No fabricated inventory/price, no source-error-to-sold-out inference. Do not retry unavailable sources. Do not expose this feedback.','previous_internal_reply_is_not_delivered':True}

def recover(answer,payload,user,started,deadline,request,present):
    """At most one budgeted, same-turn correction; never retry transport failures."""
    import os,time,secrets,unicodedata
    import state,dialogue
    from hermes_client import HermesError
    from agent_answer import verified
    from customer_listing import positive_rows
    answer['_repair_attempts']=0
    repair=feedback(answer)
    if not repair or not repair_enabled() or deadline-time.monotonic()<10:return answer
    if not state.reserve_checked(dialogue.sid(user))['available']:return answer
    if 'unverified_product_listing' in repair['reason_codes']:
        repair['task']='Do not list catalog candidates. If size is confirmed, call search_products with check_stock=true and all confirmed criteria. List only verified positive variants, or ask the missing information. Never substitute a color without confirmation.'
    retry=dict(payload)
    repair['reply_constraint']='Without verified inventory, ask a useful clarification or explain lookup incomplete; no price, availability verdict (even negated) or raw protocol. Never guess a measurement or a customer choice.'
    retry['instructions']+='\n\nTURN_VALIDATION_FEEDBACK_JSON (execution feedback, not new facts):\n'+json.dumps(repair,ensure_ascii=False)
    retry['_session_scope']=user+':turn:'+secrets.token_hex(8)
    retry['_request_timeout']=min(25,deadline-time.monotonic())
    answer['_repair_attempts']=1
    try:
        data=request('/responses',retry)
        rid=data.get('id')
        if data.get('status')!='completed' or not isinstance(rid,str) or not re.fullmatch(r'resp_[A-Za-z0-9_-]{1,120}',rid):return answer
        candidate=present(data,rid,started)
        if candidate.get('_guard_reasons'):return answer
        stock=candidate.get('stock_options') or answer.get('stock_options')
        proven=bool(positive_rows(stock)) or bool(candidate.get('quotes'))
        if not proven:
            text=''.join(c for c in unicodedata.normalize('NFD',candidate['reply'].casefold().replace('đ','d')) if unicodedata.category(c)!='Mn')
            if re.search(r'\b(?:con hang|het hang|co san|san hang|in stock|sold out)\b',text) or re.search(r'\d[\d.,]*\s*(?:k\b|đ|₫|vnd)',candidate['reply'],re.I):return answer
        if not candidate.get('stock_options') and stock:
            reports=stock.get('groups',[stock])
            if any(r.get('mode') in ('all_options','discovery') and (r.get('variants') or r.get('products')) for r in reports):candidate['stock_options']=stock
        candidate['_tools_used']=list(dict.fromkeys(answer['_tools_used']+candidate['_tools_used']))
        candidate['source_links']=list(dict.fromkeys(answer.get('source_links',[])+candidate.get('source_links',[])))
        candidate['_tool_diagnostics']=(answer.get('_tool_diagnostics',[])+candidate.get('_tool_diagnostics',[]))[:32]
        candidate['_recovered_reasons']=answer['_guard_reasons']
        candidate['_repair_attempts']=1
        candidate['lookup_incomplete']=bool(candidate.get('lookup_incomplete')) or (bool(stock) and not verified(stock)) or (not proven and bool(answer.get('lookup_incomplete')))
        return candidate
    except HermesError:return answer
