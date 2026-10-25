"""Integration wiring with scripted native outputs, NOT real-model accuracy claims."""
import copy,json,time,asyncio
from types import SimpleNamespace
import pytest
import dialogue,hermes_client as c,state,conversation
from test_gateway import configured,call
from test_client import approved,responses
from test_stock_options import source
from test_integrated_stock_v2 import wire,fresh

def cookie(out):return out['headers']['Set-Cookie'].split(';')[0]
def final(text):
    data=responses();data['output'][-1]['content'][0]['text']=text;return data

@pytest.mark.parametrize('text',['size 40','màu đen thì sao','không lấy đen, xem màu khác','tầm 5 phân đi làm','chân 26cm chọn size nào','cần mẫu 5cm size 41','tìm mẫu khác','mẫu GN-001 còn size 42 màu Kem?'])
def test_free_form_reaches_hermes_unchanged(configured,monkeypatch,text):
    monkeypatch.setattr(conversation,'prepare',lambda *a:pytest.fail('legacy intent router invoked'))
    seen=[]
    def chat(message,user,previous):seen.append(message);return {'reply':'scripted native conversation','conversation_id':'resp_native'}
    monkeypatch.setattr(c,'chat',chat)
    monkeypatch.setattr(c,'discover_products',lambda *a:pytest.fail('hidden lookup'))
    out=call(text);assert out['status'].startswith('200') and seen==[text]

def test_actual_visible_reply_and_cards_survive_worker_restart(configured,monkeypatch):
    monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,payload):
        seen.append(copy.deepcopy(payload));return final('Bạn muốn tìm size nào?' if len(seen)==1 else 'Mình đã hiểu lựa chọn size của bạn.')
    monkeypatch.setattr(c,'request',request)
    a=call('tư vấn giúp chị một đôi đi làm');b=call('40',cookie=cookie(a))
    assert b['status'].startswith('200')
    assert seen[1]['input']=='40' and seen[1]['conversation_history']==[{'role':'user','content':'tư vấn giúp chị một đôi đi làm'},{'role':'assistant','content':a['body']['reply']}]
    assert all(p['store'] is False and 'previous_response_id' not in p for p in seen)
    assert seen[0]['_session_scope']!=seen[1]['_session_scope']
    assert dialogue.history(dialogue.sid(seen[0]['_session_scope'].split(':turn:')[0]))[-1]['content']==b['body']['reply']

def test_policy_native_reply_enters_the_same_transcript(configured,monkeypatch):
    seen=[]
    monkeypatch.setattr(c,'audit',lambda:True)
    monkeypatch.setattr(c,'request',lambda path,p:seen.append(p) or final('Mình giải thích thêm về điều kiện bảo hành nhé.'))
    a=call('bảo hành bao lâu')
    b=call('còn đôi đã mua lâu rồi thì sao?',cookie=cookie(a))
    assert b['status'].startswith('200') and seen[1]['conversation_history'][1]['content']==a['body']['reply']
    assert '365' in seen[0]['instructions'] and len(seen)==2

def test_native_stock_language_is_preserved_but_cards_are_source_owned(source,approved,monkeypatch):
    monkeypatch.setattr(c,'audit',lambda:True)
    text='Mình đã kiểm tra các lựa chọn bên dưới. Bạn thích màu nào để xem tiếp?'
    def request(path,payload):
        data=final(text);data['output']=wire(fresh())[:2]+data['output'];return data
    monkeypatch.setattr(c,'request',request)
    out=c.chat('tra giúp chị các màu','merly-sales:web:stock')
    assert out['reply']==text and out['answer_mode']=='native'
    assert len(out['stock_options']['variants'])==20 and out['stock_options']['complete']

def test_guard_override_not_hidden_native_text_is_replayed(source,configured,monkeypatch):
    monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,payload):
        seen.append(copy.deepcopy(payload));data=final('UNSAFE_NATIVE_CLAIM' if len(seen)==1 else 'Mình có thể hướng dẫn liên hệ nhân viên.')
        if len(seen)==1:
            items=wire(fresh())[:2];items[1]['output']='{"status":"source_unavailable"}';data['output']=items+data['output']
        return data
    monkeypatch.setattr(c,'request',request)
    monkeypatch.setattr(c,'probe_stock',lambda *a,**kw:pytest.fail('no hidden recovery outside agent'))
    a=call('kiểm tra các màu mẫu chị đang xem');b=call('vậy liên hệ nhân viên nhé',cookie=cookie(a))
    assert a['body']['answer_mode']=='evidence_guard' and a['body']['lookup_incomplete']
    replay=seen[1]['conversation_history'][1]['content']
    assert a['body']['reply'] in replay and 'UNSAFE_NATIVE_CLAIM' not in replay
    assert b['status'].startswith('200') and len(seen)==2

