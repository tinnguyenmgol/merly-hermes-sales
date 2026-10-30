"""Scripted native pipeline, synthetic Haravan; not live model quality claims."""
import copy,json,time
import pytest
import agent_answer,customer_listing,merly_tools as tools,mcp_server,stock_report
from test_stock_options import source,product
from test_client import responses,approved
from test_model_size_schema import visible
import audit_instance

@pytest.fixture
def heels(source,monkeypatch):
    source['products']=[]
    for i,cm in enumerate((5,7,10)):
        p=product(100+i,1);p['title']=f'Giày cao gót {cm}cm fixture'
        p['variants'][0].update(option1='Đen',option2='42')
        source['products'].append(p)
    monkeypatch.setattr(tools,'enrichment',lambda:{})
    return source

def native(args,text):
    result,error=mcp_server.invoke('search_products',args);assert not error
    data=responses();data['output']=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'height-test','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'height-test','output':json.dumps(result)}]+data['output']
    data['output'][-1]['content'][0]['text']=text
    return data

def presented(args,text):
    start=time.time();return agent_answer.present(native(args,text),'resp_fixture',start)

def test_model_must_explicitly_declare_height_without_nullable_provider_schema():
    defs=visible();audit_instance.check_model_definitions(defs)
    s=next(d['function']['parameters'] for d in defs if d['function']['name']=='mcp__merly__search_products')
    assert 'heel_mode' in s['required'] and s['properties']['heel_mode']['enum']==['exact','unspecified']
    s['required'].remove('heel_mode')
    with pytest.raises(ValueError,match='model_heel'):audit_instance.check_model_definitions(defs)

@pytest.mark.parametrize('args',[{'heel_mode':'exact'},{'heel_mode':'unspecified','heel_cm':7},{'heel_mode':'unknown'}])
def test_contradictory_declaration_never_reads_source(monkeypatch,args):
    monkeypatch.setattr(tools.catalog,'snapshot',lambda:pytest.fail('no source read'))
    result,error=mcp_server.invoke('search_products',{'size':42,**args})
    assert error and result['reason']=='inconsistent_heel_requirement'

@pytest.mark.parametrize('cm',[5,7,10])
def test_exact_search_and_positive_cards_match_each_selected_height(heels,cm):
    out=presented({'size':42,'heel_mode':'exact','heel_cm':cm},f'Các mẫu gót {cm}cm đã tra ở bên dưới.')
    assert out['answer_mode']=='native' and not out['_guard_reasons']
    view=customer_listing.project(out)
    assert view['listing']['shown']==1
    assert all(p['verified_specs']['heel_cm']==cm for p in view['stock_options']['products'])

def test_unselected_height_keeps_all_available_heights(heels):
    out=presented({'size':42,'heel_mode':'unspecified'},'Đây là các lựa chọn mình đã tra.')
    assert out['answer_mode']=='native'
    assert customer_listing.project(out)['listing']['shown']==3
    assert 'heel_cm' not in out['stock_options']['criteria']

def test_single_height_claim_cannot_leak_other_height_cards(heels):
    out=presented({'size':42},'Các mẫu gót 7cm ở bên dưới nhé.')
    assert 'unsupported_spec_claim' in out['_guard_reasons']
    view=customer_listing.project(out)
    assert view['listing']['shown']==0
    assert not any(k in view for k in ('stock_options','quotes','products'))
    assert not any('/products/' in u for u in view['source_links'])

def test_data_free_question_and_foot_length_are_not_heel_claims():
    for text in ('Bạn thích gót 7cm hay 10cm?','Chân dài 26cm, chị thường mang size nào?'):
        data=responses();data['output'][-1]['content'][0]['text']=text
        out=agent_answer.present(data,'resp_fixture',time.time())
        assert out['reply']==text and out['answer_mode']=='native'


def test_scripted_height_change_keeps_raw_message_and_delivered_history(heels,approved,monkeypatch):
    import hermes_client as client,dialogue
    monkeypatch.setattr(client,'audit',lambda:True)
    user='merly-sales:web:height-history';key=dialogue.sid(user);seen=[]
    messages=['Tôi muốn gót 5cm, size 42.','Đổi sang gót 7cm, vẫn size 42.']
    def request(path,payload):
        n=len(seen);seen.append(copy.deepcopy(payload))
        assert payload['input']==messages[n]
        if n==1:
            assert payload['conversation_history'][0]['content']==messages[0]
            assert '5cm' in payload['conversation_history'][1]['content']
        cm=(5,7)[n]
        return native({'size':42,'heel_mode':'exact','heel_cm':cm},f'Các mẫu gót {cm}cm ở bên dưới.')
    monkeypatch.setattr(client,'request',request)
    for message,cm in zip(messages,(5,7)):
        out=customer_listing.project(client.chat(message,user))
        assert out['stock_options']['criteria']['heel_cm']==cm and out['listing']['shown']==1
        assert all(p['verified_specs']['heel_cm']==cm for p in out['stock_options']['products'])
        dialogue.record(key,message,out)
    assert len(seen)==2


def test_bad_cards_allow_only_one_existing_bounded_repair(heels,approved,monkeypatch):
    import hermes_client as client
    monkeypatch.setattr(client,'audit',lambda:True);monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1')
    seen=[]
    def request(path,payload):
        seen.append(copy.deepcopy(payload))
        assert payload['input']=='Đổi sang gót 7cm, size 42.'
        args={'size':42} if len(seen)==1 else {'size':42,'heel_mode':'exact','heel_cm':7}
        return native(args,'Các mẫu gót 7cm ở bên dưới.')
    monkeypatch.setattr(client,'request',request)
    out=customer_listing.project(client.chat('Đổi sang gót 7cm, size 42.','merly-sales:web:height-repair'))
    assert len(seen)==2 and out['_repair_attempts']==1
    assert out['_recovered_reasons']==['unsupported_spec_claim']
    assert out['listing']['shown']==1 and out['stock_options']['criteria']['heel_cm']==7
    assert 'TURN_VALIDATION_FEEDBACK_JSON' in seen[1]['instructions']


def test_known_claim_cannot_treat_unknown_specs_as_confirmed():
    row={'product_id':1,'variant_id':2,'title':'Giày chưa rõ chiều cao','available':True,'known_available':1,'size':'42'}
    assert agent_answer.unsupported_heel_listing('Mẫu gót 7cm.',{},[row])
    assert not agent_answer.unsupported_heel_listing('Đây là mẫu đã tra.',{},[row])
    row['verified_specs']={'heel_cm':7}
    assert not agent_answer.unsupported_heel_listing('Mẫu gót 7cm.',{},[row])
    row['title']='Giày cao gót 10cm'
    assert agent_answer.unsupported_heel_listing('Mẫu gót 7cm.',{},[row])


def test_quote_only_exposes_allowlisted_numeric_heel_spec(heels,monkeypatch):
    monkeypatch.setattr(tools,'enrichment',lambda:{'101':{'heel_cm':7,'private_note':'PRIVATE_METADATA_SENTINEL'}})
    result,error=mcp_server.invoke('quote_variant',{'product_id':101,'variant_id':101001})
    assert not error and result['verified_specs']=={'heel_cm':7}
    assert 'PRIVATE_METADATA_SENTINEL' not in json.dumps(result)
