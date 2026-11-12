"""Pinned MCP rendering + scripted provider, NOT a live/NLP score."""
import asyncio,copy,json,time
import pytest
import mcp.types as mt
import merly_tools as tools,mcp_server as server,hermes_client as client
from tool_evidence import usable
from tool_payload import unpack
from agent_answer import present
from agent.tool_dispatch_helpers import _maybe_wrap_untrusted
from tools.mcp_tool_handlers import _render_call_tool_result,_result_is_error
from agent.tool_guardrails import classify_tool_failure
from test_client import approved,responses
NAME='mcp__merly__get_promotions'
TEXT='Em có thể tư vấn chính sách tài khoản đã duyệt; chiến dịch bổ sung cho đơn của chị vẫn cần kiểm tra riêng.'
CONTROL={'status':'publication_not_configured','offers':[],'shop_has_no_offers':False}

@pytest.fixture
def unpublished(tmp_path,monkeypatch):
    p=tmp_path/'public.json';p.write_text(json.dumps({'approved':False,'promotions':[],'discounts':[]}))
    monkeypatch.setattr(tools.promotions,'CONFIG',p)
    monkeypatch.setattr(tools.h,'get',lambda *a:pytest.fail('no upstream read when unpublished'))

def trace(data=CONTROL,name=NAME,args=None,render=False):
    out=responses();out['output'][-1]['content'][0]['text']=TEXT
    raw=json.dumps(data,ensure_ascii=False)
    if render:
        r=mt.CallToolResult(content=[mt.TextContent(text=raw)],structuredContent=data,isError=False)
        raw=_maybe_wrap_untrusted(name,_render_call_tool_result(r,'merly'))
    out['output'][:0]=[{'type':'function_call','call_id':'promo','name':name,'arguments':json.dumps({} if args is None else args)},{'type':'function_call_output','call_id':'promo','output':raw}]
    return out

def test_real_callback_native_wire_preserves_valid_no_data(unpublished):
    r=asyncio.run(server.call_tool(None,mt.CallToolRequestParams(name='get_promotions',arguments={})))
    assert not r.is_error and r.structured_content==CONTROL
    raw=_render_call_tool_result(r,'merly');assert not _result_is_error(raw)
    raw=_maybe_wrap_untrusted(NAME,raw);assert not classify_tool_failure(NAME,raw)[0]
    assert unpack(raw,NAME)==CONTROL
    d=trace();d['output'][1]['output']=raw
    assert usable(d['output'][0],d['output'][1],time.time())
    a=present(d,'resp_promo',time.time())
    assert a['reply']==TEXT and a['answer_mode']=='native' and not a['_guard_reasons']
    assert a['_tool_diagnostics'][0]['source_status']=='publication_not_configured'
    assert 'stock_options' not in a and 'quotes' not in a

@pytest.mark.parametrize('message',['hiện đang có chương trình khuyến mãi gì','shop có ưu đãi nào','khách mới được gì','có chương trình khác không'])
def test_no_phrase_shortcut_or_repair_for_valid_control(approved,unpublished,monkeypatch,message):
    import state
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');monkeypatch.setattr(client,'audit',lambda:True)
    monkeypatch.setattr(state,'reserve_checked',lambda *a:pytest.fail('must not open repair'))
    seen=[]
    def request(path,payload):seen.append(copy.deepcopy(payload));return trace(render=True)
    monkeypatch.setattr(client,'request',request)
    a=client.chat(message,'merly-sales:web:promo-fixture')
    assert len(seen)==1 and seen[0]['input']==message
    assert a['reply']==TEXT and a['_repair_attempts']==0 and not a['_guard_reasons']

@pytest.mark.parametrize('change',[
 {'offers':[{'label':'UNAPPROVED'}]},{'offers':None},{'offers':{}},
 {'shop_has_no_offers':True},{'shop_has_no_offers':0},{'shop_has_no_offers':'false'},
 {'eligibility_confirmed':True},{'stacking_confirmed':True},
 {'stock_report':{}},{'products':[{'product_id':1}]},{'price_vnd':100},
 {'status':'source_unavailable'},{'status':'tool_unavailable'},{'status':'unverified'}])
def test_control_does_not_authorize_offers_claims_or_source_failures(change):
    d=trace({**CONTROL,**change},render=True)
    assert not usable(d['output'][0],d['output'][1],time.time())
    a=present(d,'resp_rejected',time.time())
    assert 'rejected_tool_evidence' in a['_guard_reasons'] and a['answer_mode']=='evidence_guard'

@pytest.mark.parametrize('args',[{'extra':1},{'topic':'shipping'}])
def test_control_cannot_hide_invalid_arguments(args):
    d=trace(args=args)
    assert not usable(d['output'][0],d['output'][1],time.time())

@pytest.mark.parametrize('name',['mcp__merly__get_policy','mcp__merly__size_guide','mcp__merly__search_products','mcp__merly__quote_variant'])
def test_control_is_scoped_to_its_own_tool(name):
    d=trace(name=name)
    assert not usable(d['output'][0],d['output'][1],time.time())


def test_no_data_error_envelope_is_not_reinterpreted_as_business_control():
    d=trace();d['output'][1]['output']=json.dumps({'error':json.dumps(CONTROL)})
    assert not usable(d['output'][0],d['output'][1],time.time())


def test_approved_policy_and_unpublished_campaign_catalog_can_coexist():
    d=trace(render=True);policy=tools.get_policy({'topic':'new_customer'})
    assert policy['status']=='approved'
    extra=trace(policy,'mcp__merly__get_policy',{'topic':'new_customer'},render=True)['output'][:2]
    for row in extra:row['call_id']='account-policy'
    d['output'][2:2]=extra
    a=present(d,'resp_mixed',time.time())
    assert not a['_guard_reasons'] and a['reply']==TEXT and a['_policy_topics']==['new_customer']


def test_valid_control_does_not_hide_another_corrupt_output():
    d=trace(render=True)
    d['output'][2:2]=[{'type':'function_call','call_id':'bad','name':'mcp__merly__get_policy','arguments':'{"topic":"shipping"}'},{'type':'function_call_output','call_id':'bad','output':'{'}]
    a=present(d,'resp_corrupt',time.time())
    assert 'rejected_tool_evidence' in a['_guard_reasons']


def test_wsgi_does_not_turn_valid_control_into_generic_fallback(configured,unpublished,monkeypatch,caplog):
    from test_gateway import call
    import logging
    seen=[];monkeypatch.setattr(client,'audit',lambda:True)
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1')
    def request(path,payload):seen.append(copy.deepcopy(payload));return trace(render=True)
    monkeypatch.setattr(client,'request',request)
    message='hiện đang có chương trình khuyến mãi gì'
    with caplog.at_level(logging.INFO,logger='merly.gateway'):out=call(message)
    assert out['status']=='200 OK' and len(seen)==1
    assert out['body']['reply']==TEXT and out['body']['answer_mode']=='native'
    assert out['body']['engine']=='hermes' and not out['body']['lookup_incomplete']
    assert len(out['body']['diagnostic_id'])==16
    assert 'publication_not_configured' in caplog.text and message not in caplog.text
    assert not any(k.startswith('_') for k in out['body'])

from test_gateway import configured
