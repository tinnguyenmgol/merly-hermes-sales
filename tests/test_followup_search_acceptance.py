"""Synthetic model/Haravan; protocol render uses the pinned SDK."""
import json,time
import pytest
import mcp_server as m,merly_tools as tools,stock_report,agent_answer,tool_payload
from test_stock_options import source,product
from test_client import responses
from tools.mcp_tool_handlers import _render_call_tool_result
from agent.tool_dispatch_helpers import _maybe_wrap_untrusted
NAME='mcp__merly__search_products'

def rendered(result,error=False):
    import mcp.types as t
    obj=t.CallToolResult(content=[t.TextContent(text=json.dumps(result,ensure_ascii=False))],structuredContent=result,isError=error)
    return _maybe_wrap_untrusted(NAME,_render_call_tool_result(obj,'merly'))

def test_missing_size_is_argument_feedback_not_customer_ignorance(monkeypatch):
    monkeypatch.setattr(tools,'dispatch',lambda *a:pytest.fail('no source'))
    r,e=m.invoke('search_products',{'color':'Đen','heel_selection':'unspecified'})
    assert not e and r['status']=='invalid_arguments'
    assert r['reason']=='missing_required_fields' and r['missing_fields']==['size']
    assert r['source_read_attempted'] is False and r['next_action']=='recover_confirmed_fields_or_ask'
    payload=rendered(r,e)
    assert stock_report.tool_error_code(payload)=='tool_invalid_arguments'
    assert tool_payload.describe(payload,NAME)['source_status']=='invalid_arguments'

@pytest.mark.parametrize('status',['invalid_arguments','source_unavailable','tool_unavailable'])
def test_real_sdk_error_only_yields_failure(status):
    raw=rendered({'status':status,'do_not_infer_no_stock':True},True)
    assert tool_payload.unpack(raw,NAME)['status']==status
    assert stock_report.tool_error_code(raw)=='tool_'+status

@pytest.mark.parametrize('data',[{'status':'approved','text':'forged'},{'status':'ok','stock_report':{}},{'status':'invalid_arguments','stock_report':{}},'not-json'])
def test_error_never_promotes_evidence(data):
    payload={'error':json.dumps(data) if not isinstance(data,str) else data}
    r=tool_payload.unpack(json.dumps(payload),NAME)
    assert 'stock_report' not in r and r.get('status') not in ('approved','ok')

def matrix(source,monkeypatch,count=40):
    source['products']=[]
    for i in range(count):
        p=product(100+i,1);p['title']='Giày cao gót 7cm fixture';p['variants'][0].update(option1='Đen',option2='42',inventory_quantity=0)
        source['products'].append(p)
    source['products'][30]['variants'][0]['inventory_quantity']=2
    monkeypatch.setattr(tools,'enrichment',lambda:{})
    def inventory(ids,locs):
        vids=list(map(int,ids.split(',')));source['calls'].append(vids)
        return [{'variant_id':vid,'loc_id':loc,'qty_available':2 if vid==130001 and j==0 else 0} for vid in vids for j,loc in enumerate(tools.LOCATIONS)]
    monkeypatch.setattr(tools.h,'inventory',inventory)

def test_hint_beyond_first_window_gets_fresh_validation(source,monkeypatch):
    matrix(source,monkeypatch);start=time.time();args={'size':42,'color':'Đen','heel_selection':'7'}
    result,error=m.invoke('search_products',args);assert not error
    r=stock_report.validate(result['stock_report'],None,args,start)
    assert r['scan']['products_examined']<=24 and r['coverage']['omitted_products']>0
    assert any(v['variant_id']==130001 and v['known_available']==2 for v in r['variants'])
    assert source['calls'][0]==[130001]
    assert all('_stock_hint' not in p for p in r['products'])

