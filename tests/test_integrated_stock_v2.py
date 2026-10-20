"""Synthetic sources, actual native Hermes serialization; no inference calls."""
import json,time
from datetime import datetime,timezone
import pytest
import merly_tools as t,stock_report as s,hermes_client as c
from test_stock_options import source
from test_client import approved
from gateway.platforms.api_server_openai_routes import OpenAICompatRoutesMixin as NativeAPI
from tools.mcp_tool_handlers import _render_call_tool_result
import mcp.types as mt
ARGS={'model_code':'1514','size':38,'check_stock':True}
def fresh():return t.dispatch('search_products',ARGS)['stock_report']
def wire(report,args=None,cid='native_case'):
    body={'stock_report':report}
    result=mt.CallToolResult(content=[mt.TextContent(text=json.dumps(body))],structuredContent=body)
    content=_render_call_tool_result(result,'merly')
    messages=[{'role':'assistant','tool_calls':[{'id':cid,'type':'function','function':{'name':'mcp__merly__search_products','arguments':json.dumps(args or ARGS)}}]},{'role':'tool','tool_call_id':cid,'content':content}]
    return NativeAPI._extract_output_items({'messages':messages,'final_response':'synthetic model omitted colors'})

def test_server_creates_metadata_no_model_copy(source):
    start=time.time();r=fresh()
    assert r['schema']=='merly-stock-options-v2' and len(r['stock_request_id'])==32
    result,requested=s.extract(wire(r),'unrelated-gateway-id',turn_started=start)
    assert requested and result['complete'] and len(result['variants'])==20
    assert fresh()['stock_request_id']!=r['stock_request_id']

@pytest.mark.parametrize('delta',[-3600,3600])
def test_stale_or_future_evidence_not_accepted(source,delta):
    start=time.time();r=fresh();r['checked_at']=datetime.fromtimestamp(start+delta,timezone.utc).isoformat()
    result,_=s.extract(wire(r),'unused',turn_started=start)
    assert result['operation_status']=='failed' and result['reason_code']=='stale_evidence'

def test_missing_current_turn_boundary_fails_closed(source):
    r,_=s.extract(wire(fresh()),'unused')
    assert r['operation_status']=='failed' and r['reason_code']=='missing_turn_boundary'

def test_wrong_scope_and_orphan_outputs_do_not_cross(source):
    start=time.time();items=wire(fresh(),args={**ARGS,'size':39})
    r,_=s.extract(items,'unused',turn_started=start);assert r['operation_status']=='failed'
    assert s.extract([items[1]],'unused',turn_started=start)==(None,False)

def test_retry_failure_preserves_but_marks_previous_evidence(source):
    start=time.time();items=wire(fresh());bad=wire(fresh(),cid='retry');bad[1]['output']='{"status":"invalid_arguments"}'
    r,_=s.extract(items+bad,'unused',turn_started=start)
    assert len(r['variants'])==20 and r['recheck_failed'] and not r['complete']
    assert 'không phải xác nhận tồn mới' in s.summary(r)

def test_valid_retry_recovers_after_failure(source):
    start=time.time();bad=wire(fresh(),cid='bad');bad[1]['output']='invalid json'
    r,_=s.extract(bad+wire(fresh()),'unused',turn_started=start)
    assert r['complete'] and not r.get('recheck_failed')

def test_duplicate_call_id_cannot_replace_scope(source):
    start=time.time();r,_=s.extract(wire(fresh())+wire(fresh()),'unused',turn_started=start)
    assert r['operation_status']=='failed'

def test_completed_client_independent_of_model_color_summary(source,approved,monkeypatch):
    monkeypatch.setattr(c,'audit',lambda:True)
    def request(path,payload):
        assert 'Mã lượt tra tồn hiện tại:' not in payload['instructions']
        assert 'Không gửi stock_request_id' in payload['instructions']
        return {'status':'completed','id':'resp_native_case','output':wire(fresh())}
    monkeypatch.setattr(c,'request',request)
    r=c.chat('synthetic availability request','synthetic-scope')
    assert 'omitted colors' not in r['reply']
    assert {'Kem','Chì Bóng'}<={v['color'] for v in r['stock_options']['variants']}

def test_source_error_is_not_empty_success(source,monkeypatch,caplog):
    def fail(*a):raise t.h.HaravanError('haravan_http_403')
    monkeypatch.setattr(t.h,'get',fail);start=time.time()
    r,_=s.extract(wire(fresh()),'unused',turn_started=start)
    assert r['operation_status']=='source_error' and not r['complete']
    assert 'haravan_http_403' in caplog.text and 'chưa trả đủ' in s.summary(r)

def test_mcp_error_envelope_retains_safe_classification(source):
    start=time.time();items=wire(fresh())
    items[1]['output']=json.dumps({'error':json.dumps({'status':'invalid_arguments','reason':'invalid_size','private':'must-not-log-fixture'})})
    r,_=s.extract(items,'unused',turn_started=start)
    assert r['operation_status']=='failed' and r['reason_code']=='tool_invalid_arguments'

def test_current_turn_legacy_metadata_does_not_require_model_copy(source):
    start=time.time();args={**ARGS,'stock_request_id':'b'*32}
    r=t.dispatch('search_products',args)['stock_report']
    result,_=s.extract(wire(r,args=args),'different-private-gateway-id',turn_started=start)
    assert result['complete'] and len(result['variants'])==20
    r['stock_request_id']='c'*32
    result,_=s.extract(wire(r,args=args),'unused',turn_started=start)
    assert result['operation_status']=='failed'

def test_unknown_variant_metadata_does_not_erase_known_options(source):
    source['products'][0]['variants'][0]['option2']=None
    source['products'][0]['variants'][0]['title']='unknown-size'
    start=time.time();r,_=s.extract(wire(fresh()),'unused',turn_started=start)
    assert not r['complete'] and len(r['variants'])==19
    assert r['coverage']['unclassified_variants']==1
    assert {'Kem','Chì Bóng'}<={v['color'] for v in r['variants']}

def test_other_numeric_size_does_not_poison_requested_scope(source):
    source['products'][0]['variants'][0]['option2']='44'
    start=time.time();r,_=s.extract(wire(fresh()),'unused',turn_started=start)
    assert r['complete'] and len(r['variants'])==19
