"""Prompt delivery/evidence wiring only; NOT real-model sales quality."""
import copy
import pytest
import hermes_client as c
from test_client import approved,responses
from test_stock_options import source
from test_integrated_stock_v2 import wire,fresh
from customer_listing import project


def final(text):
    data=responses();data['output'][-1]['content'][0]['text']=text;return data


def test_guidance_delivered_without_new_tool_or_router(approved,monkeypatch):
    seen=[];monkeypatch.setattr(c,'audit',lambda:True)
    monkeypatch.setattr(c,'request',lambda path,p:seen.append(copy.deepcopy(p)) or final('Chị muốn em giải thích thêm điều gì ạ?'))
    raw='Mình đang cân nhắc mua, tư vấn giúp nhé'
    c.chat(raw,'merly-sales:web:guidance')
    assert len(seen)==1 and seen[0]['input']==raw
    prompt=seen[0]['instructions']
    assert '## Tư vấn tự nhiên và mời khách đi tiếp' in prompt
    assert 'không tạo đơn hay giữ hàng' in prompt
    assert 'không xin điện thoại/địa chỉ' in prompt
    assert 'link sản phẩm từ nguồn/thẻ' in prompt
    assert 'KHÔNG phải dữ kiện hàng hóa hay câu bắt buộc' in prompt
    assert len(c.EXPECTED)==5 and not any('order' in name for name in c.EXPECTED)

@pytest.mark.parametrize('text',[
 'Em đã tìm được lựa chọn trong các thẻ. Chị muốn chọn một mẫu hay xem thêm ạ?',
 'Chị muốn em giúp so sánh kiểu dáng trước khi chọn không ạ?',
 'Chị có thể mở link sản phẩm trong thẻ để đặt trên website ạ.',
])
def test_verified_native_advice_and_invitation_survive(source,approved,monkeypatch,text):
    monkeypatch.setattr(c,'audit',lambda:True)
    def request(path,payload):
        data=final(text);data['output']=wire(fresh())[:2]+data['output'];return data
    monkeypatch.setattr(c,'request',request)
    result=project(c.chat('Giúp mình chọn mẫu phù hợp','merly-sales:web:choose'))
    assert result['reply']==text and result['answer_mode']=='native'
    assert result['listing']['shown']==4
    assert all(r['known_available']>0 for r in result['stock_options']['variants'])


def test_guidance_does_not_replace_unverified_listing_guard(approved,monkeypatch):
    monkeypatch.setattr(c,'audit',lambda:True)
    text='Chị đặt ngay mẫu https://merlyshoes.com/products/unverified-example nhé?'
    monkeypatch.setattr(c,'request',lambda *a:final(text))
    result=project(c.chat('Muốn mua ngay','merly-sales:web:guard'))
    assert result['reply']!=text and result['answer_mode']=='evidence_guard'
    assert result['listing']['shown']==0
