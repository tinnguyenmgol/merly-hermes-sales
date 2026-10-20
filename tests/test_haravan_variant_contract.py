"""Contract cases from Haravan docs, synthetic IDs/stock; no live API calls."""
from types import SimpleNamespace
import io,json,urllib.parse
import pytest
import haravan_variants as v
import merly_tools as t
from test_stock_options import source,lookup

class SourceError(Exception):pass

def reader(count,rows):
    calls=[]
    def get(resource,params):
        calls.append((resource,params))
        if resource.endswith('/count'):return {'count':count}
        start=(params['page']-1)*params['limit']
        return {'variants':rows[start:start+params['limit']]}
    return SimpleNamespace(get=get,HaravanError=SourceError),calls

def variants(n):return [{'id':i+1,'product_id':123} for i in range(n)]

@pytest.mark.parametrize('count',[0,1,50,51,100])
def test_all_pages_match_documented_count(count):
    h,calls=reader(count,variants(count));rows=v.all_variants(h,123)
    assert len(rows)==count
    assert calls[0][0]=='products/123/variants/count'
    assert all(params=={'limit':50,'page':i} for i,(_,params) in enumerate(calls[1:],1))

def test_duplicate_page_or_wrong_parent_rejected():
    for rows in ([{'id':1,'product_id':123}]*2,[{'id':1,'product_id':999}]):
        h,_=reader(len(rows),rows)
        with pytest.raises(SourceError,match='variant_identity_mismatch'):v.all_variants(h,123)

def test_count_mismatch_not_silently_complete():
    h,_=reader(51,variants(50))
    with pytest.raises(SourceError,match='variant_count_changed_or_incomplete'):v.all_variants(h,123)

def test_deadline_checked_before_request():
    h,calls=reader(1,variants(1))
    with pytest.raises(SourceError,match='budget_exceeded'):v.all_variants(h,123,deadline=0)
    assert not calls

def test_size_uses_option_metadata_not_first_number():
    p={'options':[{'name':'Màu sắc','position':1},{'name':'Size','position':2}]}
    row={'option1':'38','option2':'39','title':'38 / 39'}
    assert t.catalog.size(row)=='38' # reproduces old heuristic error
    assert t.variant_size(p,row)=='39'
    assert t.variant_color(p,row)=='38'

def test_size_color_positions_may_be_reversed():
    p={'options':[{'name':'Kích thước','position':1},{'name':'Colour','position':3}]}
    row={'option1':'38','option2':'Leather','option3':'Chì','title':'38 / Leather / Chì'}
    assert t.variant_size(p,row)=='38' and t.variant_color(p,row)=='Chì'

def test_missing_size_metadata_does_not_guess_from_color():
    p={'options':[{'name':'Màu','position':1}]};row={'option1':'38'}
    assert t.variant_size(p,row) is None

def test_documented_255_character_option_not_rejected(source):
    source['products'][0]['variants'][0]['option1']='A'*255
    r=lookup()
    import stock_report
    validated=stock_report.validate(r,'a'*32,{'model_code':'1514','size':38})
    assert validated['variants'][0]['color']=='A'*255

@pytest.mark.parametrize('resource',['products/123/variants','products/123/variants/count','variants/456'])
def test_documented_read_endpoints_still_fixed_host_get(monkeypatch,resource):
    monkeypatch.setenv('HARAVAN_ACCESS_TOKEN','synthetic-not-real')
    class Opener:
        def open(self,req,timeout):
            assert req.method=='GET'
            assert req.full_url.split('?')[0]=='https://apis.haravan.com/com/'+resource+'.json'
            return io.BytesIO(b'{}')
    monkeypatch.setattr(t.h.urllib.request,'build_opener',lambda *a:Opener())
    assert t.h.get(resource,{})=={}

@pytest.mark.parametrize('resource',['orders','draft_orders','products/123/variants/../../orders','variants/1?evil=1','https://evil.invalid/products'])
def test_no_new_write_order_or_arbitrary_route(resource):
    with pytest.raises(t.h.HaravanError,match='resource_not_allowed'):t.h.get(resource,{})

def test_full_documented_http_contract_keeps_two_colors_after_twelfth(monkeypatch):
    """Real Haravan client/reader/validator; SYNTHETIC HTTP, no live requests."""
    import copy
    from test_stock_options import product
    import stock_report
    p=product();p['variants'][14]['option1']='Chì'
    all_rows=copy.deepcopy(p['variants']);active={all_rows[13]['id'],all_rows[14]['id']}
    monkeypatch.setenv('HARAVAN_ACCESS_TOKEN','synthetic-transport-only')
    monkeypatch.setattr(t.catalog,'snapshot',lambda:[copy.deepcopy(p)])
    monkeypatch.setattr(t.catalog,'status',lambda:{'ready':True,'age_seconds':1})
    requests=[]
    class Opener:
        def open(self,req,timeout):
            assert req.method=='GET';u=urllib.parse.urlsplit(req.full_url)
            assert u.netloc=='apis.haravan.com';requests.append(u.path)
            if u.path=='/com/products/100.json':
                small=copy.deepcopy(p);small['variants']=small['variants'][:1];payload={'product':small}
            elif u.path=='/com/products/100/variants/count.json':payload={'count':20}
            elif u.path=='/com/products/100/variants.json':payload={'variants':all_rows}
            elif u.path=='/com/inventory_locations.json':
                q=urllib.parse.parse_qs(u.query);ids=list(map(int,q['variant_ids'][0].split(',')))
                payload={'inventory_locations':[{'variant_id':vid,'loc_id':loc,'product_id':100,'qty_onhand':99,'qty_available':1 if vid in active and i==0 else 0} for vid in ids for i,loc in enumerate(t.LOCATIONS)]}
            else:raise AssertionError('unexpected endpoint')
            return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.setattr(t.h.urllib.request,'build_opener',lambda *a:Opener())
    r=lookup();clean=stock_report.validate(r,'a'*32,{'model_code':'1514','size':38})
    assert clean['complete'] and len(clean['variants'])==20 and len(requests)==5
    assert {v['color'] for v in clean['variants'] if v['available']}=={'Kem','Chì'}
    assert all(v['known_available'] in (0,1) for v in clean['variants'])

def test_ambiguous_option_positions_not_assigned():
    p={'options':[{'name':'Size','position':1},{'name':'Màu','position':1}]}
    assert t.variant_size(p,{'option1':'38'}) is None
    assert t.variant_color(p,{'option1':'38'}) is None

def test_unknown_size_is_partial_not_no_matching_variant(source):
    source['products'][0]['options']=[{'name':'Màu','position':1}]
    r=lookup()
    assert not r['complete'] and r['coverage']['unclassified_variants']==20

def test_missing_or_nonarray_option_metadata_not_crash():
    for value in (None,{},'Size'):
        assert t.variant_size({'options':value},{'option1':'38'}) is None

@pytest.mark.parametrize('size_name,color_name',[('Kích Cỡ','Màu giày'),('Size Giày','Màu sắc giày')])
def test_explicit_vietnamese_option_names(size_name,color_name):
    p={'options':[{'name':size_name,'position':1},{'name':color_name,'position':2}]}
    row={'option1':'38','option2':'Chì'}
    assert t.variant_size(p,row)=='38' and t.variant_color(p,row)=='Chì'
