"""Synthetic Haravan transport: scan bounds and exact scope, not live stock."""
import copy,time
import pytest
import merly_tools as t,stock_report,product_discovery as d,customer_listing
from test_stock_options import source,product
from test_product_discovery import query

@pytest.fixture
def items(source,monkeypatch):
    monkeypatch.setattr(t,'enrichment',lambda:{})
    def prepare(count,color='Đen'):
        rows=[]
        for pid in range(100,100+count):
            p=product(pid,1);p.update(title='Giày cao gót 10cm fixture '+str(pid),handle='fixture-'+str(pid))
            for v in p['variants']:v.update(option1=color,option2='42')
            rows.append(p)
        source['products']=rows;return rows
    return source,prepare

def checked(**extra):
    start=time.time();args=query(**extra)
    raw=t.dispatch('search_products',args)['stock_report']
    return stock_report.validate(raw,None,args,start)

def test_reaches_positive_inventory_after_first_four(items,monkeypatch):
    state,prepare=items;prepare(12)
    def inventory(ids,locs):
        values=list(map(int,ids.split(',')));state['calls'].append(values)
        return [{'variant_id':v,'loc_id':loc,'qty_available':1 if v//1000>=104 and i==0 else 0} for v in values for i,loc in enumerate(t.LOCATIONS)]
    monkeypatch.setattr(t.h,'inventory',inventory)
    report=checked();positive=customer_listing.positive_rows(report)
    assert {r['product_id'] for r in positive}=={104,105,106,107}
    assert len(state['calls'])==8 and report['scan']['stop_reason']=='enough_positive'
    assert report['coverage']['omitted_products']==4 and not report['complete']
    visible=customer_listing.project({'reply':'fixture','stock_options':report})
    assert visible['listing']['shown']==4 and all(r['known_available']>0 for r in visible['stock_options']['variants'])

def test_cached_color_ranking_is_not_a_fresh_inventory_filter(items,monkeypatch):
    state,prepare=items;rows=prepare(6);rows[4]['variants'][0]['option1']='Trắng'
    get=t.h.get;visited=[]
    def fresh(resource,params):
        value=get(resource,params);pid=int(resource.split('/')[1])
        if resource=='products/'+str(pid):visited.append(pid)
        if pid==104:
            if 'product' in value:value['product']['variants'][0]['option1']='Đen'
            for v in value.get('variants',[]):v['option1']='Đen'
        return value
    monkeypatch.setattr(t.h,'get',fresh)
    monkeypatch.setattr(t.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':1 if int(v)//1000==104 and i==0 else 0} for v in ids.split(',') for i,loc in enumerate(t.LOCATIONS)])
    report=checked(limit=1)
    assert customer_listing.positive_rows(report)[0]['product_id']==104
    assert visited==[100,101,102,103,105,104]

def test_scan_cap_is_partial_not_global_no_match(items):
    _,prepare=items;prepare(30,color='Kem Sữa')
    report=checked()
    assert len(report['products'])==24 and report['coverage']['omitted_products']==6
    assert report['scan']['stop_reason']=='product_limit' and not report['complete']
    assert report['operation_status']=='partial_no_match' and not report['variants']
    assert 'Chưa kiểm tra hết' in stock_report.summary(report)

def test_display_limit_does_not_limit_candidate_scanning(items,monkeypatch):
    _,prepare=items;prepare(8)
    monkeypatch.setattr(t.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':1 if int(v)//1000==107 and i==0 else 0} for v in ids.split(',') for i,loc in enumerate(t.LOCATIONS)])
    report=checked(limit=1)
    assert len(report['products'])==8 and customer_listing.positive_rows(report)[0]['product_id']==107

@pytest.mark.parametrize('status',[401,403,429])
def test_source_blocked_stops_without_repeated_requests(items,monkeypatch,status):
    state,prepare=items;prepare(12);calls=[]
    def blocked(*args):calls.append(args);raise t.h.HaravanError('haravan_http_'+str(status))
    monkeypatch.setattr(t.h,'inventory',blocked)
    report=checked()
    assert len(calls)==1 and len(report['products'])==1 and not report['complete']
    assert report['scan']['stop_reason']=='source_blocked' and not customer_listing.positive_rows(report)

def test_expired_budget_never_starts_inventory_or_next_product(items,monkeypatch):
    state,prepare=items;prepare(8);clock=[0.0];get=t.h.get;reads=[]
    monkeypatch.setattr(d.time,'monotonic',lambda:clock[0])
    def slow(resource,params):
        reads.append(resource);result=get(resource,params);clock[0]+=6;return result
    monkeypatch.setattr(t.h,'get',slow)
    report=checked()
    assert len(reads)==3 and not state['calls'] and len(report['products'])==1
    assert report['scan']['stop_reason']=='time_limit' and not report['complete']

@pytest.mark.parametrize('field,value',[('positive_variants',99),('products_examined',0),('target',5),('stop_reason','invented')])
def test_scan_metadata_is_checked(items,field,value):
    _,prepare=items;prepare(2);start=time.time();args=query()
    raw=t.dispatch('search_products',args)['stock_report'];raw['scan'][field]=value
    with pytest.raises(stock_report.InvalidReport,match='invalid_scan'):stock_report.validate(raw,None,args,start)

def test_candidate_limit_is_not_a_public_tool_argument(items):
    _,prepare=items;prepare(2)
    with pytest.raises(t.Invalid,match='unknown_fields'):t.dispatch('search_products',{**query(),'candidate_limit':24})

def test_joint_variant_ranking_uses_more_than_twelve_cached_variants(items):
    state,prepare=items;rows=prepare(2)
    p=product(101,20);p.update(title='Giày cao gót 10cm fixture',handle='fixture-101')
    for v in p['variants']:v.update(option1='Trắng',option2='38')
    p['variants'][13].update(option1='Đen',option2='42');rows[0]['variants'][0]['option1']='Kem';state['products']=[rows[0],p]
    result=t.search_products({'size':42,'color':'Đen','limit':1},candidate_only=True,candidate_limit=24)
    assert result['products'][0]['product_id']==101
    report=checked(limit=1)
    assert [r['variant_id'] for r in customer_listing.positive_rows(report)]==[101014]

def test_variant_bound_is_not_global_zero(items,monkeypatch):
    state,prepare=items;rows=prepare(2);p=product(100,60);p.update(title='Giày cao gót 10cm fixture',handle='fixture-100')
    for v in p['variants']:v.update(option1='Đen',option2='42')
    state['products']=[p,rows[1]]
    monkeypatch.setattr(t.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':0} for v in ids.split(',') for loc in t.LOCATIONS])
    report=checked()
    assert len(report['variants'])==40 and report['coverage']['omitted_variants']==20
    assert report['coverage']['omitted_products']==1 and report['scan']['stop_reason']=='variant_limit'
    assert not report['complete'] and report['operation_status'] not in ('no_match','verified_zero')

def test_source_block_on_last_candidate_is_still_reported(items,monkeypatch):
    _,prepare=items;prepare(1)
    def blocked(*a):raise t.h.HaravanError('haravan_http_429')
    monkeypatch.setattr(t.h,'inventory',blocked)
    assert checked()['scan']['stop_reason']=='source_blocked'

def test_scan_time_is_added_to_index_age(items,monkeypatch):
    _,prepare=items;prepare(1);clock=[0.0];get=t.h.get
    monkeypatch.setattr(d.time,'monotonic',lambda:clock[0]);monkeypatch.setattr(t.catalog,'status',lambda:{'ready':True,'age_seconds':299})
    def slow(resource,params):
        value=get(resource,params);clock[0]+=.5;return value
    monkeypatch.setattr(t.h,'get',slow)
    start=time.time();args=query();raw=t.dispatch('search_products',args)['stock_report']
    assert raw['catalog_age_seconds']>300
    report=stock_report.validate(raw,None,args,start)
    assert not report['complete']
    assert report['operation_status']=='partial_available' and customer_listing.positive_rows(report)

def test_variant_titles_are_joined_from_one_source_parent(items):
    _,prepare=items;prepare(1);args=query();start=time.time();raw=t.dispatch('search_products',args)['stock_report']
    assert all('title' not in r for r in raw['variants'])
    validated=stock_report.validate(raw,None,args,start)
    assert validated['variants'][0]['title']==validated['products'][0]['title']

def test_early_stop_keeps_collection_membership_for_examined_products(items,monkeypatch):
    import collection_catalog
    _,prepare=items;rows=prepare(12)
    group={'status':'resolved','collection':{'id':99,'title':'Nhóm fixture','handle':'nhom-fixture'},'products':copy.deepcopy(rows)}
    monkeypatch.setattr(collection_catalog,'resolve',lambda *a:copy.deepcopy(group))
    report=checked(collection='Nhóm fixture')
    assert len(report['products'])==4 and report['coverage']['omitted_products']==8
    assert set(report['collection_evidence']['product_ids'])=={r['product_id'] for r in report['products']}
    assert not report['complete']


def test_later_match_survives_native_responses_serialization(items,monkeypatch):
    from test_integrated_stock_v2 import wire
    _,prepare=items;prepare(7)
    monkeypatch.setattr(t.h,'inventory',lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':1 if int(v)//1000==106 and i==0 else 0} for v in ids.split(',') for i,loc in enumerate(t.LOCATIONS)])
    args=query(limit=1);start=time.time();raw=t.dispatch('search_products',args)['stock_report']
    parsed,requested=stock_report.extract(wire(raw,args=args),None,start)
    assert requested and customer_listing.positive_rows(parsed)[0]['product_id']==106
    assert parsed['scan']['products_examined']==7
