"""Contract/transport tests, not evidence of model semantic comprehension."""
import copy,json,time
import pytest
import dialogue_response as d,hermes_client as c,dialogue,state
from agent_answer import present
from customer_listing import project
from test_client import approved,responses
from test_gateway import configured,call
from test_stock_options import source

@pytest.fixture
def strict(approved,monkeypatch):
    monkeypatch.delenv('MERLY_DIALOGUE_CONTRACT_ENABLED',raising=False)
    monkeypatch.setattr(c,'audit',lambda:True)

@pytest.fixture
def strict_gateway(configured,monkeypatch):
    monkeypatch.delenv('MERLY_DIALOGUE_CONTRACT_ENABLED',raising=False)
    monkeypatch.setattr(c,'audit',lambda:True)

def envelope(understanding='understood',reply='NATIVE_REPLY',question='',options=None):
    return dict(understanding=understanding,reply=reply,question=question,options=options or [])

def wire(value,items=None):
    r=responses();r['output']=(items or [])+r['output'];r['output'][-1]['content'][0]['text']=json.dumps(value,ensure_ascii=False) if not isinstance(value,str) else value
    return r

@pytest.mark.parametrize('status',['understood','partial','unclear'])
def test_native_statuses_preserve_generated_question_and_labels(strict,status):
    value=envelope(status,'Giữ đúng phần bạn đã nói.','Bạn muốn mình làm rõ điểm nào?',['Lựa chọn A','Một ý khác'])
    answer=present(wire(value),'resp_fixture',time.time())
    assert answer['reply']==value['reply']+'\n'+value['question']
    assert answer['clarification_options']==value['options']
    assert answer['needs_clarification']==(status!='understood')
    assert not answer['_guard_reasons'] and '{"understanding"' not in answer['reply']

@pytest.mark.parametrize('patch',[{'understanding':'maybe'},{'understanding':True},{'reply':None},{'question':False},{'reply':'x'*6001},{'question':'x'*501},{'reply':'\x00'},{'options':None},{'options':['x']},{'options':['x']*4},{'options':['a','a']},{'options':['a',False]},{'options':['a','x'*121]},{'options':['a','\n']},{'options':['a',' ']},{'options':{'a':'b'}},{'options':['a','b'],'question':''},{'understanding':'partial','question':''},{'understanding':'unclear','question':''},{'reply':'','question':''},{'confidence':.99}])
def test_invalid_shapes_are_not_silently_repaired(strict,patch):
    value=envelope();value.update(patch)
    with pytest.raises(d.InvalidDialogue):d.parse(json.dumps(value))

@pytest.mark.parametrize('raw',['[]','null','true','"plain"','plain','```json\n{}\n```','{"understanding":"understood","understanding":"partial","reply":"a","question":"b","options":[]}'])
def test_no_fence_scraping_or_duplicate_keys(strict,raw):
    with pytest.raises(d.InvalidDialogue):d.parse(raw)

@pytest.mark.parametrize('status',['partial','unclear'])
def test_open_question_does_not_force_menu(strict,status):
    answer=present(wire(envelope(status,'','Bạn có thể nói rõ hơn điều bạn cần không?')),'resp_fixture',time.time())
    assert answer['needs_clarification'] and answer['clarification_options']==[]
    assert answer['_guard_reasons']==[]

def test_positive_inventory_is_hidden_while_clarifying(strict,source):
    from test_integrated_stock_v2 import wire as stock_wire,fresh
    value=envelope('partial','Mình giữ size và màu bạn đã chọn.','Bạn muốn kiểu nào?',['Kiểu A','Kiểu B'])
    answer=present(wire(value,stock_wire(fresh())[:2]),'resp_fixture',time.time())
    assert answer['stock_options']['variants']
    view=project(answer)
    assert view['needs_clarification'] and not any(k in view for k in ('stock_options','products','quotes'))
    assert view['listing']['shown']==0 and not any('/products/' in u for u in view['source_links'])
    assert value['question'] in view['reply']

