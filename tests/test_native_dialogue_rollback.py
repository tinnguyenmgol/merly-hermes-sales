"""Regression: native prose must not require an invented JSON envelope.
These are scripted wire checks, NOT a score of the real model's understanding.
"""
import copy,json,time
import pytest
import hermes_client as c
from agent_answer import present
from customer_listing import project
from test_client import approved,responses
from test_stock_options import source

@pytest.mark.parametrize('old_flag',[None,'0','1'])
@pytest.mark.parametrize('reply',['Bạn muốn kiểu giày nào để mình tư vấn đúng nhu cầu?','Mình chưa hiểu rõ nhu cầu của bạn. Bạn nói rõ hơn giúp mình nhé.'])
def test_native_reply_is_not_blocked_by_removed_contract(approved,monkeypatch,old_flag,reply):
    if old_flag is None:monkeypatch.delenv('MERLY_DIALOGUE_CONTRACT_ENABLED',raising=False)
    else:monkeypatch.setenv('MERLY_DIALOGUE_CONTRACT_ENABLED',old_flag)
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,payload):
        seen.append(copy.deepcopy(payload));d=responses();d['output'][-1]['content'][0]['text']=reply;return d
    monkeypatch.setattr(c,'request',request)
    answer=c.chat('RAW_CUSTOMER_MESSAGE','merly-sales:web:'+'a'*64)
    assert answer['reply']==reply and answer['answer_mode']=='native'
    assert answer['_guard_reasons']==[] and len(seen)==1 and answer['_repair_attempts']==0
    assert seen[0]['input']=='RAW_CUSTOMER_MESSAGE'
    assert 'Chỉ phản hồi CUỐI cho ứng dụng bằng một JSON object' not in seen[0]['instructions']


def test_native_reply_still_uses_verified_positive_stock_only(source,monkeypatch):
    from test_integrated_stock_v2 import wire,fresh
    monkeypatch.setenv('MERLY_DIALOGUE_CONTRACT_ENABLED','1')
    data=responses();data['output']=wire(fresh())[:2]+data['output']
    data['output'][-1]['content'][0]['text']='Các lựa chọn đã tra được gửi trong thẻ bên dưới; chưa giữ hàng.'
    answer=project(present(data,'resp_native',time.time()))
    assert answer['answer_mode']=='native' and answer['reply'].startswith('Các lựa chọn')
    assert answer['listing']['shown']<=4
    assert all(row['known_available']>0 for row in answer['stock_options']['variants'])
