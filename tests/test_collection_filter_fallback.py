"""Real retrieval/inventory orchestration; synthetic Haravan, no live inference."""
import copy,json,time
import pytest
import merly_tools as t,collection_catalog as c,stock_report as s
from test_stock_options import source,product


def shoe(pid,heel=5,size='42',color='Đen'):
    p=product(pid,1);p['title']='Giày cao gót '+str(heel)+'cm fixture'
    p['variants'][0].update(option1=color,option2=size)
    return p

@pytest.fixture
def routed(source,monkeypatch):
    source['products']=[shoe(100),shoe(200)];old=t.h.get
    state={'source':source,'members':[200],'names':[{'id':11,'title':'Giày cao gót 5cm','handle':'cao-got-5cm','published_at':'2026-01-01T00:00:00Z'}],'calls':[],'error':None}
    def get(resource,params,timeout=12):
        state['calls'].append((resource,dict(params),timeout))
        if resource in ('custom_collections','smart_collections'):
            if state['error']:raise t.h.HaravanError(state['error'])
            return {resource:copy.deepcopy(state['names']) if resource=='custom_collections' else []}
        if resource=='products':
            assert params['collection_id']==11
            return {'products':copy.deepcopy([p for p in source['products'] if p['id'] in state['members']])}
        return old(resource,params)
    c.clear();monkeypatch.setattr(t.h,'get',get);monkeypatch.setattr(t,'enrichment',lambda:{})
    monkeypatch.setenv('HARAVAN_ACCESS_TOKEN','synthetic-routing-fixture-not-a-real-key')
    yield state
    c.clear()

def checked(**extra):
    args={'heel_cm':5,'color':'Đen','size':42,'check_stock':True,**extra};start=time.time()
    raw=t.dispatch('search_products',args)['stock_report']
    return s.validate(raw,None,args,start)


def test_auto_collection_prioritizes_but_does_not_restrict_catalog(routed):
    report=checked()
    assert report['routing']['strategy']=='collection_first_filters'
    assert [p['product_id'] for p in report['products']]==[200,100]
    assert {r['product_id'] for r in report['variants']}=={100,200}
    assert report['complete'] and report['criteria']=={'heel_cm':5,'color':'Đen','size':42}
    assert all(r['known_available']>0 for r in report['variants'])

@pytest.mark.parametrize('hint',[None,'Nhóm không tồn tại'])
def test_no_collection_falls_back_to_all_filters(routed,hint):
    routed['names']=[]
    report=checked(**({'collection_hint':hint} if hint else {}))
    assert report['routing']['strategy']=='filters' and report['routing']['collection_status']=='not_found'
    assert {r['product_id'] for r in report['variants']}=={100,200} and report['complete']


def test_ambiguous_optional_group_does_not_ask_customer_or_drop_filters(routed):
    routed['names'].append({'id':22,'title':'Giày cao gót 5cm mới','handle':'cao-got-moi','published_at':'2026-01-01T00:00:00Z'})
    report=checked()
    assert report['routing']['collection_status']=='ambiguous' and report['variants']
    assert not any(path=='products' for path,_,_ in routed['calls'])


def test_group_name_is_not_heel_evidence(routed):
    routed['source']['products'][1]=shoe(200,heel=7)
    report=checked()
    assert {r['product_id'] for r in report['variants']}=={100}
    assert all(p['verified_specs']['heel_cm']==5 for p in report['products'])


