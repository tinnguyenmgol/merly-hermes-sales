"""Real backend orchestration with synthetic Haravan transport, never live stock."""
import copy,json,time
import pytest
import merly_tools as tools,product_discovery as d,stock_report
from test_stock_options import source,product

@pytest.fixture
def setup(source,monkeypatch):
    p=product(100,3);p['title']='Giày cao gót 10cm fixture'
    for v in p['variants']:v.update(option1='Đen',option2='42')
    source['products']=[p];monkeypatch.setattr(tools,'enrichment',lambda:{})
    return source

def query(**extra):return {'heel_cm':10.0,'size':42,'color':'Đen','check_stock':True,**extra}
def report(**extra):return tools.dispatch('search_products',query(**extra))['stock_report']
def checked(**extra):
    start=time.time();args=query(**extra);r=tools.dispatch('search_products',args)['stock_report']
    return stock_report.validate(r,None,args,start)

def test_generic_request_has_no_fake_model_code_and_live_inventory(setup):
    r=checked();assert r['mode']=='discovery' and r['complete']
    assert 'model_code' not in r['criteria'] and len(r['variants'])==3
    assert all(v['available'] is True and v['size']=='42' and v['color']=='Đen' for v in r['variants'])
    assert setup['calls']==[[100001,100002,100003]]
    assert '1 mẫu còn hàng' in stock_report.summary(r)

@pytest.mark.parametrize('height,size,color',[(3.5,35,'Trắng Kem'),(7.0,40,'Nâu'),(12.0,43,'Đỏ Rượu')])
def test_algorithm_not_specific_to_test_question(setup,height,size,color):
    p=setup['products'][0];p['title']='Giày gót '+str(height)+'cm fixture'
    for v in p['variants']:v.update(option1=color,option2=str(size))
    r=checked(heel_cm=height,size=size,color=color)
    assert r['variants'] and r['criteria']=={'heel_cm':height,'size':size,'color':color}
    assert all(v['available'] for v in r['variants'])

def test_missing_metadata_not_no_stock(setup):
    setup['products'][0]['title']='Giày fixture chưa có gót'
    r=checked();assert r['operation_status']=='metadata_missing' and not r['complete']
    assert not r['variants'] and setup['calls']==[]

def test_verified_zero_and_unknown_are_distinct(setup,monkeypatch):
    monkeypatch.setattr(tools.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':0} for v in ids.split(',') for loc in tools.LOCATIONS])
    r=checked();assert r['operation_status']=='verified_zero' and all(v['available'] is False for v in r['variants'])
    monkeypatch.setattr(tools.h,'inventory',lambda ids,locs:[])
    r=checked();assert r['operation_status']=='partial' and all(v['available'] is None for v in r['variants'])

def test_partial_warehouse_positive_preserved(setup,monkeypatch):
    monkeypatch.setattr(tools.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':next(iter(tools.LOCATIONS)),'qty_available':2} for v in ids.split(',')])
    r=checked();assert r['operation_status']=='partial_available'
    assert all(v['available'] is True and not v['inventory_complete'] for v in r['variants'])

def test_one_product_failure_preserves_other_results(setup,monkeypatch):
    p=copy.deepcopy(setup['products'][0]);p['id']=200;p['handle']='fixture-other'
    for i,v in enumerate(p['variants']):v.update(id=200001+i,product_id=200)
    setup['products'].append(p);get=tools.h.get
    def fail(resource,params):
        if resource=='products/200':raise tools.h.HaravanError('haravan_http_503')
        return get(resource,params)
    monkeypatch.setattr(tools.h,'get',fail)
    r=checked();assert r['operation_status']=='partial_available' and len(r['products'])==2
    assert r['products'][1]['status']=='source_unavailable'
    assert len(r['variants'])==3 and all(v['available'] for v in r['variants'])

def test_changed_live_heel_not_presented_as_matching(setup,monkeypatch):
    get=tools.h.get
    def changed(resource,params):
        value=get(resource,params)
        if resource=='products/100':value['product']['title']='Giày gót 11cm'
        return value
    monkeypatch.setattr(tools.h,'get',changed)
    r=checked();assert not r['variants'] and r['products'][0]['status']=='changed'
    assert setup['calls']==[]

def test_cream_and_white_cream_not_merged(setup):
    setup['products'][0]['variants'][0]['option1']='Trắng Kem'
    setup['products'][0]['variants'][1]['option1']='Kem'
    r=checked(color='Kem');assert [v['variant_id'] for v in r['variants']]==[100002]

def test_after_12th_variant_checked_but_bounded_coverage_explicit(setup):
    p=product(100,60);p['title']='Giày cao gót 10cm'
    for v in p['variants']:v.update(option1='Đen',option2='42')
    setup['products']=[p]
    r=checked();assert len(r['variants'])==40 and r['coverage']['omitted_variants']==20 and not r['complete']
    assert r['variants'][13]['available'] is True

@pytest.mark.parametrize('mutate',[
 lambda r:r['criteria'].update(heel_cm=9),
 lambda r:r.update(checked_at='2020-01-01T00:00:00+00:00'),
 lambda r:r['variants'][0].update(size='41'),
 lambda r:r['variants'][0].update(color='Nâu'),
 lambda r:r['variants'][0].update(product_id=999),
 lambda r:r['products'][0]['verified_specs'].update(heel_cm=9),
 lambda r:r['variants'][0].update(product_url='https://evil.invalid/')])
def test_contract_rejects_wrong_criteria_stale_or_mixed_evidence(setup,mutate):
    start=time.time();r=report();mutate(r)
    with pytest.raises(stock_report.InvalidReport):stock_report.validate(r,None,query(),start)

def test_full_tool_call_provenance_and_report_extraction(setup):
    import mcp_server
    start=time.time();args=query();result,error=mcp_server.invoke('search_products',args)
    assert not error
    items=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'fixture-call','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'fixture-call','output':json.dumps(result)}]
    r,requested=stock_report.extract(items,None,start)
    assert requested and r['mode']=='discovery' and all(v['available'] for v in r['variants'])

def test_real_agent_adapter_routes_report_without_narrowing_criteria(setup,monkeypatch,tmp_path):
    monkeypatch.setenv("HERMES_PILOT_STATE_DB",str(tmp_path/"agent-sessions.db"))
    import hermes_client as client,mcp_server,conversation as ctx
    from test_client import responses
    user='merly-sales:web:'+'b'*64;message='tìm giày cao 10cm size42 màu đen'
    ctx.prepare('b'*64,message)
    monkeypatch.setattr(client,'audit',lambda:True)
    monkeypatch.setattr(client,'probe_stock',lambda *a,**kw:pytest.fail('cannot drop heel criterion'))
    calls=[]
    def request(path,payload):
        calls.append(path);result,error=mcp_server.invoke('search_products',query())
        assert not error
        r=responses(contract=True);r['output']=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'discovery','arguments':json.dumps(query())},{'type':'function_call_output','call_id':'discovery','output':json.dumps(result)}]+r['output'];return r
    monkeypatch.setattr(client,'request',request)
    r=client.chat(message,user)
    assert calls==['/responses'] and r['stock_options']['mode']=='discovery'
    assert r['reply']=='FINAL' and len(r['stock_options']['variants'])==3

