"""Set-of-products semantics using synthetic source data, never live inventory."""
import copy,time
import pytest
import merly_tools as t,stock_report,customer_listing
from test_stock_options import source,product
from test_gateway import configured

@pytest.fixture
def catalog(source,monkeypatch):
    monkeypatch.setattr(t,'enrichment',lambda:{})
    def populate(count=4,first_variants=6,heel=7,size=40,color='Nâu'):
        rows=[]
        for i in range(count):
            p=product(100+i,first_variants if i==0 else 1)
            p.update(title='Giày cao gót '+str(heel)+'cm fixture '+str(i),handle='fixture-'+str(100+i))
            for v in p['variants']:v.update(option1=color,option2=str(size))
            rows.append(p)
        source['products']=rows
        return {'heel_cm':heel,'size':size,'color':color,'check_stock':True}
    return source,populate

def execute(args):
    started=time.time();raw=t.dispatch('search_products',args)['stock_report']
    return stock_report.validate(raw,None,args,started)

def test_discovery_target_means_products_not_four_skus_of_first_product(catalog):
    state,populate=catalog;args=populate()
    report=execute(args)
    assert len({r['product_id'] for r in report['variants'] if r['known_available']>0})==4
    view=customer_listing.project({'reply':'native','stock_options':report})
    assert len({r['product_id'] for r in view['stock_options']['variants']})==4


def test_missing_metadata_explanation_is_not_erased_by_display_projection(catalog):
    state,populate=catalog;args=populate(1,1);args['occasion']='Đi làm'
    report=execute(args);assert report['operation_status']=='metadata_missing'
    view=customer_listing.project({'reply':stock_report.summary(report),'answer_mode':'evidence_guard','stock_options':report})
    assert view['reply']==stock_report.summary(report)
    assert not view.get('stock_options') and view['listing']['shown']==0

@pytest.mark.parametrize('heel,size,color',[(2.5,35,'Trắng Kem'),(9,43,'Đỏ Rượu'),(5,39,'Đen')])
def test_multi_product_matching_is_not_a_specific_customer_phrase(catalog,heel,size,color):
    state,populate=catalog;report=execute(populate(4,6,heel,size,color))
    assert report['selection']=={'scope':'verified_positive_subset','kind':'multiple_products','products':4,'skus':9}
    assert report['scan']['target_kind']=='products' and report['scan']['positive_products']==4
    assert all(r['size']==str(size) and r['color']==color for r in report['variants'])
    view=customer_listing.project({'reply':'native','stock_options':report})
    assert view['listing']['shown_products']==4 and view['listing']['verified_positive_products']==4

@pytest.mark.parametrize('count,kind',[(1,'single_product'),(2,'multiple_products')])
def test_single_or_multiple_products_still_retains_their_distinct_skus(catalog,count,kind):
    state,populate=catalog;report=execute(populate(count,6))
    assert report['selection']['kind']==kind and report['selection']['products']==count
    view=customer_listing.project({'reply':'native','stock_options':report})
    assert view['listing']['shown_products']==count and view['listing']['shown']<=4


def test_only_relevant_unknown_attributes_are_reported(catalog):
    state,populate=catalog;args=populate(3,1);args['occasion']='Fixture occasion'
    state['products'][1]['title']='Giày cao gót 8cm mismatching fixture'
    state['products'][2]['title']='Giày cao gót 9cm mismatching fixture'
    report=execute(args)
    assert report['coverage']['unknown_spec_products']==1
    assert report['unverified_criteria']==['occasion']
    text=stock_report.summary(report)
    assert 'dịp sử dụng' in text and 'chiều cao gót' not in text
    assert state['calls']==[]