def test_zero_stock_in_group_continues_outside_group(routed,monkeypatch):
    def inventory(ids,locations):
        routed['source']['calls'].append(ids)
        return [{'variant_id':int(v),'loc_id':loc,'qty_available':1 if int(v)//1000==100 and i==0 else 0} for v in ids.split(',') for i,loc in enumerate(t.LOCATIONS)]
    monkeypatch.setattr(t.h,'inventory',inventory)
    report=checked()
    assert {r['product_id'] for r in report['variants'] if r['known_available']>0}=={100}
    assert [p['product_id'] for p in report['products']]==[200,100]


def test_color_and_size_must_match_same_variant(routed):
    p=shoe(200,size='38');other=copy.deepcopy(p['variants'][0]);other.update(id=200002,option1='Kem',option2='42');p['variants'].append(other)
    routed['source']['products'][1]=p
    report=checked()
    assert {r['product_id'] for r in report['variants']}=={100}

@pytest.mark.parametrize('error',['haravan_http_403','haravan_unavailable','collection_budget_exceeded'])
def test_optional_collection_failure_falls_back_without_dropping_filters(routed,error):
    routed['error']=error;report=checked()
    assert report['routing']['collection_status']=='source_unavailable'
    assert {r['product_id'] for r in report['variants']}=={100,200}
    assert report['criteria']=={'heel_cm':5,'color':'Đen','size':42}


def test_rate_limit_does_not_retry_other_haravan_endpoints(routed):
    routed['error']='haravan_http_429';report=checked()
    assert report['operation_status']=='source_error' and not report['complete']
    assert report['scan']['stop_reason']=='source_blocked'
    assert [p for p,_,_ in routed['calls']]==['custom_collections']
    assert not routed['source']['calls']


def test_required_collection_never_silently_expands(routed):
    report=checked(collection='Giày cao gót 5cm')
    assert {r['product_id'] for r in report['variants']}=={200}
    c.clear();routed['names']=[]
    report=checked(collection='Giày cao gót 5cm')
    assert report['collection_status']=='not_found' and not report['variants'] and not report['complete']


def test_large_group_cannot_take_all_early_candidate_slots():
    rows=[{'product_id':i,'_candidate_rank':0} for i in range(50)]
    result=c.prioritize(rows,set(range(49)),24)
    assert result[0]['product_id']==0 and result[4]['product_id']==49
    assert len({r['product_id'] for r in result})==50


def test_unknown_size_color_ranks_do_not_displace_exact_matches():
    rows=[{'product_id':1,'_candidate_rank':1},{'product_id':2,'_candidate_rank':0}]
    assert c.prioritize(rows,{1},24)[0]['product_id']==2


def test_routing_is_bounded_and_not_membership_evidence(routed):
    report=checked(collection_hint='Giày cao gót 5cm')
    assert 'collection' not in report['criteria'] and 'collection_evidence' not in report
    assert max(timeout for path,_,timeout in routed['calls'] if path in ('products','custom_collections','smart_collections'))<=c.PREFER_SECONDS
    assert report['routing']['preferred_products']==1


def test_missing_source_attribute_is_not_supplied_by_group_label(routed):
    for p in routed['source']['products']:p['title']='Giày chưa có chiều cao gót'
    report=checked()
    assert report['operation_status']=='metadata_missing' and not report['variants']


def test_private_collection_is_not_used_as_hint(routed):
    routed['names'][0]['published']=False;report=checked()
    assert report['routing']['collection_status']=='not_found'
    assert report['variants'] and not any(p=='products' for p,_,_ in routed['calls'])


def test_preference_finds_positive_beyond_old_candidate_window(routed,monkeypatch):
    routed['source']['products']=[shoe(i) for i in range(100,130)]+[shoe(999)]
    routed['members']=[999]
    def inventory(ids,locations):
        return [{'variant_id':int(v),'loc_id':loc,'qty_available':1 if int(v)//1000==999 and i==0 else 0} for v in ids.split(',') for i,loc in enumerate(t.LOCATIONS)]
    monkeypatch.setattr(t.h,'inventory',inventory)
    monkeypatch.delenv('HARAVAN_ACCESS_TOKEN',raising=False)
    baseline=checked(limit=1)
    before=sum(path.startswith('products/') and len(path.split('/'))==2 for path,_,_ in routed['calls'])
    assert before==24 and not any(r['known_available']>0 for r in baseline['variants'])
    assert not baseline['complete']  # never report all-shop sold-out
    routed['calls'].clear();c.clear()
    monkeypatch.setenv('HARAVAN_ACCESS_TOKEN','synthetic-routing-fixture-not-a-real-key')
    preferred=checked(limit=1)
    after=sum(path.startswith('products/') and len(path.split('/'))==2 for path,_,_ in routed['calls'])
    assert after==1 and preferred['variants'][0]['product_id']==999
    assert preferred['variants'][0]['known_available']>0 and not preferred['complete']

@pytest.mark.parametrize('routing',[
 {'strategy':'collection_first_filters','collection_status':'not_found','preferred_products':0},
 {'strategy':'filters','collection_status':'resolved','preferred_products':1},
 {'strategy':'filters','collection_status':'not_found','preferred_products':True},
])
def test_invalid_routing_metadata_is_rejected(routed,routing):
    args={'size':42,'heel_cm':5,'color':'Đen','check_stock':True};start=time.time()
    raw=t.dispatch('search_products',args)['stock_report'];raw['routing']=routing
    with pytest.raises(s.InvalidReport,match='invalid_routing'):s.validate(raw,None,args,start)


def test_lookup_log_contains_only_bounded_routing_metadata(routed):
    report=checked(collection_hint='Giày cao gót 5cm')
    info=s.lookup_diagnostics(report)[0]
    assert info['retrieval_strategy']=='collection_first_filters'
    assert info['preferred_collection_status']=='resolved'
    assert info['preferred_collection_products']==1
    assert 'Giày cao gót' not in json.dumps(info,ensure_ascii=False)


def test_collection_cache_lock_wait_obeys_deadline(monkeypatch):
    class Busy:
        def acquire(self,timeout):
            assert 0<=timeout<=.1
            return False
    monkeypatch.setattr(c,'_LOCK',Busy())
    with pytest.raises(t.h.HaravanError,match='collection_budget_exceeded'):
        c.names(t.h,time.monotonic()+.1)
