"""Allowlisted learning metadata. No customer text/IDs/URLs/credentials accepted."""
import re,json
FIELDS=('query','collection','collection_hint','model_code','size','color','heel_cm','category','occasion','check_stock','limit')
TOOLS=tuple('mcp__merly__'+n for n in ('search_products','quote_variant','get_policy','get_promotions','size_guide'))
REASONS=('incomplete_tool_trace','rejected_tool_evidence','unverified_inventory','unsupported_stock_claim','unsupported_spec_claim','wrong_selection_scope','too_many_product_listings','unverified_product_listing','protocol_text','invalid_dialogue_contract','staff_reported','hermes_timeout','hermes_unavailable','turn_not_completed','pilot_unavailable','other_failure')
STATUSES=('approved','reference_only','ok','partial_metadata','partial_inventory','needs_staff_review','needs_staff_confirmation','needs_clarification','invalid_arguments','source_unavailable','tool_unavailable','unverified','publication_not_configured','unknown')
OUTCOMES=('guarded','failed','staff_marked')
KEYS={'diagnostic_id','outcome','reason_codes','criterion_fields','tools','tool_statuses'}
class InvalidEvent(ValueError):pass

def validate(event):
    if not isinstance(event,dict) or set(event)!=KEYS:raise InvalidEvent('invalid_event_shape')
    if not isinstance(event['diagnostic_id'],str) or not re.fullmatch('[0-9a-f]{16}',event['diagnostic_id']):raise InvalidEvent('invalid_diagnostic_id')
    if event['outcome'] not in OUTCOMES:raise InvalidEvent('invalid_outcome')
    for key,allowed in (('reason_codes',REASONS),('criterion_fields',FIELDS),('tools',TOOLS),('tool_statuses',STATUSES)):
        values=event[key]
        if not isinstance(values,list) or len(values)>len(allowed) or any(not isinstance(v,str) or v not in allowed for v in values) or len(set(values))!=len(values):raise InvalidEvent('invalid_metadata')
    return {k:sorted(v) if isinstance(v,list) else v for k,v in event.items()}

def pick(values,allowed):
    return sorted({v for v in values if isinstance(v,str) and v in allowed}) if isinstance(values,list) else []

def capture(diagnostic_id,answer,trace=None,failure=None):
    trace=trace if isinstance(trace,dict) else {};answer=answer if isinstance(answer,dict) else {}
    reasons=pick(trace.get('guard_reasons',[]),REASONS)
    if failure:reasons=pick([failure if failure in REASONS else 'other_failure'],REASONS)
    if not reasons and not failure and answer.get('answer_mode') not in ('evidence_guard','protocol_guard'):return None
    lookups=trace.get('lookup_diagnostics',[]);lookups=lookups if isinstance(lookups,list) else []
    diagnostics=trace.get('tool_diagnostics',[]);diagnostics=diagnostics if isinstance(diagnostics,list) else []
    fields=[]
    for row in lookups[:8]+diagnostics[:32]:
        if isinstance(row,dict):
            for key in ('criteria_fields','argument_fields'):fields+=pick(row.get(key,[]),FIELDS)
    return validate({'diagnostic_id':diagnostic_id,'outcome':'failed' if failure else 'guarded','reason_codes':reasons,'criterion_fields':pick(fields,FIELDS),'tools':pick(trace.get('tools_used',[]),TOOLS),'tool_statuses':pick([r.get('source_status') for r in diagnostics[:32] if isinstance(r,dict)],STATUSES)})

def json_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise InvalidEvent('duplicate_key')
        result[key]=value
    return result
