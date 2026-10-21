import json
import pytest
import conversation as ctx,hermes_client as client
from test_gateway import configured,call
@pytest.fixture(autouse=True)
def clean():
    ctx._STATE.clear();yield;ctx._STATE.clear()
def test_followups():
    assert ctx.prepare('a','mẫu 1514 size 41 còn không')['scope']=={'model_code':'1514','size':41}
    assert ctx.prepare('a','Màu đen thì sao?')['scope']=={'model_code':'1514','size':41,'color':'đen'}
    assert ctx.prepare('a','còn 42?')['scope']=={'model_code':'1514','size':42,'color':'đen'}
    assert ctx.prepare('a','còn màu nào?')['scope']=={'model_code':'1514','size':42}
def test_cream_not_white_cream():
    ctx.prepare('a','mẫu 1514 size 38 còn không')
    assert ctx.prepare('a','màu Trắng Kem thì sao')['scope']['color']=='Trắng Kem'
    assert ctx.prepare('a','màu Kem thì sao')['scope']['color']=='Kem'
@pytest.mark.parametrize('text',['Tìm mẫu khác','tìm giày đi làm','có đôi nào đi tiệc không'])
def test_new_search(text):
    ctx.seed('a',{'model_code':'1514','size':41,'color':'đen'})
    assert ctx.prepare('a',text)['route']=='model'
    assert not ctx.get('a')['slots'] and ctx.get('a')['reset']
@pytest.mark.parametrize('text',['size 42','còn 42','Màu đen thì sao?'])
def test_missing_model(text):assert ctx.prepare('new',text)['route']=='clarify'
@pytest.mark.parametrize('text',['không lấy màu đen','không phải mẫu 1514'])
def test_negation(text):
    ctx.seed('a',{'model_code':'1514','size':41,'color':'đen'})
    assert ctx.prepare('a',text)['route'] in ('model','clarify')
    assert not ctx.get('a')['allow_fast']
@pytest.mark.parametrize('text',['cần mẫu 5cm size 41','Tìm giúp chị giày cao 5cm cỡ 41','tìm giày gót 5 phân size 41'])
def test_explicit_filters(text):
    assert ctx.prepare('a',text)=={'route':'catalog','scope':{'heel_cm':5.0,'size':41,'limit':4}}
@pytest.mark.parametrize('text',['Có đôi nào gót tầm 5 phân, chân mang 41 không?','cần giày cao khoảng 5cm size 41'])
def test_approximate(text):
    assert ctx.prepare('a',text)['route']=='clarify'
    assert 'heel_cm' not in ctx.get('a')['slots']
@pytest.mark.parametrize('text',['cần mẫu 5cm size41 màu đen','mẫu 1514 size41 và42 còn không','chân 26cm đi vừa không'])
def test_extra_criteria(text):assert ctx.prepare('a',text)['route']!='stock'
def test_policy_barrier():
    ctx.seed('a',{'model_code':'1514','size':41});ctx.policy_turn('a','warranty')
    assert ctx.prepare('a','còn 42')['route']=='clarify'
def test_isolation_expiry_bounded(monkeypatch):
    ctx.seed('a',{'model_code':'GN-01523','size':42});assert not ctx.get('b')
    assert 'GN-01523' in ctx.instructions('merly-sales:web:a')
    assert not ctx.instructions('merly-sales:web:b')
    monkeypatch.setattr(ctx,'TTL',-1);assert not ctx.get('a')
    monkeypatch.setattr(ctx,'TTL',1800);monkeypatch.setattr(ctx,'MAX',2)
    for i in range(3):ctx.seed(str(i),{'size':41})
    assert len(ctx._STATE)==2

def plan(**args):return [{'type':'function_call','name':'mcp__merly__search_products','arguments':json.dumps(args)}]
def test_dropped_criteria_rejected_before_display():
    ctx.prepare('a','tìm giày gót 5cm size41 màu đen')
    assert ctx.observe('merly-sales:web:a',plan(size=41,heel_cm=5)) is not None
    assert ctx.observe('merly-sales:web:a',plan(size=41,heel_cm=5,color='đen')) is None
    assert ctx.get('a')['last_plan']['customer_confirmed'] is False

def test_foot_length_not_confirmed_size_and_yes_is_explicit_confirmation():
    ctx.prepare('a','chân 26cm chọn size nào')
    q=ctx.observe('merly-sales:web:a',plan(model_code='1514',size=42,check_stock=True))
    assert 'chưa chốt size' in q
    assert 'size' not in ctx.get('a')['confirmed']
    assert ctx.prepare('a','đúng rồi')=={'route':'stock','scope':{'model_code':'1514','size':42}}

def test_approximate_then_exact():
    ctx.prepare('a','cần giày gót tầm 5cm size41')
    assert ctx.prepare('a','đúng 5cm')['scope']=={'heel_cm':5.0,'size':41,'limit':4}

def test_negative_then_positive_color_keeps_model():
    ctx.seed('a',{'model_code':'1514','size':41,'color':'đen'})
    assert ctx.prepare('a','không lấy màu đen')['route']=='clarify'
    assert ctx.get('a')['slots']=={'model_code':'1514','size':41}
    assert ctx.prepare('a','màu trắng')['scope']=={'model_code':'1514','size':41,'color':'trắng'}

