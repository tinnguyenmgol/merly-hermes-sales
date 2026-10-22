"""Actual tools/validators, synthetic Haravan data. No live stock/model claims."""
import copy,time,json
from datetime import datetime,timezone
from types import SimpleNamespace
import pytest
import merly_tools as t,stock_report as s,media_urls as media,catalog_query as q,collection_catalog as groups
from test_stock_options import source,product,api_response
IMG='https://product.hstatic.net/1000000000/product/fixture.jpg'
@pytest.fixture
def named(source,monkeypatch):
    p=source['products'][0];p.update(title='Merly Sandal quai mảnh - cao gót 10cm GN-041',product_type='Sandal cao gót',image={'src':IMG})
    for v in p['variants']:v.update(option1='Đen',option2='42')
    monkeypatch.setattr(t,'enrichment',lambda:{})
    return source

def checked(args):
    start=time.time();raw=t.dispatch('search_products',dict(args,check_stock=True))['stock_report']
    return s.validate(raw,None,dict(args,check_stock=True),start)

@pytest.mark.parametrize('query',['sandal quai mảnh','Merly quai','cao gót','GN-041'])
def test_source_name_type_retrieval_retains_size_color_height(named,query):
    args={'query':query,'category':'cao gót','size':42,'color':'đen','heel_cm':10}
    report=checked(args)
    assert report['complete'] and report['criteria']==args
    assert len(report['variants'])==20 and all(r['available'] for r in report['variants'])
    assert report['products'][0]['product_type']=='Sandal cao gót'
    assert all(r['image_url']==IMG and r['image_scope']=='product' for r in report['variants'])

@pytest.mark.parametrize('extra',[{'query':'quai bự'},{'heel_cm':7},{'color':'Kem'},{'size':40}])
def test_no_criteria_silently_relaxed(named,extra):
    r=checked({'query':'sandal','size':42,'color':'đen','heel_cm':10,**extra})
    assert not any(v['available'] for v in r['variants'])
    assert all(r['criteria'][k]==v for k,v in extra.items())

def test_type_without_manual_enrichment(named):
    rows=t.search_products({'category':'Sandal','size':42})['products']
    assert rows and rows[0]['product_type']=='Sandal cao gót'
    assert rows[0]['match_evidence']['category']['field']=='product_type'
    assert rows[0]['availability']=='not_checked'

def test_keyword_boundary_and_no_sku_repair():
    assert not q.phrase('Giày robot','bốt') and not q.name_matches({'title':'A','product_type':None},'none')
    assert not q.phrase('Giày không phải cao gót','cao gót')
    p={'title':'Giày GN-041','variants':[]}
    assert t.matches_model(p,'GN-041') and not t.matches_model(p,'GN_041')

@pytest.mark.parametrize('title,ptype,expected',[
 ('Giày cao gót Merly - 10cm','Sandal',10),('Mẫu quai mảnh - 7cm','Giày cao gót',7),
 ('Giày cao gót tầm 10cm','Sandal',None),('Mẫu 10cm chân 26cm','Khác',None),
 ('Giày cao gót SKU 5CM','Khác',None),('Giày cao gót 5cm hoặc 7cm','Khác',None)])
def test_explicit_source_height(title,ptype,expected):
    assert t.verified_product_specs({'title':title,'product_type':ptype},{}).get('heel_cm')==expected

def test_cached_variant_absence_cannot_hide_fresh_size(named,monkeypatch):
    fresh=copy.deepcopy(named['products'][0]);named['products'][0]['variants']=copy.deepcopy(fresh['variants'][:1]);named['products'][0]['variants'][0]['option2']='35'
    monkeypatch.setattr(t.h,'get',lambda resource,params:api_response(fresh,resource,params))
    r=checked({'query':'sandal','size':42,'color':'đen','heel_cm':10})
    assert len(r['variants'])==20 and r['complete'] and named['calls']

