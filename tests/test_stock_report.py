"""Real client parsing, synthetic model/tool outputs, zero provider calls."""
import copy,json
import hermes_client as c
import stock_report as s
from test_stock_options import source,lookup,TOKEN
from test_client import approved,responses

def envelope(report,kind='string'):
    output=json.dumps({'result':json.dumps({'stock_report':report},ensure_ascii=False)})
    if kind=='blocks':output=[{'type':'input_text','text':output}]
    return [
      {'type':'function_call','name':'mcp__merly__search_products','call_id':'call_test','arguments':json.dumps({'model_code':'1514','size':38,'check_stock':True,'stock_request_id':TOKEN})},
      {'type':'function_call_output','call_id':'call_test','output':output}
    ]

def test_client_corrects_model_that_omits_colors(source,approved,monkeypatch):
    report=lookup();monkeypatch.setattr(c,'audit',lambda:True);monkeypatch.setattr(c.secrets,'token_hex',lambda n:TOKEN)
    def request(path,payload):
        assert TOKEN not in payload['instructions']
        data=responses();data['output']=envelope(report,'blocks')+data['output']
        data['output'][-1]['content'][0]['text']='SYNTHETIC WRONG SUMMARY: only one color'
        return data
    monkeypatch.setattr(c,'request',request)
    reply=c.chat('fixture stock request','fixture-user')
    assert 'WRONG SUMMARY' not in reply['reply']
    assert len(reply['stock_options']['variants'])==20
    assert {'Kem','Chì Bóng'}<={v['color'] for v in reply['stock_options']['variants']}

def test_wrong_turn_fail_closed(source):
    report=lookup();report['stock_request_id']='b'*32
    result,requested=s.extract(envelope(report),TOKEN)
    assert requested and result['mode']=='unverified'

def test_corrupted_count_not_trusted(source):
    report=lookup();report['coverage']['variants_checked']=1
    result,requested=s.extract(envelope(report),TOKEN)
    assert requested and result['mode']=='unverified'

def test_wrong_product_link_rejected(source):
    report=lookup();report['variants'][0]['product_url']='https://evil.invalid/products/fake'
    assert s.extract(envelope(report),TOKEN)[0]['mode']=='unverified'

def test_assistant_cannot_forge_stock_cards(source):
    fake={'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps({'stock_report':lookup()})}]}
    assert s.extract([fake],TOKEN)==(None,False)

def test_two_scopes_not_silently_reduced(source):
    first=lookup();second=copy.deepcopy(first);second['model_code']='1676'
    items=envelope(first)+envelope(second)
    items[2]['call_id']='call_second';items[2]['arguments']=items[2]['arguments'].replace('1514','1676')
    items[3]['call_id']='call_second'
    report,requested=s.extract(items,TOKEN)
    assert requested and report['mode']=='groups' and len(report['groups'])==2

def test_second_scope_failure_remains_visible(source):
    items=envelope(lookup());args={'model_code':'1676','size':38,'check_stock':True,'stock_request_id':TOKEN}
    items+=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'second','arguments':json.dumps(args)}, {'type':'function_call_output','call_id':'second','output':'{"error":"synthetic_failure"}'}]
    report,requested=s.extract(items,TOKEN)
    assert requested and report['mode']=='groups' and len(report['groups'])==2
    assert report['groups'][1]['mode']=='unverified' and report['groups'][1]['model_code']=='1676'

def test_unsafe_browser_integer_not_rounded_into_price(source):
    report=lookup();report['variants'][0]['price_vnd']=9007199254740992
    assert s.extract(envelope(report),TOKEN)[0]['mode']=='unverified'
