"""Stock-first MCP contract; synthetic sources, no paid model calls."""
import copy,json,time
import pytest
import merly_tools as t,mcp_server as m,stock_report as stock
from agent_answer import present
from customer_listing import project
from test_stock_options import source
from test_client import responses
from tool_evidence import usable
from test_integrated_stock_v2 import wire

def items(data,args,text):
    d=responses();d['output'][-1]['content'][0]['text']=text
    calls=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'policy','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'policy','output':json.dumps(data)}]
    d['output']=calls+d['output'];return d

@pytest.mark.parametrize('args',[{}, {'color':'Đen','heel_cm':5}, {'check_stock':True,'query':'giày'}, {'occasion':'đi làm','limit':4}])
def test_missing_size_returns_no_candidates_and_never_reads_source(monkeypatch,args):
    monkeypatch.setattr(t,'dispatch',lambda *a:pytest.fail('must not read source'))
    before=copy.deepcopy(args);data,error=m.invoke('search_products',args)
    assert not error and args==before
    assert data['status']=='needs_clarification' and data['missing_fields']==['size']
    assert data['products']==[] and data['stock_checked'] is False and data['source_read_attempted'] is False
    assert stock.clarification_request(data,args)

@pytest.mark.parametrize('flag',[None,True])
def test_confirmed_size_gets_stock_and_gate_accepts_default(source,flag):
    args={'model_code':'1514','size':38}
    if flag is not None:args['check_stock']=flag
    before=copy.deepcopy(args);began=time.time();data,error=m.invoke('search_products',args)
    assert not error and args==before and data['stock_report']['variants']
    assert source['calls']
    actual=wire(data['stock_report'],args=args)
    report,requested=stock.extract(actual,None,turn_started=began)
    assert requested and report['complete'] and report['variants']
    assert usable(actual[0],actual[1],began)
    view=project(present(items(data,args,'Chị muốn xem kỹ lựa chọn nào?'),'resp_policy',began))
    assert view['answer_mode']=='native' and view['listing']['shown']==4

@pytest.mark.parametrize('args',[{'check_stock':False},{'check_stock':False,'size':38}])
def test_false_mode_is_rejected_not_silently_repaired(monkeypatch,args):
    monkeypatch.setattr(t,'dispatch',lambda *a:pytest.fail('source read forbidden'))
    before=copy.deepcopy(args);data,error=m.invoke('search_products',args)
    assert error and data['reason']=='stock_check_required' and args==before
    assert 'products' not in data

@pytest.mark.parametrize('question',['Chị đi size mấy để em kiểm tra mẫu còn hàng ạ?', 'Bạn cho em biết size để em đối chiếu nhé.'])
@pytest.mark.parametrize('args',[{}, {'check_stock':True}])
def test_missing_customer_info_is_not_invalid_inventory(question,args):
    began=time.time();data,error=m.invoke('search_products',args);assert not error
    d=items(data,args,question)
    assert usable(d['output'][0],d['output'][1],began)
    assert stock.extract(d['output'],None,turn_started=began)==(None,False)
    view=project(present(d,'resp_missing',began))
    assert view['reply']==question and view['needs_clarification'] and view['answer_mode']=='native'
    assert view['listing']['shown']==0 and 'stock_options' not in view

@pytest.mark.parametrize('change',[
 {'missing_fields':['color']},{'source_read_attempted':True},
 {'source_read_attempted':0},{'stock_checked':True},
 {'stock_checked':0},{'products':[{'product_id':123}]},
 {'stock_report':{}},{'source_links':['https://example.invalid']},
 {'next_action':'buy_now'},{'status':'ok'}])
def test_clarification_is_not_a_backdoor_for_arbitrary_payload(change):
    data,error=m.invoke('search_products',{});assert not error
    data.update(change)
    assert not stock.clarification_request(data,{})
    d=items(data,{},'UNSUPPORTED_ASSERTION')
    assert not usable(d['output'][0],d['output'][1],time.time())

@pytest.mark.parametrize('args',[{'size':'42'},{'size':True},{'size':99},{'size':None},{'check_stock':'true'}])
def test_defaults_do_not_repair_malformed_customer_values(monkeypatch,args):
    monkeypatch.setattr(t,'dispatch',lambda *a:pytest.fail('no source access'))
    before=copy.deepcopy(args);data,error=m.invoke('search_products',args)
    assert error and args==before and data['status']=='invalid_arguments'


def test_customer_stock_schema_has_one_supported_mode():
    schema=m.DEFINITIONS['search_products']['requestBody']['content']['application/json']['schema']
    assert schema['properties']['check_stock']['default'] is True
    assert schema['properties']['check_stock']['enum']==[True]


def test_internal_candidate_retrieval_stays_catalog_only(source,monkeypatch):
    monkeypatch.setattr(t.h,'inventory',lambda *a:pytest.fail('catalog phase must not read stock'))
    found=t.search_products({'model_code':'1514','size':38},candidate_only=True,candidate_limit=4)
    assert found['products'] and found['stock_checked'] is False

@pytest.mark.parametrize('args',[{}, {'check_stock':True}])
def test_actual_mcp_result_and_pinned_native_wire_preserve_clarification(args):
    import asyncio,mcp.types as mt
    from tools.mcp_tool_handlers import _render_call_tool_result
    from gateway.platforms.api_server_openai_routes import OpenAICompatRoutesMixin as NativeAPI
    began=time.time()
    result=asyncio.run(m.call_tool(None,mt.CallToolRequestParams(name='search_products',arguments=args)))
    assert not result.is_error and result.structured_content['status']=='needs_clarification'
    rendered=_render_call_tool_result(result,'merly')
    question='Chị đi size mấy để em kiểm tra mẫu còn hàng ạ?'
    messages=[{'role':'assistant','tool_calls':[{'id':'native_missing','type':'function','function':{'name':'mcp__merly__search_products','arguments':json.dumps(args)}}]},{'role':'tool','tool_call_id':'native_missing','content':rendered}]
    output=NativeAPI._extract_output_items({'messages':messages,'final_response':question})
    d={'output':output}
    view=project(present(d,'resp_native_missing',began))
    assert view['reply']==question and view['needs_clarification']
    assert view['answer_mode']=='native' and view['listing']['shown']==0
    assert view['_guard_reasons']==[]


def test_default_public_search_vs_legacy_catalog_reproduces_logged_mismatch(source):
    args={'model_code':'1514','size':38}
    legacy=t.dispatch('search_products',args)
    assert legacy['status']=='ok' and legacy['products'] and 'stock_report' not in legacy
    assert not source['calls']
    current,error=m.invoke('search_products',args)
    assert not error and current['stock_report']['variants'] and source['calls']


def test_default_stock_does_not_drop_any_confirmed_criterion(monkeypatch):
    seen=[]
    monkeypatch.setattr(t,'dispatch',lambda name,args:seen.append(copy.deepcopy(args)) or {})
    args={'size':42,'heel_cm':5,'color':'Đen','occasion':'đi làm','category':'cao gót','query':'giày','limit':4}
    _,error=m.invoke('search_products',args)
    assert not error and seen==[{**args,'check_stock':True}]
    assert 'check_stock' not in args
