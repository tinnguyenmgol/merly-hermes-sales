"""All upstreams are synthetic; no real stock or account access asserted."""
import copy,json
import pytest
import merly_tools as tools
P={'id':100,'title':'1676 Hồng Pearl','handle':'fixture-1676','published_at':'fixture','options':[{'name':'Màu','position':1},{'name':'Size','position':2}],'image':{'src':'https://product.hstatic.net/test.jpg'},'variants':[{'id':101,'sku':'SPTEST','option1':'Hồng Pearl','option2':'42','title':'Hồng Pearl / 42','price':'350000'}]}
@pytest.fixture
def products(monkeypatch):
    monkeypatch.setattr(tools.catalog,'snapshot',lambda:[copy.deepcopy(P)])
    monkeypatch.setattr(tools.h,'get',lambda *a:{'product':copy.deepcopy(P)})
    monkeypatch.setattr(tools.h,'inventory',lambda *a:[{'loc_id':loc,'qty_available':2} for loc in tools.LOCATIONS])
    monkeypatch.setattr(tools,'enrichment',lambda:{})

def test_search_not_stock(products):
    r=tools.dispatch('search_products',{'size':42,'color':'Hồng Pearl'})
    p=r['products'][0]
    assert p['variants'][0]['variant_id']==101
    assert p['availability']=='not_checked' and 'price' not in p
    assert p['product_url']=='https://merlyshoes.com/products/fixture-1676'
    assert p['image_url']=='https://product.hstatic.net/test.jpg'

def test_missing_spec_not_silently_ignored(products):
    r=tools.dispatch('search_products',{'size':42,'heel_cm':5})
    assert r['status']=='partial_metadata' and r['products']==[]
    assert r['unknown_spec_products']==1

def test_verified_spec_filter(products,monkeypatch):
    monkeypatch.setattr(tools,'enrichment',lambda:{'100':{'heel_cm':5,'category':'sandal','private_note':'DO NOT EXPOSE'}})
    r=tools.dispatch('search_products',{'heel_cm':5,'category':'sandal'})
    assert r['products'] and 'private_note' not in r['products'][0]['verified_specs']
    assert tools.dispatch('search_products',{'heel_cm':10})['products']==[]

def test_quote_current_prices(products):
    r=tools.dispatch('quote_variant',{'product_id':100,'variant_id':101,'quantity':2})
    assert r['available'] and r['price_vnd']==350000 and r['subtotal_vnd']==700000
    assert r['inventory_complete'] and r['known_available']==6
    assert r['reserved'] is False and r['discounts_applied'] is False

def test_partial_inventory_not_zero(products,monkeypatch):
    monkeypatch.setattr(tools.h,'inventory',lambda *a:[])
    r=tools.dispatch('quote_variant',{'product_id':100,'variant_id':101})
    assert r['available'] is None and r['status']=='partial_inventory'

def test_ids_not_substituted(products):
    assert tools.dispatch('quote_variant',{'product_id':100,'variant_id':999})['status']=='variant_mismatch'

def test_size43_owner_source():
    r=tools.dispatch('size_guide',{'length_cm':26.5})
    assert r['chart'][0]['size']==43 and r['chart'][0]['circumference_cm']==24.6
    assert not r['fit_confirmed']
    assert tools.dispatch('size_guide',{'length_cm':24.2})['status']=='needs_staff_review'

def test_unapproved_sources_not_invented():
    assert tools.dispatch('get_policy',{'topic':'store_hours'})['status']=='approved'
    assert tools.dispatch('get_promotions',{})['status']=='publication_not_configured'

@pytest.mark.parametrize('name,data',[
 ('shell',{}),('search_products',{'url':'https://evil.invalid'}),
 ('search_products',{'size':True}),('search_products',{'heel_cm':'5cm'}),
 ('quote_variant',{'product_id':100}),('quote_variant',{'product_id':1,'variant_id':2,'quantity':21}),
 ('get_policy',{'topic':'internal_payroll'}),('size_guide',{'size':44})])
def test_arguments_fail_closed(name,data):
    with pytest.raises(tools.Invalid):tools.dispatch(name,data)