def test_malformed_identifier_never_repaired():
    ctx.prepare('a','mẫu GN-01523 size42 còn không')
    assert ctx.observe('merly-sales:web:a',plan(model_code='GN_01523',size=42,check_stock=True)) is not None
    assert ctx.get('a')['slots']['model_code']=='GN-01523'

def test_reset_disallows_old_model_plan():
    ctx.seed('a',{'model_code':'1514','size':41})
    ctx.prepare('a','tìm mẫu khác')
    assert 'mã mẫu cũ' in ctx.observe('merly-sales:web:a',plan(model_code='1514',size=41))

def test_gateway_multi_turn_uses_new_stock_each_time_and_no_ai(configured,monkeypatch):
    scopes=[]
    monkeypatch.setattr(client,'chat',lambda *a:pytest.fail('followup must not invoke AI'))
    monkeypatch.setattr(client,'probe_stock',lambda s:scopes.append(dict(s)) or {'reply':'fixture','model_called':False})
    r=call('mẫu 1514 size41 còn không');cookie=r['headers']['Set-Cookie'].split(';')[0]
    assert call('màu đen thì sao',cookie=cookie)['status'].startswith('200')
    assert call('còn42',cookie=cookie)['status'].startswith('200')
    assert scopes==[{'model_code':'1514','size':41},{'model_code':'1514','size':41,'color':'đen'},{'model_code':'1514','size':42,'color':'đen'}]
    import state
    db=state.database();assert db.execute('SELECT count(*) FROM calls').fetchone()[0]==0;db.close()

def test_client_semantic_contract_one_model_turn_and_no_unsafe_report(monkeypatch):
    from test_client import responses
    user='merly-sales:web:'+'a'*64
    ctx.prepare('a'*64,'tìm giày gót5cm size41 màu đen')
    seen=[];monkeypatch.setattr(client,'audit',lambda:True)
    def request(path,payload):
        seen.append((path,payload));r=responses();r['output']=plan(size=41,heel_cm=5)+r['output'];return r
    monkeypatch.setattr(client,'request',request)
    r=client.chat('tìm giày gót5cm size41 màu đen',user,'resp_prior')
    assert r['needs_clarification'] and 'stock_options' not in r
    assert len(seen)==1 and seen[0][1]['previous_response_id']=='resp_prior'
    assert 'LATEST_STRUCTURED_CUSTOMER_CONTEXT' in seen[0][1]['instructions']
    assert 'last_plan' in seen[0][1]['instructions'] or 'hợp đồng yêu cầu' in seen[0][1]['instructions']

def test_model_understands_rich_request_then_followup_is_not_forced_to_old_sku():
    text='Có đôi nào gót 5 phân để đi làm, em mang 41 không?'
    assert ctx.prepare('a',text)['route']=='model'
    assert ctx.observe('merly-sales:web:a',plan(heel_cm=5,size=41,occasion='đi làm')) is None
    d=ctx.prepare('a','còn 42')
    assert d['route']=='model'
    state=ctx.get('a');assert state['slots']['size']==42
    assert state['last_plan']['slots']['occasion']=='đi làm'
    assert 'size' in state['binding']
    assert ctx.observe('merly-sales:web:a',plan(size=41,heel_cm=5,occasion='đi làm')) is not None

def test_native_history_used_after_worker_context_restart(configured,monkeypatch):
    seen=[]
    def chat(message,user,cid):
        seen.append((message,cid));return {'reply':'synthetic advice','conversation_id':'resp_context'}
    monkeypatch.setattr(client,'chat',chat)
    r=call('tư vấn chọn giày');cookie=r['headers']['Set-Cookie'].split(';')[0]
    ctx._STATE.clear()
    r=call('size42',cookie=cookie)
    assert r['status'].startswith('200') and seen[-1]==('size42','resp_context')

def test_white_cream_not_repaired_into_cream_by_model():
    ctx.seed('a',{'model_code':'1514','size':38,'color':'Trắng Kem'})
    assert ctx.observe('merly-sales:web:a',plan(model_code='1514',size=38,color='Kem',check_stock=True)) is not None
    assert ctx.get('a')['slots']['color']=='Trắng Kem'

def test_clear_color_blocks_old_model_filter():
    ctx.seed('a',{'heel_cm':5.0,'size':41,'color':'đen'},'find_products')
    ctx.prepare('a','tất cả màu')
    assert ctx.observe('merly-sales:web:a',plan(size=41,heel_cm=5,color='đen')) is not None

def test_reset_allows_new_source_candidates_but_not_old_selected_model():
    ctx.seed('a',{'model_code':'1514','size':41})
    ctx.prepare('a','tìm mẫu khác size41')
    assert ctx.observe('merly-sales:web:a',plan(model_code='1523',size=41,check_stock=True)) is None
    assert ctx.observe('merly-sales:web:a',plan(model_code='1514',size=41,check_stock=True)) is not None

def test_model_policy_tool_records_topic_barrier_without_phrase_match():
    ctx.seed('a',{'model_code':'1514','size':41})
    ctx.prepare('a','đôi mua rồi cần sửa thì bảo hành sao shop')
    ctx.observe('merly-sales:web:a',[{'type':'function_call','name':'mcp__merly__get_policy','arguments':{'topic':'warranty'}}])
    assert ctx.get('a')['intent']=='policy'
    assert ctx.prepare('a','còn42')['route']=='clarify'
