"""Synthetic Haravan fixtures only. Never assert real price/stock from these tests."""
import copy
import pytest
import merly_tools as t
import stock_report
TOKEN='a'*32

def product(pid=100,count=20):
    variants=[]
    for i in range(count):
        color='Kem' if i==13 else 'Chì Bóng' if i==14 else 'Màu fixture '+str(i)
        variants.append({'id':pid*1000+i+1,'product_id':pid,'sku':'fixture-'+str(i),'option1':color,'option2':'38','title':color+' / 38','price':'310000'})
    return {'id':pid,'title':'Giày fixture 1514','handle':'fixture-source-handle','published_at':'fixture','options':[{'name':'Màu','position':1},{'name':'Size','position':2}],'variants':variants}

def api_response(product,resource,params):
    if resource.endswith('/variants/count'):return {'count':len(product['variants'])}
    if resource.endswith('/variants'):
        start=(params.get('page',1)-1)*params.get('limit',50)
        return {'variants':copy.deepcopy(product['variants'][start:start+params.get('limit',50)])}
    return {'product':copy.deepcopy(product)}

@pytest.fixture
def source(monkeypatch):
    state={'products':[product()],'calls':[]}
    monkeypatch.setattr(t.catalog,'snapshot',lambda:copy.deepcopy(state['products']))
    monkeypatch.setattr(t.catalog,'status',lambda:{'ready':True,'age_seconds':1})
    monkeypatch.setattr(t.h,'get',lambda resource,params:api_response(next(p for p in state['products'] if p['id']==int(resource.split('/')[1])),resource,params))
    def inventory(ids,locations):
        parsed=list(map(int,ids.split(',')));assert len(parsed)<=10;state['calls'].append(parsed)
        return [{'variant_id':vid,'loc_id':loc,'qty_available':1 if n==0 else 0} for vid in parsed for n,loc in enumerate(t.LOCATIONS)]
    monkeypatch.setattr(t.h,'inventory',inventory)
    return state

def lookup(**extra):
    return t.dispatch('search_products',{'model_code':'1514','size':38,'check_stock':True,'stock_request_id':TOKEN,**extra})['stock_report']

def test_all_colors_not_first12_or_limit(source):
    report=lookup(limit=1)
    assert report['complete'] and len(report['variants'])==20 and report['coverage']['variants_checked']==20
    colors=[v['color'] for v in report['variants']]
    assert 'Kem' in colors and 'Chì Bóng' in colors and len(source['calls'])==2
    assert stock_report.validate(report,TOKEN,{'model_code':'1514','size':38})['complete']

def test_more_than_four_product_records(source):
    source['products']=[product(pid,3) for pid in range(100,106)]
    report=lookup(limit=1)
    assert len(report['variants'])==18 and report['coverage']['products_checked']==6 and report['complete']

def test_inventory_missing_is_unknown_not_out_of_stock(source,monkeypatch):
    monkeypatch.setattr(t.h,'inventory',lambda *a:[])
    report=lookup();assert not report['complete'] and all(v['available'] is None for v in report['variants'])
    assert 'một phần' in stock_report.summary(report)

def test_partial_warehouse_positive_is_known_minimum(source,monkeypatch):
    monkeypatch.setattr(t.h,'inventory',lambda ids,locs:[{'variant_id':int(vid),'loc_id':next(iter(t.LOCATIONS)),'qty_available':1} for vid in ids.split(',')])
    report=lookup();assert not report['complete'] and all(v['available'] is True and not v['inventory_complete'] for v in report['variants'])

def test_true_zero_requires_all_locations(source,monkeypatch):
    monkeypatch.setattr(t.h,'inventory',lambda ids,locs:[{'variant_id':int(vid),'loc_id':loc,'qty_available':0} for vid in ids.split(',') for loc in t.LOCATIONS])
    report=lookup();assert report['complete'] and all(v['available'] is False for v in report['variants'])

def test_large_scope_marks_omission(source):
    source['products']=[product(100,60),product(101,45)];report=lookup()
    assert len(report['variants'])==100 and report['coverage']['omitted_variants']==5 and not report['complete']

def test_stale_index_not_global_complete(source,monkeypatch):
    monkeypatch.setattr(t.catalog,'status',lambda:{'ready':True,'age_seconds':301})
    assert not lookup()['complete']

def test_one_batch_failure_preserves_unknown(source,monkeypatch):
    base=t.h.inventory;calls=[]
    def inventory(*args):
        calls.append(1)
        if len(calls)==2:raise t.h.HaravanError('synthetic_failure')
        return base(*args)
    monkeypatch.setattr(t.h,'inventory',inventory)
    report=lookup();assert not report['complete']
    assert sum(v['available'] is True for v in report['variants'])==10
    assert sum(v['available'] is None for v in report['variants'])==10

def test_fresh_product_instead_of_truncated_snapshot(source,monkeypatch):
    fresh=copy.deepcopy(source['products'][0]);source['products'][0]['variants']=fresh['variants'][:12]
    monkeypatch.setattr(t.h,'get',lambda resource,params:api_response(fresh,resource,params))
    assert len(lookup()['variants'])==20

def test_explicit_color_scope_named_not_all_colors(source):
    report=lookup(color='Chì Bóng');assert len(report['variants'])==1
    assert 'màu Chì Bóng' in stock_report.summary(report)

@pytest.mark.parametrize('data',[{'check_stock':True,'model_code':'1514'}, {'check_stock':True,'model_code':'1514','size':True}, {'check_stock':True,'model_code':'1514','size':38,'stock_request_id':TOKEN,'heel_cm':5}])
def test_incomplete_or_unsupported_scope_rejected(source,data):
    with pytest.raises(t.Invalid):t.dispatch('search_products',data)

def test_numeric_string_inventory_id_matches_without_rewriting(source,monkeypatch):
    original=t.h.inventory
    def inventory(*a):
        rows=original(*a)
        for row in rows:row['variant_id']=str(row['variant_id'])
        return rows
    monkeypatch.setattr(t.h,'inventory',inventory)
    assert lookup()['complete']

def test_duplicate_inventory_row_not_double_counted(source,monkeypatch):
    original=t.h.inventory
    def inventory(*a):
        rows=original(*a);return rows+[dict(rows[0])]
    monkeypatch.setattr(t.h,'inventory',inventory)
    report=lookup();assert not report['complete'] and all(v['available'] is None for v in report['variants'])

def test_product_fetch_failure_not_no_stock(source,monkeypatch):
    def fail(*a):raise t.h.HaravanError('synthetic_network_error')
    monkeypatch.setattr(t.h,'get',fail)
    report=lookup();assert not report['complete'] and report['coverage']['unverified_products']==1

def test_more_than_product_cap_not_silently_complete(source):
    source['products']=[product(pid,1) for pid in range(100,121)]
    report=lookup();assert not report['complete'] and report['coverage']['candidate_products']==21
    assert report['coverage']['unverified_products']==1 and len(report['variants'])==20