def test_verified_zero_and_unknown_inventory_do_not_become_same_result(catalog,monkeypatch):
    state,populate=catalog;args=populate(3,1)
    monkeypatch.setattr(t.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':0} for v in ids.split(',') for loc in t.LOCATIONS])
    zero=execute(args);assert zero['operation_status']=='verified_zero' and zero['selection']['kind']=='none_verified'
    view=customer_listing.project({'reply':stock_report.summary(zero),'answer_mode':'evidence_guard','stock_options':zero})
    assert view['listing']['shown']==0 and 'tồn 0' in view['reply']
    monkeypatch.setattr(t.h,'inventory',lambda *a:[])
    unknown=execute(args);assert unknown['operation_status']=='partial' and not unknown['complete']
    view=customer_listing.project({'reply':stock_report.summary(unknown),'answer_mode':'evidence_guard','stock_options':unknown})
    assert view['listing']['shown']==0 and 'chưa được xác minh' in view['reply']


def test_fresh_product_attributes_still_have_to_match(catalog,monkeypatch):
    state,populate=catalog;args=populate(2,1);get=t.h.get
    def changed(resource,params):
        value=get(resource,params)
        if 'product' in value:value['product']['title']='Giày chưa có dữ liệu chiều cao'
        return value
    monkeypatch.setattr(t.h,'get',changed)
    report=execute(args)
    assert report['operation_status']=='metadata_missing' and report['unverified_criteria']==['heel_cm']
    assert report['selection']['products']==0 and state['calls']==[]


def test_missing_variant_field_does_not_poison_known_mismatches(catalog):
    state,populate=catalog;args=populate(1,3)
    variants=state['products'][0]['variants']
    variants[1].update(option1=None,option2='35',title='',sku='UNKNOWN-COLOR')
    variants[2].update(option1='Trắng',option2=None,title='',sku='UNKNOWN-SIZE')
    report=execute(args)
    assert report['complete'] and report['unverified_criteria']==[]
    assert len(report['variants'])==1

@pytest.mark.parametrize('kind',['missing_field','wrong_product_count','false_target'])
def test_result_diagnostics_cannot_forge_scope_or_cardinality(catalog,kind):
    state,populate=catalog;args=populate(4,6);started=time.time()
    raw=t.dispatch('search_products',args)['stock_report']
    if kind=='missing_field':raw['unverified_criteria']=['phone_number']
    elif kind=='wrong_product_count':raw['scan']['positive_products']=100
    else:raw['scan']['target_kind']='arbitrary'
    with pytest.raises(stock_report.InvalidReport):stock_report.validate(raw,None,args,started)


def test_display_diversity_does_not_mutate_the_verified_report(catalog):
    state,populate=catalog;report=execute(populate(4,6))
    original=copy.deepcopy(report)
    quotes=[dict(report['variants'][i]) for i in (0,1)]
    view=customer_listing.project({'reply':'native','stock_options':report,'quotes':quotes})
    visible=view.get('quotes',[])+view['stock_options']['variants']
    assert len(visible)==4 and len({r['product_id'] for r in visible})==4
    assert report==original and len(report['variants'])==9


def test_logging_metadata_never_copies_customer_text_or_product_identifiers(catalog):
    import json
    state,populate=catalog;report=execute(populate(2,2))
    report['criteria']['query']='PRIVATE_USER_SENTINEL'
    report['products'][0]['title']='PRIVATE_TITLE_SENTINEL'
    data=stock_report.lookup_diagnostics(report)
    assert data[0]['verified_positive_products']==2 and 'query' in data[0]['criteria_fields']
    text=json.dumps(data)
    assert not any(value in text for value in ('PRIVATE_USER_SENTINEL','PRIVATE_TITLE_SENTINEL','fixture-100','variant_id','product_id'))


def test_quote_with_same_size_color_cannot_override_other_product_criteria(catalog):
    state,populate=catalog;report=execute(populate(4,1))
    foreign={**report['variants'][0],'product_id':999,'variant_id':999001,'product_url':'https://merlyshoes.com/products/foreign-fixture'}
    view=customer_listing.project({'reply':'native','stock_options':report,'quotes':[foreign]})
    assert not view.get('quotes') and view['listing']['shown_products']==4
    assert all(r['product_id']!=999 for r in view['stock_options']['variants'])


def test_gateway_records_set_diagnostics_without_private_fields(catalog,configured,monkeypatch,caplog):
    import json,logging,hermes_client as c,mcp_server
    from test_gateway import call
    from gateway.platforms.api_server_openai_routes import OpenAICompatRoutesMixin as NativeAPI
    from tools.mcp_tool_handlers import _render_call_tool_result
    import mcp.types as mt
    state,populate=catalog;args=populate(4,6)
    monkeypatch.setattr(c,'audit',lambda:True)
    def request(path,payload):
        result,error=mcp_server.invoke('search_products',args);assert not error
        tool=mt.CallToolResult(content=[mt.TextContent(text=json.dumps(result))],structuredContent=result)
        messages=[{'role':'assistant','tool_calls':[{'id':'set','type':'function','function':{'name':'mcp__merly__search_products','arguments':json.dumps(args)}}]},{'role':'tool','tool_call_id':'set','content':_render_call_tool_result(tool,'merly')}]
        items=NativeAPI._extract_output_items({'messages':messages,'final_response':'NATIVE_FIXTURE_REPLY'})
        return {'id':'resp_gateway_sets','status':'completed','output':items}
    monkeypatch.setattr(c,'request',request)
    with caplog.at_level(logging.INFO,logger='merly.gateway'):response=call('PRIVATE_USER_SENTINEL')
    assert response['status'].startswith('200') and response['body']['listing']['shown_products']==4
    assert not any(k.startswith('_') for k in response['body'])
    assert 'lookup_diagnostics' in caplog.text and '"verified_positive_products": 4' in caplog.text
    assert 'PRIVATE_USER_SENTINEL' not in caplog.text