def test_changed_fresh_name_type_not_matching(named,monkeypatch):
    get=t.h.get
    def changed(resource,params):
        data=get(resource,params)
        if resource=='products/100':data['product'].update(title='Giày búp bê GN-041',product_type='Búp bê')
        return data
    monkeypatch.setattr(t.h,'get',changed)
    r=checked({'query':'quai mảnh','category':'Sandal','size':42})
    assert not r['variants'] and not named['calls']

@pytest.mark.parametrize('value',[None,'javascript:alert(1)','data:image/png;base64,AAAA','https://evil.invalid/a.jpg','http://product.hstatic.net/a.jpg','https://product.hstatic.net.evil.invalid/a.jpg','https://u:p@product.hstatic.net/a.jpg','https://product.hstatic.net/a.svg','https://product.hstatic.net:444/a.jpg','https://product.hstatic.net/a.jpg#x','https://product.hstatic.net/a\n.jpg'])
def test_unsafe_images_inert(value):assert media.safe_image(value) is None

def test_picture_maps_variant_and_labels_product_fallback(named):
    p=named['products'][0];v=p['variants'][0];v['image_id']=22
    variant_url=IMG.replace('fixture.jpg','variant.webp')
    p['images']=[{'id':22,'src':variant_url,'variant_ids':[v['id']]}]
    assert media.picture(p,v)=={'image_url':variant_url,'image_scope':'variant'}
    assert media.picture(p,p['variants'][1])=={'image_url':IMG,'image_scope':'product'}
    r=checked({'query':'sandal','size':42,'color':'đen'})
    assert r['variants'][0]['image_url']==variant_url and r['variants'][0]['image_scope']=='variant'

def test_bad_optional_image_does_not_erase_valid_stock(named):
    raw=t.dispatch('search_products',{'query':'sandal','size':42,'check_stock':True})['stock_report']
    raw['variants'][0]['image_url']='https://evil.invalid/fake.jpg'
    out=s.validate(raw,None,{'query':'sandal','size':42,'check_stock':True},time.time()-1)
    assert out['complete'] and out['variants'][0]['image_url'] is None

@pytest.fixture
def group_source(named,monkeypatch):
    groups.clear();calls=[]
    names={'custom_collections':[{'id':11,'title':'Giày đi tiệc','handle':'giay-di-tiec','published_at':'2026-01-01T00:00:00Z'}], 'smart_collections':[{'id':22,'title':'Sandal cao gót','handle':'sandal-cao-got','published_at':'2026-01-01T00:00:00Z'}]}
    get=t.h.get
    def api(resource,params,timeout=12):
        calls.append((resource,dict(params),timeout))
        if resource in names:return {resource:copy.deepcopy(names[resource])}
        if resource=='products':
            assert params['collection_id'] in (11,22)
            return {'products':copy.deepcopy(named['products']) if params['page']==1 else []}
        return get(resource,params)
    monkeypatch.setattr(t.h,'get',api)
    yield {'calls':calls,'names':names,'api':api,'data':named}
    groups.clear()

@pytest.mark.parametrize('query,id',[('Giày đi tiệc',11),('sandal-cao-got',22)])
def test_custom_smart_membership_comes_from_api(group_source,query,id):
    r=checked({'collection':query,'query':'quai mảnh','category':'Sandal','size':42,'color':'đen','heel_cm':10})
    assert r['complete'] and len(r['variants'])==20
    assert r['collection_evidence']['id']==id and r['collection_evidence']['product_ids']==[100]
    req=[c for c in group_source['calls'] if c[0]=='products']
    assert req and all(c[1]['collection_id']==id and 0<c[2]<=3 for c in req)
    assert all(v['available'] for v in r['variants'])

def test_ambiguous_group_not_auto_selected(group_source):
    group_source['names']['smart_collections'].append({'id':33,'title':'Giày đi tiệc mới','handle':'giay-di-tiec-moi','published_at':'2026-01-01T00:00:00Z'})
    r=checked({'collection':'đi tiệc','size':42})
    assert r['collection_status']=='ambiguous' and len(r['collection_choices'])==2
    assert not r['variants'] and not r['complete']
    assert not any(c[0]=='products' for c in group_source['calls'])

