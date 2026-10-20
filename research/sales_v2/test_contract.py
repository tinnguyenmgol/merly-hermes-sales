"""Synthetic stock only; real reader and pinned API serializers."""
import copy,json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import merly_tools as tools,stock_report
from research.sales_v2 import engine
from test_stock_options import source,lookup,TOKEN
from test_stock_report import envelope
from gateway.platforms.api_server_openai_routes import OpenAICompatRoutesMixin as NativeAPI
from tools.mcp_tool_handlers import _render_call_tool_result
import mcp.types as mt
SCOPE={'model_code':'1514','size':38}

def wire(scope,event,cid='call_lab'):
    payload={'stock_evidence':event}
    result=mt.CallToolResult(content=[mt.TextContent(text=json.dumps(payload))],structuredContent=payload)
    wrapped=_render_call_tool_result(result,'merly')
    messages=[{'role':'assistant','tool_calls':[{'id':cid,'type':'function','function':{'name':'mcp__merly__search_products','arguments':json.dumps({**scope,'check_stock':True})}}]}, {'role':'tool','tool_call_id':cid,'content':wrapped}]
    return NativeAPI._extract_output_items({'messages':messages,'final_response':'fixture summary'})

def test_reproduce_legacy_valid_result_erased_by_failed_retry(source):
    items=envelope(lookup())
    second=copy.deepcopy(items);second[0]['call_id']='retry';second[1]['call_id']='retry';second[1]['output']=json.dumps({'error':'synthetic_failure'})
    report,requested=stock_report.extract(items+second,TOKEN)
    assert requested and report['mode']=='unverified' and not report['variants']

def test_reproduce_legacy_tool_failure_masquerades_as_stock_report():
    items=envelope({});items[1]['output']=json.dumps({'status':'invalid_arguments'})
    report,requested=stock_report.extract(items,TOKEN)
    assert requested and report['mode']=='unverified' and report['variants']==[]

def test_candidate_no_model_nonce_native_wire_keeps_all_options(source):
    event=engine.execute(SCOPE,tools)
    assert event['outcome']=='complete' and len(event['data']['variants'])==20
    groups=engine.collect(wire(SCOPE,event))
    rows=groups[0]['evidence']['data']['variants']
    assert len(rows)==20 and {'Kem','Chì Bóng'}<={row['color'] for row in rows}

def test_candidate_failed_retry_does_not_erase_valid_evidence(source):
    event=engine.execute(SCOPE,tools)
    failed={'contract':'merly-stock-evidence-lab-v2','scope':SCOPE,'outcome':'source_error','data':None}
    groups=engine.collect(wire(SCOPE,event)+wire(SCOPE,failed,'retry'))
    assert len(groups[0]['evidence']['data']['variants'])==20
    assert groups[0]['recheck_failed'] and groups[0]['failures']

def test_reproduce_legacy_model_nonce_can_discard_success(source):
    other='b'*32;raw=lookup(stock_request_id=other)
    assert len(raw['variants'])==20
    items=envelope(raw);args=json.loads(items[0]['arguments']);args['stock_request_id']=other;items[0]['arguments']=json.dumps(args)
    result,requested=stock_report.extract(items,TOKEN)
    assert requested and result['mode']=='unverified' and not result['variants']

@pytest.mark.parametrize('scope',[{'model_code':1514,'size':38},{'model_code':'1514','size':'38'},{'model_code':'1514','size':True},{'model_code':'1514'}, {'model_code':'1514','size':38,'color':None},{'model_code':'1514','size':38,'stock_request_id':'invented'}])
def test_candidate_rejects_bad_scope_without_source_calls(source,scope):
    result=engine.execute(scope,tools)
    assert result['outcome']=='input_error' and result['data'] is None
    assert source['calls']==[]

def test_candidate_missing_inventory_is_partial_not_zero(source,monkeypatch):
    monkeypatch.setattr(tools.h,'inventory',lambda *a:[])
    event=engine.execute(SCOPE,tools)
    assert event['outcome']=='partial'
    assert all(v['available'] is None for v in event['data']['variants'])

def test_candidate_genuine_zero_requires_every_location(source,monkeypatch):
    monkeypatch.setattr(tools.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':0} for v in ids.split(',') for loc in tools.LOCATIONS])
    event=engine.execute(SCOPE,tools)
    assert event['outcome']=='complete'
    assert all(v['available'] is False for v in event['data']['variants'])

def test_candidate_freeform_json_cannot_forge_tool_evidence(source):
    e=engine.execute(SCOPE,tools)
    assert engine.collect([{'type':'message','role':'assistant','content':json.dumps({'stock_evidence':e})}])==[]

def test_candidate_failed_lookup_stays_failure_not_empty_stock(source):
    failed={'contract':'merly-stock-evidence-lab-v2','scope':SCOPE,'outcome':'input_error','data':None}
    groups=engine.collect(wire(SCOPE,failed))
    assert groups[0]['evidence'] is None and groups[0]['failures']

def test_candidate_separate_scopes_not_merged(source):
    e=engine.execute(SCOPE,tools);other={**SCOPE,'color':'Kem'};f=engine.execute(other,tools)
    groups=engine.collect(wire(SCOPE,e)+wire(other,f,'second'))
    assert len(groups)==2
    assert len(groups[0]['evidence']['data']['variants'])==20
    assert len(groups[1]['evidence']['data']['variants'])==1