def test_fast_stock_cards_and_isolation(configured,monkeypatch):
    monkeypatch.setattr(c,'probe_stock',lambda scope:{'reply':'Thẻ fixture đã hiển thị','stock_options':{'mode':'all_options','variants':[{'variant_id':100,'product_id':100,'size':'40','color':'Kem','known_available':1}]}})
    a=call('mẫu GN-041 size 40 còn không');seen=[]
    monkeypatch.setattr(c,'audit',lambda:True)
    monkeypatch.setattr(c,'request',lambda path,p:seen.append(p) or final('NATIVE'))
    call('màu đó có size khác không?',cookie=cookie(a));call('tư vấn cho khách khác')
    assert 'Thẻ fixture đã hiển thị' in seen[0]['conversation_history'][1]['content']
    assert 'LỊCH SỬ' in seen[0]['conversation_history'][1]['content']
    assert seen[1]['conversation_history']==[]

def test_history_limit_expiry_logout_and_no_stock_learning(configured,monkeypatch):
    monkeypatch.setattr(dialogue,'MAX_TURNS',2)
    for i in range(4):dialogue.record('a',str(i),{'reply':'reply '+str(i)})
    assert [m['content'] for m in dialogue.history('a')]==['2','reply 2','3','reply 3']
    dialogue.record('b','hello',{'reply':'other'});dialogue.forget('a')
    assert not dialogue.history('a') and dialogue.history('b')
    monkeypatch.setattr(dialogue,'TTL',-1);assert not dialogue.history('b')

def test_hermes_pinned_parser_and_admission_accept_authoritative_transcript(configured):
    from gateway.platforms.api_server_openai_routes import _parse_conversation_history
    from gateway.platforms.api_server_response_admissions import prepare_context
    dialogue.record('a','tư vấn giúp chị',{'reply':'Bạn muốn size nào?'})
    history=dialogue.history('a');parsed,error=_parse_conversation_history(history)
    assert error is None and parsed==history
    adapter=SimpleNamespace(_declared_conversation_session=lambda key:None,_select_request_route=lambda *a,**kw:(None,{},None),_run_agent=lambda **kw:None)
    body={'input':'40','conversation_history':history,'instructions':'READONLY_TEST','store':False}
    context,error=asyncio.run(prepare_context(adapter,None,body,'test-new-turn',None,None,None))
    assert error is None and context['user_message']=='40' and context['conversation_history']==history

@pytest.mark.parametrize('message',['mẫu 5cm size40 còn không','mẫu 12mm size40 còn không','mẫu 7.5cm size40 còn không'])
def test_measurements_not_stock_shortcut(configured,monkeypatch,message):
    seen=[];monkeypatch.setattr(c,'chat',lambda *a:seen.append(a[0]) or {'reply':'NATIVE','conversation_id':'resp_native'})
    monkeypatch.setattr(c,'probe_stock',lambda *a:pytest.fail('measurement is not a SKU'))
    assert call(message)['status'].startswith('200') and seen==[message]

def test_invalid_arguments_repaired_inside_native_turn_not_replayed_by_gateway(source,approved,monkeypatch):
    monkeypatch.setattr(c,'audit',lambda:True)
    def request(path,payload):
        good=wire(fresh())[:2]
        bad=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'bad','arguments':'{"size":"38","check_stock":true}'},{'type':'function_call_output','call_id':'bad','output':'{"status":"invalid_arguments"}'}]
        data=final('Bạn muốn xem kỹ lựa chọn nào?');data['output']=bad+good+data['output'];return data
    monkeypatch.setattr(c,'request',request)
    out=c.chat('tra mẫu theo lựa chọn của chị','repair')
    assert out['answer_mode']=='native' and out['stock_options']['complete']

