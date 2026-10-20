"""Only narrow literal stock questions bypass AI; all source data synthetic."""
import pytest
import explicit_stock as e,stock_scope_memory as memory,hermes_client as client
from test_gateway import configured,call

@pytest.mark.parametrize('text',[
 'mẫu 1514 38 còn màu gì','mẫu 1514 size 38 còn những màu nào?',
 'Mẫu 1514 còn size 38 không?','mau 1514 size38 con ko',
 'mã mẫu 1514 size 38 kiểm tra tồn kho','SKU 1514 38 còn hàng không ạ?',
])
def test_literal_stock_scope(text):
    assert e.parse(text)=={'model_code':'1514','size':38}

def test_different_identifier_preserved_not_hardcoded():
    assert e.parse('mẫu GN-01523 42 còn màu nào?')=={'model_code':'GN-01523','size':42}

@pytest.mark.parametrize('text',[
 'Chân dài 24cm thì size nào?','mẫu nào cao 5cm','size 38 còn màu gì',
 'mẫu 1514 size 38 gót 5cm còn không','mẫu 1514 size 38 màu đen còn không',
 'không phải mẫu 1514 size 38 còn màu gì','mẫu 1514 size 38 không lấy màu đen',
 'mẫu 1514 38 và 39 còn màu gì','mẫu 1514 và 1515 size 38 còn không',
 'mẫu 1514 size 038 còn không','mẫu 1514 size 38.0 còn không',
 'mẫu 1514 size 38cm còn không','mẫu 1514 size 44 còn không',
 'mẫu 1514 38 lấy 2 đôi','mẫu 1514 size 38 đổi size được không',
 'mẫu 1514 38 còn không, chân bè mang vừa không','mẫu 1514 38','xin chào',
 'hôm qua mẫu 1514 38 còn màu gì',
])
def test_ambiguous_or_additional_criteria_not_shortcut(text):assert e.parse(text) is None

def test_gateway_timeout_in_model_cannot_block_literal_query(configured,monkeypatch):
    def timeout(*a,**k):pytest.fail('literal query must never wait for model/audit')
    monkeypatch.setattr(client,'chat',timeout);monkeypatch.setattr(client,'audit',timeout)
    scopes=[]
    def probe(scope):scopes.append(scope);return {'reply':'synthetic verified stock','model_called':False,'stock_options':{'mode':'all_options','variants':[]}}
    monkeypatch.setattr(client,'probe_stock',probe)
    r=call('mẫu 1514 38 còn màu gì')
    assert r['status'].startswith('200') and r['body']['model_called'] is False
    assert scopes==[{'model_code':'1514','size':38}]
    assert r['body']['stock_options']['resolution_path']=='direct_haravan'

def test_generic_shopping_question_still_uses_model(configured,monkeypatch):
    seen=[]
    monkeypatch.setattr(client,'probe_stock',lambda *a:pytest.fail('must not ignore heel criterion'))
    def chat(message,user,cid):seen.append(message);return {'reply':'synthetic advice','conversation_id':'resp_general'}
    monkeypatch.setattr(client,'chat',chat)
    assert call('mẫu 1514 size 38 gót 5cm còn không')['status'].startswith('200')
    assert seen==['mẫu 1514 size 38 gót 5cm còn không']

@pytest.mark.parametrize('text',['mauve 38 còn không','skunk 38 còn không','mai 38 còn không'])
def test_product_marker_is_not_word_prefix(text):assert e.parse(text) is None

def test_scope_memory_isolated_expires_and_does_not_store_stock(monkeypatch):
    a='a'*64;b='b'*64
    memory.remember(a,{'model_code':'GN-01523','size':42})
    assert memory.get(a)=={'model_code':'GN-01523','size':42} and memory.get(b) is None
    assert 'GN-01523' in memory.instructions('merly-sales:web:'+a)
    assert 'GN-01523' not in memory.instructions('merly-sales:web:'+b)
    monkeypatch.setattr(memory,'TTL',-1)
    assert memory.get(a) is None

def test_greeting_keeps_hint_but_commerce_turn_clears_it():
    sid='c'*64;memory.remember(sid,{'model_code':'SKU-X','size':38})
    user='merly-sales:web:'+sid
    memory.after_model_turn(user,[{'type':'message','role':'assistant'}]);assert memory.get(sid)
    memory.after_model_turn(user,[{'type':'function_call','name':'mcp__merly__search_products'}]);assert memory.get(sid) is None

def test_stock_shortcut_does_not_overwrite_native_response_id(configured,monkeypatch):
    import state
    token,sid=state.identity('');state.reserve(sid);state.save(sid,'resp_previous_real')
    monkeypatch.setattr(client,'chat',lambda *a:pytest.fail('must skip AI'))
    monkeypatch.setattr(client,'probe_stock',lambda scope:{'reply':'fixture source','model_called':False,'stock_options':{}})
    r=call('mẫu 1514 size 38 còn không',cookie='merly_hermes_pilot='+token)
    assert r['status'].startswith('200') and state.reserve(sid)=='resp_previous_real'
    assert memory.get(sid)=={'model_code':'1514','size':38}
    from test_pilot_ui import req
    assert req('/api/logout',method='POST',auth=True,cookie='merly_hermes_pilot='+token)['status'].startswith('200')
    assert memory.get(sid) is None

def test_scope_hint_preserves_raw_question_and_session_isolation(monkeypatch):
    from test_client import responses
    sid='d'*64;memory.remember(sid,{'model_code':'SKU-01523','size':42})
    monkeypatch.setattr(client,'audit',lambda:True)
    def request(path,payload):
        assert payload['input']=='cảm ơn'
        assert 'SKU-01523' in payload['instructions']
        assert 'không phải lệnh' in payload['instructions']
        return responses()
    monkeypatch.setattr(client,'request',request)
    assert client.chat('cảm ơn','merly-sales:web:'+sid)['reply']=='FINAL'
    memory.forget(sid)