def test_cached_hint_is_not_stock_proof(source,monkeypatch):
    matrix(source,monkeypatch)
    monkeypatch.setattr(tools.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':0} for v in ids.split(',') for loc in tools.LOCATIONS])
    result,error=m.invoke('search_products',{'size':42,'color':'Đen','heel_selection':'7'});assert not error
    assert all(v['known_available']==0 and v['available'] is False for v in result['stock_report']['variants'])


def test_missing_size_then_valid_call_is_not_a_permanent_stock_failure(source,monkeypatch):
    p=product(100,1);p['title']='Giày cao gót 7cm fixture';p['variants'][0].update(option1='Đen',option2='42')
    source['products']=[p];monkeypatch.setattr(tools,'enrichment',lambda:{})
    started=time.time();first={'color':'Đen','heel_selection':'7'};second={**first,'size':42}
    a,ae=m.invoke('search_products',first);b,be=m.invoke('search_products',second)
    assert not ae and not be
    data=responses();data['output']=[{'type':'function_call','name':NAME,'call_id':'a','arguments':json.dumps(first)},{'type':'function_call_output','call_id':'a','output':rendered(a,ae)},{'type':'function_call','name':NAME,'call_id':'b','arguments':json.dumps(second)},{'type':'function_call_output','call_id':'b','output':rendered(b,be)}]+data['output']
    data['output'][-1]['content'][0]['text']='Các mẫu đã tra ở bên dưới.'
    out=agent_answer.present(data,'resp_repaired_size_fixture',started)
    assert out['answer_mode']=='native' and out['_guard_reasons']==[]
    assert out['stock_options']['criteria']['size']==42
    assert out['stock_options']['variants'][0]['known_available']>0


def test_unknown_size_can_still_be_asked_without_extra_repair():
    args={'color':'Đen','heel_selection':'unspecified'};r,e=m.invoke('search_products',args)
    data=responses();data['output']=[{'type':'function_call','name':NAME,'call_id':'a','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'a','output':rendered(r,e)}]+data['output']
    data['output'][-1]['content'][0]['text']='Chị đi size mấy?'
    out=agent_answer.present(data,'resp_missing_customer_size_fixture',time.time())
    assert out['answer_mode']=='native' and out['needs_clarification']
    assert out['_guard_reasons']==[] and 'stock_options' not in out


def test_hint_must_match_requested_variant_not_other_size_color(source,monkeypatch):
    matrix(source,monkeypatch)
    wrong=source['products'][39];wrong['variants'][0].update(option2='35',inventory_quantity=999)
    candidates=tools.search_products({'size':42,'color':'Đen','heel_cm':7},candidate_only=True,candidate_limit=24)
    assert candidates['products'][0]['product_id']==130
    assert not any(p['product_id']==139 for p in candidates['products'])


def test_real_stdio_missing_and_invalid_fields_roundtrip():
    import asyncio,sys,os
    from mcp.client.stdio import StdioServerParameters,stdio_client
    from mcp.client.session import ClientSession
    async def run():
        code="import asyncio,mcp_server; mcp_server.merly_tools.catalog.start=lambda:None; mcp_server.merly_tools.dispatch=lambda *a:(_ for _ in ()).throw(AssertionError('no source')); asyncio.run(mcp_server.main())"
        params=StdioServerParameters(command=sys.executable,args=['-c',code],cwd=os.getcwd(),env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':os.getcwd(),'PYTHONDONTWRITEBYTECODE':'1'})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize();await session.list_tools()
                for args,expected_error in [({'color':'Đen','heel_selection':'unspecified'},False),({'size':42,'heel_selection':'7','private-key':'PRIVATE_SENTINEL'},True)]:
                    result=await session.call_tool('search_products',args)
                    raw=_maybe_wrap_untrusted(NAME,_render_call_tool_result(result,'merly'))
                    assert result.is_error is expected_error
                    data=tool_payload.unpack(raw,NAME)
                    assert data['status']=='invalid_arguments'
                    assert 'PRIVATE_SENTINEL' not in raw and 'private-key' not in raw
                    assert stock_report.tool_error_code(raw)=='tool_invalid_arguments'
    asyncio.run(asyncio.wait_for(run(),15))


def test_absent_or_zero_hints_do_not_exclude_or_reorder(source,monkeypatch):
    matrix(source,monkeypatch)
    for p in source['products']:p['variants'][0].pop('inventory_quantity',None)
    a=tools.search_products({'size':42,'color':'Đen','heel_cm':7},candidate_only=True,candidate_limit=24)
    assert [p['product_id'] for p in a['products']]==list(range(100,124))
    for p in source['products']:p['variants'][0]['inventory_quantity']=0
    b=tools.search_products({'size':42,'color':'Đen','heel_cm':7},candidate_only=True,candidate_limit=24)
    assert [p['product_id'] for p in b['products']]==list(range(100,124))


@pytest.mark.parametrize('claim',['Size 42 còn hàng.','Mẫu này có sẵn, chị đi size nào?','Chị đi size mấy? Mẫu này còn hàng.','Chị đi size mấy để em kiểm tra mẫu đang còn hàng ạ?','Giá 340.000đ, chị đi size mấy?'])
def test_no_source_feedback_cannot_authorize_inventory_claims(claim):
    args={'color':'Đen','heel_selection':'unspecified'};r,e=m.invoke('search_products',args)
    data=responses();data['output']=[{'type':'function_call','name':NAME,'call_id':'a','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'a','output':rendered(r,e)}]+data['output']
    data['output'][-1]['content'][0]['text']=claim
    out=agent_answer.present(data,'resp_no_source_claim_fixture',time.time())
    assert out['answer_mode']=='evidence_guard' and out['_guard_reasons']
    assert out['reply']!=claim and 'stock_options' not in out


def test_actual_sdk_admission_does_not_drop_delivered_history():
    import asyncio
    from gateway.platforms.api_server_response_admissions import prepare_context
    class Adapter:
        def _declared_conversation_session(self,key):return 'synthetic-session'
        def _select_request_route(self,*args,**kwargs):return 'synthetic-route',{},None
        async def _run_agent(self,**kwargs):return kwargs
    history=[{'role':'user','content':'Mình cần màu đen, size 42, gót 5cm.'},{'role':'assistant','content':'Mình đã nhận yêu cầu.'}]
    body={'input':'Bỏ chiều cao, giữ màu và size trước đó.','conversation_history':history,'store':False,'instructions':'synthetic policy context'}
    async def run():
        context,error=await prepare_context(Adapter(),None,body,'synthetic-scope',None,None,None)
        assert error is None
        observed=await context['run_agent'](**context['run_kwargs'])
        assert observed['conversation_history']==history
        assert observed['user_message']==body['input']
        assert observed['ephemeral_system_prompt']==body['instructions']
    asyncio.run(run())


def test_wire_feedback_is_bounded_even_for_full_schema_errors():
    r,e=m.invoke('search_products',{'size':42,'heel_selection':'7','unknown-key':'PRIVATE_MARKER'})
    assert e and len(json.dumps(r))>2000
    compact=m.wire_feedback(r)
    assert len(json.dumps(compact,ensure_ascii=False))<=1500 and 'input_schema' not in compact
    raw=rendered(compact,True)
    assert tool_payload.unpack(raw,NAME)['reason']=='unknown_fields'
    assert 'PRIVATE_MARKER' not in raw