def test_source_error_does_not_overwrite_safe_question(strict):
    items=[{'type':'function_call','call_id':'f','name':'mcp__merly__search_products','arguments':'{"query":"fixture","size":40}'},{'type':'function_call_output','call_id':'f','output':'{"status":"source_unavailable"}'}]
    value=envelope('partial','Mình đã ghi nhận yêu cầu trước đó.','Bạn muốn kiểu nào?')
    answer=present(wire(value,items),'resp_fixture',time.time())
    assert answer['answer_mode']=='clarification' and value['question'] in answer['reply']
    assert not answer['_guard_reasons'] and answer['_deferred_tool_reasons']
    assert answer['_tool_diagnostics'][0]['source_status']=='source_unavailable'
    # Backend must NOT infer "unclear" from a failed lookup.
    understood=present(wire(envelope('understood','Nguồn đang lỗi; mình giữ điều kiện của bạn.'),items),'resp_fixture',time.time())
    assert understood['understanding']=='understood' and not understood.get('needs_clarification')
    assert understood['_guard_reasons']

@pytest.mark.parametrize('patch',[{'reply':'Mẫu này còn hàng'},{'reply':'Giá 399.000đ'},{'question':'Xem https://merlyshoes.com/products/unsafe-fixture ?'},{'options':['Lựa chọn A','mcp__merly__search_products']}])
def test_clarification_cannot_bypass_listing_or_protocol_guard(strict,patch):
    value=envelope('partial','Mình cần hỏi rõ thêm.','Bạn cần kiểu nào?');value.update(patch)
    answer=project(present(wire(value),'resp_fixture',time.time()))
    assert answer['understanding']=='invalid' and not answer['needs_clarification']
    assert not any(k in answer for k in ('stock_options','products','quotes','clarification_options'))
    assert value['question'] not in answer['reply']

def test_budget_question_is_not_misread_as_a_quoted_product_price(strict):
    value=envelope('partial','Mình giữ các điều kiện bạn đã nêu.','Bạn muốn ngân sách dưới 300k hay trên 300k?',['Dưới 300k','Trên 300k'])
    answer=present(wire(value),'resp_fixture',time.time())
    assert answer['answer_mode']=='clarification' and not answer['_guard_reasons']

@pytest.mark.parametrize('bad',['0 ','true','2',''])
def test_invalid_config_fails_before_network(strict,monkeypatch,bad):
    monkeypatch.setenv('MERLY_DIALOGUE_CONTRACT_ENABLED',bad)
    monkeypatch.setattr(c,'audit',lambda:pytest.fail('no network'))
    with pytest.raises(c.HermesError,match='invalid_agent_settings'):c.chat('hello','test')

def test_legacy_mode_is_explicit_not_default(strict,monkeypatch):
    assert d.enabled()
    monkeypatch.setenv('MERLY_DIALOGUE_CONTRACT_ENABLED','0')
    answer=present(wire('NATIVE_LEGACY'),'resp_fixture',time.time())
    assert answer['reply']=='NATIVE_LEGACY' and answer['understanding']=='legacy'

def test_choices_and_free_text_followup_are_delivered_not_auto_selected(strict_gateway,monkeypatch):
    seen=[]
    def request(path,payload):
        seen.append(copy.deepcopy(payload))
        return wire(envelope('partial','Mình giữ đúng điều kiện bạn đã gửi.','Bạn muốn kiểu nào?',['Lựa chọn A','Lựa chọn B'])) if len(seen)==1 else wire(envelope(reply='FOLLOWUP_NATIVE'))
    monkeypatch.setattr(c,'request',request)
    first=call('RAW_FIRST_USER_SENTINEL');cookie=first['headers']['Set-Cookie'].split(';')[0]
    assert first['body']['needs_clarification'] and first['body']['clarification_options']==['Lựa chọn A','Lựa chọn B']
    _,sid=state.identity(cookie);before=dialogue.history(sid)
    assert before[0]['content']=='RAW_FIRST_USER_SENTINEL' and 'choices_shown' in before[1]['content']
    assert len(before)==2 # no invented customer selection, and only delivered text
    second=call('Mình muốn một kiểu khác, không chọn A hay B',cookie=cookie)
    assert second['body']['reply']=='FOLLOWUP_NATIVE'
    assert seen[1]['input']=='Mình muốn một kiểu khác, không chọn A hay B'
    assert seen[1]['conversation_history']==before
    assert all(x in seen[0]['instructions'] for x in ('understanding:','partial:','unclear:'))
    assert not any(k.startswith('_') for k in first['body'])

