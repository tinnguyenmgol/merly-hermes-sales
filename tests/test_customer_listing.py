"""Display policy only; all stock inputs synthetic, not live inventory."""
import copy,json
import pytest
import customer_listing as v
from test_gateway import configured

def row(id,qty=1,color='Đen',size='42'):
    return {'product_id':100+id,'variant_id':id,'known_available':qty,'available':qty>0,'size':size,'color':color,'product_url':'https://merlyshoes.com/products/fixture-'+str(id)}
def report(rows,**extra):return {'mode':'discovery','criteria':{'size':42,'color':'Đen'},'variants':rows,'products':[],'complete':True,'coverage':{'catalog_matches':30},**extra}

@pytest.mark.parametrize('qty',[0,-1,None,True,1.0,'1'])
def test_hide_zero_unknown_invalid_quantities(qty):
    body=v.project({'reply':'fixture','stock_options':report([row(1,1),{**row(2),'known_available':qty}])})
    assert [r['variant_id'] for r in body['stock_options']['variants']]==[1]

def test_cap_dedupe_and_do_not_mutate_evidence():
    answer={'reply':'fixture','stock_options':report([row(i) for i in range(1,21)]),'quotes':[row(18)],'products':[{'title':'unchecked'}]}
    original=copy.deepcopy(answer);out=v.project(answer)
    assert answer==original and len(answer['stock_options']['variants'])==20
    shown=out.get('quotes',[])+v.positive_rows(out.get('stock_options'))
    assert len(shown)==4 and len({r['variant_id'] for r in shown})==4 and shown[0]['variant_id']==18
    assert out['listing']['verified_positive_skus']==20 and out['listing']['has_more']
    assert out['stock_options']['coverage']==original['stock_options']['coverage']
    assert out['stock_options']['view_mode']=='verified_positive_subset' and 'products' not in out

def test_no_empty_panels_and_no_unverified_links():
    out=v.project({'reply':'fixture','stock_options':report([row(1,0)]),'products':[{'title':'unknown'}],'quotes':[row(2,0)],'source_links':['https://merlyshoes.com/products/fixture-1','https://merlyshoes.com/']})
    assert not any(k in out for k in ('stock_options','products','quotes'))
    assert out['source_links']==['https://merlyshoes.com/'] and out['listing']['shown']==0

def test_wrong_color_quote_hidden_even_when_positive():
    out=v.project({'reply':'fixture','stock_options':report([],criteria={'size':42,'color':'Trắng'}),'quotes':[row(2,5,'Kem Sữa'),row(3,1,'Trắng')]})
    assert [r['variant_id'] for r in out['quotes']]==[3]

def test_positive_partial_inventory_can_be_shown():
    out=v.project({'reply':'fixture','stock_options':report([row(1,2)],complete=False)})
    assert out['listing']['shown']==1 and not out['stock_options']['complete']

def test_wrong_size_or_color_stock_rows_cannot_leak():
    out=v.project({'reply':'fixture','stock_options':report([row(1,1,'Kem Sữa'),row(2,1,'Đen','40'),row(3,1)])})
    assert [r['variant_id'] for r in out['stock_options']['variants']]==[3]

def test_unverified_product_link_in_prose_is_guarded():
    from agent_answer import present
    import time
    data={'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'Xem mẫu https://merlyshoes.com/products/unverified-fixture'}]}]}
    out=present(data,'resp_fixture',time.time())
    assert out['answer_mode']=='evidence_guard' and 'unverified_product_listing' in out['_guard_reasons']
    assert 'https://merlyshoes.com/products/' not in out['reply']

def test_public_history_only_contains_displayed_positive_skus(configured,monkeypatch):
    import hermes_client as c,dialogue,state
    from test_gateway import call
    monkeypatch.setattr(c,'chat',lambda *a:{'reply':'fixture','conversation_id':'resp_listing','stock_options':report([row(i) for i in range(1,21)])})
    out=call('Tìm mẫu phù hợp')
    cookie=out['headers']['Set-Cookie'].split(';')[0];_,sid=state.identity(cookie)
    replay=dialogue.history(sid)[1]['content']
    assert '"variant_id":1' in replay and '"variant_id":5' not in replay
    assert '"verified_positive_skus":20' in replay
    assert out['body']['listing']['shown']==4 and out['body']['listing']['verified_positive_skus']==20

def test_only_operational_fallbacks_are_shortened_not_native_speech():
    answer={'reply':'CUSTOM_NATIVE_QUESTION','stock_options':report([row(1)])}
    assert v.project(answer)['reply']=='CUSTOM_NATIVE_QUESTION'
    answer['answer_mode']='evidence_guard'
    assert v.project(answer)['reply']=='Các lựa chọn bên dưới đã xác minh có tồn; chưa giữ hàng.'
    answer['stock_options']=report([row(1,0)])
    assert v.project(answer)['reply']=='Chưa xác minh được mẫu có tồn đúng yêu cầu trong lượt này.'

def test_no_dangling_card_message_when_zero_quote_is_hidden():
    out=v.project({'reply':'Mình đã gửi thẻ bên dưới','answer_mode':'evidence_guard','quotes':[row(1,0)]})
    assert 'quotes' not in out and 'bên dưới' not in out['reply'] and out['listing']['shown']==0