def test_supported_criteria_with_model_are_not_rejected_or_dropped(setup):
    setup['products'][0]['title']='Giày cao gót 10cm mã GN-025'
    r=checked(model_code='GN-025')
    assert r['criteria']['model_code']=='GN-025' and all(v['available'] for v in r['variants'])
    assert not checked(model_code='GN_025')['variants']

def test_generic_size_proposal_requires_confirmation_not_foot_inference():
    import conversation as ctx
    sid='test-size';ctx.forget(sid);ctx.prepare(sid,'chân 26cm cần tìm giày')
    question=ctx.observe('merly-sales:web:'+sid,[{'type':'function_call','name':'mcp__merly__search_products','arguments':query()}])
    assert 'chưa tự chốt size' in question
    assert ctx.prepare(sid,'đúng rồi')=={'route':'catalog','scope':{'size':42,'limit':4}}
    ctx.forget(sid)

def test_real_internal_http_and_gateway_client(setup,monkeypatch):
    import stock_probe,hermes_client as client,threading,urllib.request,urllib.error
    monkeypatch.setenv('API_SERVER_KEY','K'*40)
    for key,value in {'HERMES_SALES_API_KEY':'K'*40,'HERMES_SALES_API_BASE':'https://offline.invalid/v1','HERMES_SALES_ISOLATION_APPROVED':'1','HERMES_CUSTOMER_DATA_APPROVED':'1','HERMES_MODEL_COST_APPROVED':'1'}.items():monkeypatch.setenv(key,value)
    server=stock_probe.make_server(('127.0.0.1',0));threading.Thread(target=server.serve_forever,daemon=True).start()
    actual=urllib.request.build_opener(client.NoRedirect);url='http://127.0.0.1:'+str(server.server_port)+'/discover'
    class Local:
        def open(self,req,timeout):
            assert req.full_url=='http://hermes-sales:8644/discover'
            req=urllib.request.Request(url,data=req.data,headers=dict(req.header_items()),method='POST')
            return actual.open(req,timeout=timeout)
    try:
        monkeypatch.setattr(client.urllib.request,'build_opener',lambda *a:Local())
        r=client.discover_products({'heel_cm':10.0,'size':42,'color':'Đen','limit':4})
        assert r['model_called'] is False and r['stock_options']['mode']=='discovery'
        assert all(v['available'] for v in r['stock_options']['variants'])
        body=json.dumps({'size':42,'url':'https://evil.invalid'}).encode()
        req=urllib.request.Request(url,data=body,headers={'Authorization':'Bearer '+'K'*40,'Content-Type':'application/json'},method='POST')
        with pytest.raises(urllib.error.HTTPError) as e:actual.open(req)
        assert e.value.code==400
    finally:server.shutdown();server.server_close()

def test_different_criteria_do_not_collapse_to_one_stock_scope(setup):
    p=copy.deepcopy(setup['products'][0]);p.update(id=200,title='Giày cao gót 12cm',handle='fixture-other')
    for i,v in enumerate(p['variants']):v.update(id=200001+i,product_id=200)
    setup['products'].append(p);start=time.time();items=[]
    for i,height in enumerate((10.0,12.0)):
        args=query(heel_cm=height);result=tools.dispatch('search_products',args)
        items.extend([{'type':'function_call','name':'mcp__merly__search_products','call_id':str(i),'arguments':json.dumps(args)},{'type':'function_call_output','call_id':str(i),'output':json.dumps(result)}])
    r,_=stock_report.extract(items,None,start)
    assert r['mode']=='groups' and len(r['groups'])==2
    assert {g['criteria']['heel_cm'] for g in r['groups']}=={10,12}
