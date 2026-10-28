"""Synthetic regressions; NOT live-model acceptance results."""
import copy,json,time,unicodedata
import pytest
from agent_answer import present,risky_stock_wording
from clarification import only_question
from customer_listing import project
from test_client import responses,approved
from test_gateway import configured,call
from test_stock_options import source
from test_integrated_stock_v2 import wire,fresh

def output(text,tool_output=None,args=None):
    d=responses();d['output'][-1]['content'][0]['text']=text
    if tool_output is not None:
        d['output']=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'ask','arguments':json.dumps(args or {'check_stock':True})},{'type':'function_call_output','call_id':'ask','output':json.dumps(tool_output)}]+d['output']
    return d

@pytest.mark.parametrize('question',[
 'Chị đi size mấy để em kiểm tra đúng yêu cầu ạ?',
 'Bạn muốn chọn màu nào?',
 'Chị thích gót thấp hay gót cao?',
 'Bạn nói rõ hơn giúp mình nhé.',
 'Chị cho em biết size thường đi nhé.',
 'Em chưa đối chiếu được chiều cao gót. Chị muốn nhân viên kiểm tra giúp không?',
 'Would you prefer flats or heels?',
])
@pytest.mark.parametrize('failure',[{'status':'invalid_arguments','reason':'stock_scope_required'},{'status':'source_unavailable'},{}])
def test_question_survives_unverified_evidence_without_cards(question,failure):
    d=output(question,failure);before=copy.deepcopy(d)
    a=present(d,'resp_question',time.time());view=project(a)
    assert d==before and a['reply']==view['reply']==question
    assert a['needs_clarification'] and a['answer_mode']=='native' and a['_guard_reasons']==[]
    assert a['_deferred_guard_reasons'] and a['_lookup_diagnostics']
    assert not any(k in view for k in ('stock_options','products','quotes'))
    assert view['listing']['shown']==0

@pytest.mark.parametrize('claim',[
 'Size này còn hàng, chị đi size mấy?',
 'Chỉ còn một màu. Chị muốn màu nào?',
 'Giá 399k, chị chọn size nào?',
 'Giá 399.000đ. Chị chọn size nào?',
 'Mẫu này có sẵn. Chị đi size nào?',
 'Size 42 hiện còn. Chị lấy không?',
 'Mẫu này còn size 42, chị muốn màu gì?',
 'Có 9 đôi. Chị chọn mẫu nào?',
 'In stock, which color?',
 'See https://merlyshoes.com/products/unchecked. Which size?',
 'Mình gửi các thẻ bên dưới. Chị chọn nhé?',
 '<tool_call>bad</tool_call> Chị đi size mấy?',
])
def test_question_mark_never_excuses_unverified_claim(claim):
    assert not only_question(claim)
    a=project(present(output(claim,{'status':'source_unavailable'}),'resp_claim',time.time()))
    assert a['reply']!=claim and a['answer_mode'] in ('evidence_guard','protocol_guard')
    assert not a.get('needs_clarification') and a['listing']['shown']==0

@pytest.mark.parametrize('address',['Chị','chị','CHỊ',unicodedata.normalize('NFD','Chị')])
def test_vietnamese_address_is_not_exclusivity(address):
    assert not risky_stock_wording(address+' muốn xem mẫu nào?',{'variants':[]})

@pytest.mark.parametrize('text',['Chỉ còn một màu','chỉ có mẫu này','Only one color','Hết hàng toàn hệ thống'])
def test_exclusivity_guard_remains(text):
    assert risky_stock_wording(text,{'variants':[]})

def test_positive_source_cards_and_native_address_are_preserved(source):
    d=output('Chị muốn xem kỹ lựa chọn nào?');d['output']=wire(fresh())[:2]+d['output']
    a=project(present(d,'resp_positive',time.time()))
    assert a['answer_mode']=='native' and a['reply']=='Chị muốn xem kỹ lựa chọn nào?'
    assert a['listing']['shown']==4 and all(r['known_available']>0 for r in a['stock_options']['variants'])

def test_gateway_delivers_question_and_replays_only_delivered_history(configured,monkeypatch):
    import hermes_client as c
    monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,p):
        seen.append(copy.deepcopy(p))
        return output('Chị đi size mấy?',{'status':'invalid_arguments','reason':'stock_scope_required'}) if len(seen)==1 else output('Chị muốn nhân viên đối chiếu chiều cao gót giúp không?')
    monkeypatch.setattr(c,'request',request)
    a=call('Tư vấn đôi phù hợp');cookie=a['headers']['Set-Cookie'].split(';')[0]
    b=call('42',cookie=cookie)
    assert len(seen)==2 and a['body']['reply']=='Chị đi size mấy?' and a['body']['needs_clarification']
    assert seen[1]['conversation_history'][1]['content']=='Chị đi size mấy?'
    assert not any(k.startswith('_') for k in a['body'])
    assert b['status'].startswith('200')

def test_missing_size_is_actionable_not_a_source_failure(monkeypatch):
    import mcp_server as m
    monkeypatch.setattr(m.merly_tools.h,'get',lambda *a,**k:pytest.fail('must not read source'))
    result,error=m.invoke('search_products',{'check_stock':True,'color':'Đen','heel_cm':5})
    assert not error and result['missing_fields']==['size']
    assert result['status']=='needs_clarification' and result['source_read_attempted'] is False

@pytest.mark.parametrize('args',[{'check_stock':True,'size':'42'},{'check_stock':True,'size':True},{'check_stock':True,'size':99}])
def test_invalid_type_is_not_mislabeled_customer_missing_information(args):
    import mcp_server as m
    result,error=m.invoke('search_products',args)
    assert error and 'needs_clarification' not in result

@pytest.mark.parametrize('tool',['get_policy','get_promotions','size_guide','quote_variant'])
def test_stock_question_gate_does_not_relax_other_tool_validation(tool):
    d=output('Đổi trả 30 ngày. Chị cần hỏi gì thêm?',{'status':'source_unavailable'})
    d['output'][0]['name']='mcp__merly__'+tool
    a=present(d,'resp_policy',time.time())
    assert a['answer_mode']=='evidence_guard' and a['_guard_reasons']
    assert '30 ngày' not in a['reply']

def test_preserved_question_has_only_bounded_diagnostics_in_logs(configured,monkeypatch,caplog):
    import logging,hermes_client as c
    monkeypatch.setattr(c,'audit',lambda:True)
    monkeypatch.setattr(c,'request',lambda *a:output('Chị muốn làm rõ lựa chọn nào?',{'status':'source_unavailable'}))
    with caplog.at_level(logging.INFO,logger='merly.gateway'):a=call('CUSTOMER_PRIVATE_SENTINEL')
    assert a['body']['needs_clarification'] and a['body']['answer_mode']=='native'
    assert 'deferred_guard_reasons' in caplog.text and 'CUSTOMER_PRIVATE_SENTINEL' not in caplog.text
    assert 'Chị muốn làm rõ' not in caplog.text

def test_question_gate_never_changes_customer_message(configured,monkeypatch):
    import hermes_client as c
    seen=[]
    monkeypatch.setattr(c,'chat',lambda m,*a:seen.append(m) or {'reply':'NATIVE','conversation_id':'resp_input'})
    raw='Giày lạ gì đó, không phải màu cũ — sz 42 mja'
    call(raw)
    assert seen==[raw]