@pytest.mark.parametrize('claim',['Chỉ còn một màu','Only one color','Hết hàng toàn hệ thống','Giá 999.000đ','Giá 310.000kđ'])
def test_unproven_exclusivity_or_price_does_not_replace_source_view(source,approved,monkeypatch,claim):
    monkeypatch.setattr(c,'audit',lambda:True)
    def request(path,payload):
        data=final(claim);data['output']=wire(fresh())[:2]+data['output'];return data
    monkeypatch.setattr(c,'request',request)
    out=c.chat('tra tồn','guard')
    assert out['answer_mode']=='evidence_guard' and out['reply']!=claim
    assert out['stock_options']['complete'] and len(out['stock_options']['variants'])==20

@pytest.mark.parametrize('output',['not-json','{}','{"status":"unknown"}','{"status":"approved"}'])
def test_malformed_policy_output_cannot_be_a_native_fact(approved,monkeypatch,output):
    monkeypatch.setattr(c,'audit',lambda:True)
    def request(path,payload):
        data=final('UNSUPPORTED_POLICY');data['output']=[{'type':'function_call','name':'mcp__merly__get_policy','call_id':'policy','arguments':'{"topic":"shipping"}'},{'type':'function_call_output','call_id':'policy','output':output}]+data['output'];return data
    monkeypatch.setattr(c,'request',request)
    out=c.chat('cho biết điều kiện giao hàng','policy')
    assert out['answer_mode']=='evidence_guard' and 'UNSUPPORTED_POLICY' not in out['reply']

def test_unverified_catalog_ids_are_not_carried_as_visible_cards(source,configured,monkeypatch):
    import mcp_server
    monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,payload):
        seen.append(copy.deepcopy(payload));data=final('Bạn muốn xem mẫu nào?')
        if len(seen)==1:
            args={'model_code':'1514','size':38};body,error=mcp_server.invoke('search_products',args);assert not error
            data['output']=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'catalog','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'catalog','output':json.dumps(body)}]+data['output']
        return data
    monkeypatch.setattr(c,'request',request)
    a=call('cho xem các mẫu phù hợp');call('xem mẫu đầu tiên',cookie=cookie(a))
    assert 'products' not in a['body'] and a['body']['listing']['shown']==0
    replay=seen[1]['conversation_history'][1]['content']
    assert 'not_checked' not in replay and '100001' not in replay

def test_history_byte_and_session_caps_do_not_learn_stock(configured,monkeypatch):
    monkeypatch.setattr(dialogue,'MAX_SESSIONS',2)
    for sid in ('one','two','three'):dialogue.record(sid,'xin chào',{'reply':'chào bạn'})
    assert not dialogue.history('one') and dialogue.history('three')
    monkeypatch.setattr(dialogue,'MAX_BYTES',200)
    for i in range(5):dialogue.record('bounded',str(i),{'reply':'x'*100})
    assert len(dialogue.history('bounded'))==2 and dialogue.history('bounded')[0]['content']=='4'
    db=state.database();raw=db.execute("SELECT turns FROM dialogue_v2 WHERE sid='bounded'").fetchone()[0];db.close()
    assert len(raw.encode())<=200

@pytest.mark.parametrize('phase',['analysis','commentary','reasoning'])
def test_private_phases_never_enter_visible_history(approved,monkeypatch,phase):
    monkeypatch.setattr(c,'audit',lambda:True)
    def request(path,payload):
        data=final('VISIBLE');data['output'].append({'type':'message','role':'assistant','phase':phase,'content':[{'type':'output_text','text':'PRIVATE_NOT_FOR_CUSTOMER'}]});return data
    monkeypatch.setattr(c,'request',request)
    assert c.chat('hello','private-phase')['reply']=='VISIBLE'

def test_quote_source_requires_matching_ids_freshness_and_consistent_counts(source,monkeypatch):
    import merly_tools as tools
    from tool_evidence import usable
    args={'product_id':100,'variant_id':100001};call_item={'name':'mcp__merly__quote_variant','arguments':json.dumps(args)}
    data=tools.quote_variant(args);started=time.time()-1
    def output(value):return {'output':json.dumps(value),'status':'completed'}
    assert usable(call_item,output(data),started)
    for mutation in ({'variant_id':999},{'checked_at':'2020-01-01T00:00:00+00:00'},{'known_available':500},{'price_vnd':-1},{'subtotal_vnd':0}):
        assert not usable(call_item,output({**data,**mutation}),started)