def test_invalid_format_gets_one_internal_repair_not_a_customer_blame(strict,monkeypatch):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');seen=[]
    def request(path,payload):
        seen.append(copy.deepcopy(payload))
        return wire('plain text format failure') if len(seen)==1 else wire(envelope(reply='Mình trả lời yêu cầu đã rõ của bạn.'))
    monkeypatch.setattr(c,'request',request)
    answer=c.chat('RAW_CLEAR_REQUEST','merly-sales:web:'+'a'*64)
    assert len(seen)==2 and answer['reply']=='Mình trả lời yêu cầu đã rõ của bạn.'
    assert answer['_repair_attempts']==1 and not answer['needs_clarification']
    assert seen[0]['input']==seen[1]['input']=='RAW_CLEAR_REQUEST'
    assert 'machine format error' in seen[1]['instructions'] and 'plain text format failure' not in seen[1]['instructions']


def test_repeated_bad_format_never_leaks_json_or_retries_forever(strict,monkeypatch):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');seen=[]
    def request(*args):seen.append(args);return wire('{"reply":"UNSAFE_RAW_SENTINEL"}')
    monkeypatch.setattr(c,'request',request)
    answer=c.chat('RAW_CLEAR_REQUEST','merly-sales:web:'+'a'*64)
    assert len(seen)==2 and answer['_repair_attempts']==1
    assert answer['understanding']=='invalid' and not answer['needs_clarification']
    assert 'UNSAFE_RAW_SENTINEL' not in answer['reply'] and 'chưa hiểu' not in answer['reply']


def test_safe_clarification_does_not_cost_a_repair(strict,monkeypatch):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');seen=[]
    def request(*args):seen.append(args);return wire(envelope('unclear','Mình chưa hiểu rõ nhu cầu của bạn.','Bạn nói rõ hơn giúp mình được không?'))
    monkeypatch.setattr(c,'request',request)
    answer=c.chat('RAW_UNCLEAR_SENTINEL','merly-sales:web:'+'b'*64)
    assert len(seen)==1 and answer['needs_clarification'] and answer['_repair_attempts']==0

@pytest.mark.parametrize('reply',['Mình giữ size 39 đen bạn đã chọn.','Bạn đang nhắc 40 đường khác nhau.','Mình giữ size 39 màu đen.'])
def test_currency_token_boundary_does_not_block_confirmed_details(strict,reply):
    value=envelope('partial',reply,'Bạn muốn kiểu nào?')
    assert d.safe_clarification(value)
    assert present(wire(value),'resp_fixture',time.time())['needs_clarification']

@pytest.mark.parametrize('reply,accepted',[('Ngưỡng phí giả lập là 300.000đ.',True),('Size này còn hàng.',False)])
def test_approved_policy_fee_is_not_product_inventory_proof(strict,monkeypatch,reply,accepted):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');seen=[]
    items=[{'type':'function_call','call_id':'p','name':'mcp__merly__get_policy','arguments':'{"topic":"store_hours"}'},{'type':'function_call_output','call_id':'p','output':json.dumps({'status':'approved','text':'Synthetic fee fixture 300.000đ, not real policy.'})}]
    def request(*args):
        seen.append(args)
        return wire('bad format') if len(seen)==1 else wire(envelope(reply=reply),items)
    monkeypatch.setattr(c,'request',request)
    answer=c.chat('RAW_POLICY_REQUEST','merly-sales:web:'+'c'*64)
    assert len(seen)==2
    assert (answer['reply']==reply)==accepted