def test_group_error_never_drops_filter(group_source,monkeypatch):
    def fail(resource,params,timeout=12):raise t.h.HaravanError('haravan_http_403')
    monkeypatch.setattr(t.h,'get',fail)
    r=checked({'collection':'đi tiệc','size':42})
    assert r['collection_status']=='source_unavailable' and not r['variants']
    assert r['operation_status']=='metadata_missing' and not group_source['data']['calls']

def test_unpublished_group_not_no_stock(group_source):
    group_source['names']['custom_collections'][0]['published']=False
    r=checked({'collection':'Giày đi tiệc','size':42})
    assert r['collection_status']=='not_found' and not r['complete']
    assert 'nhóm sản phẩm' in s.summary(r)

def test_collection_name_not_inferred_heel(group_source):
    group_source['names']['custom_collections'][0].update(title='Giày cao gót 10cm')
    p=group_source['data']['products'][0];p['title']='Merly GN-041';p['product_type']='Cao gót'
    r=checked({'collection':'Giày cao gót 10cm','heel_cm':10,'size':42})
    assert r['collection_status']=='resolved' and not r['variants']
    assert 'chiều cao gót' in s.summary(r) and not group_source['data']['calls']

def test_forged_collection_members_rejected(group_source):
    args={'collection':'Giày đi tiệc','size':42,'check_stock':True};raw=t.dispatch('search_products',args)['stock_report']
    raw['collection_evidence']['product_ids']=[999]
    with pytest.raises(s.InvalidReport,match='invalid_collection_membership'):s.validate(raw,None,args,time.time()-1)

def test_collection_paging_rejects_duplicates():
    calls=[]
    def get(resource,params,timeout=12):
        calls.append(params['page']);return {resource:[{'id':i+1} for i in range(50)]}
    h=SimpleNamespace(get=get,HaravanError=RuntimeError)
    with pytest.raises(RuntimeError,match='invalid_collection_identity'):groups._pages(h,'custom_collections','custom_collections',time.monotonic()+10,{},3)
    assert calls==[1,2]

@pytest.mark.parametrize('resource',['custom_collections','smart_collections'])
def test_new_resources_fixed_host_get(resource,monkeypatch):
    import io
    monkeypatch.setenv('HARAVAN_ACCESS_TOKEN','synthetic-transport-only')
    class Opener:
        def open(self,request,timeout):
            assert request.method=='GET' and request.full_url.startswith('https://apis.haravan.com/com/'+resource+'.json?')
            assert timeout<=3
            return io.BytesIO(b'{}')
    monkeypatch.setattr(t.h.urllib.request,'build_opener',lambda *a:Opener())
    assert t.h.get(resource,{},timeout=2)=={}

def test_conflicting_variant_image_mapping_not_claimed_correct(named):
    p=named['products'][0];v=p['variants'][0];v['image_id']=22
    p['images']=[{'id':22,'src':IMG.replace('fixture','other'),'variant_ids':[999999]}]
    assert media.picture(p,v)['image_scope']=='product'

def test_available_types_come_from_source_not_a_dictionary(named):
    r=t.search_products({'query':'không có từ khóa này'})
    assert r['available_product_types']==['Sandal cao gót'] and not r['product_types_truncated']

def test_no_strap_does_not_negate_explicit_heel():
    assert t.verified_product_specs({'title':'Giày cao gót không quai - 10cm'},{}).get('heel_cm')==10
    assert 'heel_cm' not in t.verified_product_specs({'title':'Không cao gót 10cm'}, {})

def test_history_omits_visual_urls_but_keeps_product_references(configured):
    import dialogue
    dialogue.record('picture-history','xem mẫu',{'reply':'Tên đã hiển thị','products':[{'product_id':100,'title':'Tên thật từ nguồn','image_url':IMG,'image_scope':'product'}]})
    history=dialogue.history('picture-history')[1]['content']
    assert 'Tên thật từ nguồn' in history and '100' in history
    assert 'image_url' not in history and IMG not in history

from test_gateway import configured
