import json,time
import pytest
import conversation as ctx,request_resolution as r,hermes_client as c
from test_gateway import configured

def calls(**args):return [{'type':'function_call','name':'mcp__merly__search_products','call_id':'request','arguments':json.dumps(args)}]
@pytest.fixture(autouse=True)
def fresh():ctx._STATE.clear();yield;ctx._STATE.clear()
def prepare(message='tôi cần size40, đen, gót5cm'):
    ctx.prepare('x',message);return 'merly-sales:web:x'

def test_complete_fields_not_reasked_and_missing_filter_restored():
    user=prepare();assert ctx.get('x')['slots']=={'size':40,'heel_cm':5.0,'color':'den'}
    assert r.resolve(user,calls(size=40,check_stock=True))['scope']=={'size':40,'heel_cm':5.0,'color':'den'}
    text=r.failure_reply(user);assert 'size 40' in text and 'gót 5cm' in text and 'không cần nhập lại' in text

def test_only_missing_size_asked():
    user=prepare('tìm giày đen gót5cm')
    assert r.resolve(user,calls(color='đen',heel_cm=5,check_stock=True))=={'reply':'Bạn muốn mình tìm size nào, từ 35 đến 43?'}

@pytest.mark.parametrize('args',[{'size':40,'check_stock':0},{'size':40,'check_stock':None},{'size':'40','check_stock':True},{'size':40,'stock_request_id':'bad','check_stock':True},{'size':40,'url':'https://evil.invalid','check_stock':True},{'size':40,'model_code':'wrong-proposal','check_stock':True},{'size':40,'limit':100,'check_stock':True}])
def test_no_repair_bad_tokens_or_drop_unknown_constraints(args):assert r.resolve(prepare(),calls(**args)) is None

def test_multi_scopes_not_silently_narrowed():
    user=prepare();items=calls(size=40,category='a',check_stock=True)+calls(size=40,category='b',check_stock=True)
    assert r.resolve(user,items) is None

def test_native_failure_no_hidden_reader_no_extra_inference(configured,monkeypatch):
    from test_client import responses
    user=prepare();seen=[];requests=[]
    monkeypatch.setattr(c,'audit',lambda:True)
    def model(path,payload):
        requests.append(path);data=responses();data['output']=calls(size=40,check_stock=True)+data['output'];return data
    monkeypatch.setattr(c,'request',model)
    def reader(scope):seen.append(scope);return {'reply':'synthetic verified result','stock_options':{'mode':'discovery','variants':[]},'model_called':False}
    monkeypatch.setattr(c,'discover_products',reader)
    out=c.chat('tôi cần size40, đen, gót5cm',user)
    assert out['lookup_incomplete'] and out['model_called'] is True
    assert requests==['/responses'] and seen==[]

def test_time_budget_blocks_late_replay(configured):
    assert r.recover(prepare(),calls(size=40,check_stock=True),lambda *a:pytest.fail('late request'),time.time()-40) is None

def test_measurement_is_not_invented_product_code():
    user=prepare('tôi cần mẫu 5cm size40 màu đen')
    assert 'model_code' not in ctx.get('x')['slots']
    assert r.resolve(user,calls(heel_cm=5,size=40,color='đen',check_stock=True))['scope']['heel_cm']==5
    assert ctx.explicit('SKU 5CM size40')['model_code']=='5CM'

def test_color_word_inside_sku_is_not_color_request():
    values=ctx.explicit('mẫu GN-DEN-015 size40')
    assert values['model_code']=='GN-DEN-015' and 'color' not in values

@pytest.mark.parametrize('text',['vâng size40','giao đến nhà size40','giày cho bé size36','chị bạc hỏi size40'])
def test_diacritics_not_color_hallucination(text):
    assert 'color' not in ctx.explicit(text)

def test_native_tool_executes_inventory_without_gateway_recovery(configured,monkeypatch,source):
    import mcp_server,merly_tools as tools
    from test_client import responses
    p=source['products'][0];p['title']='Giày cao gót 5cm fixture'
    for v in p['variants']:v.update(option1='Đen',option2='40')
    monkeypatch.setattr(tools,'enrichment',lambda:{})
    monkeypatch.setattr(c,'audit',lambda:True)
    monkeypatch.setattr(c,'discover_products',lambda *a:pytest.fail('hidden recovery is not agent tool use'))
    seen=[]
    def model(path,payload):
        seen.append(path)
        args={'size':40,'color':'đen','heel_cm':5.0,'check_stock':True}
        result,error=mcp_server.invoke('search_products',args);assert not error
        data=responses();data['output']=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'request','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'request','output':json.dumps(result)}]+data['output']
        return data
    monkeypatch.setattr(c,'request',model)
    out=c.chat('tôi cần size40, đen, gót5cm',prepare())
    assert seen==['/responses'] and out['stock_options']['mode']=='discovery'
    assert out['stock_options']['criteria']=={'size':40,'color':'đen','heel_cm':5.0}
    assert all(v['available'] for v in out['stock_options']['variants']) and source['calls']
    assert out['reply']=='FINAL' and out['answer_mode']=='native'

from test_stock_options import source
