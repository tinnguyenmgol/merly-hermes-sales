"""No model/Haravan calls; describe schemas/types, never customer values."""
import json
import mcp_server as server

def test_wrong_size_type_has_repair_details(capsys):
    data={'model_code':'1514','size':'38','check_stock':True,'stock_request_id':'a'*32}
    result,error=server.invoke('search_products',data)
    assert error and result['reason']=='invalid_size'
    assert result['received_field_types']['size']=='str'
    assert result['input_schema']['properties']['size']['type']=='integer'
    assert result['do_not_infer_no_stock'] and data['size']=='38'
    logged=capsys.readouterr().err
    assert 'invalid_size' in logged and '1514' not in logged and 'a'*32 not in logged

def test_missing_stock_scope_is_explicit():
    r,e=server.invoke('search_products',{'model_code':'1514','check_stock':True})
    assert e and r['reason']=='stock_scope_required'
    assert set(r['stock_requirements']['required'])=={'size'}

def test_unknown_fields_values_and_names_not_echoed(capsys):
    r,e=server.invoke('search_products',{'private-customer-name':'sensitive-fixture-text'})
    assert e and r['reason']=='unknown_fields'
    output=json.dumps(r)+capsys.readouterr().err
    assert 'sensitive-fixture-text' not in output and 'private-customer-name' not in output

def test_scope_constraints_not_silently_dropped(monkeypatch):
    import product_discovery
    seen=[]
    monkeypatch.setattr(product_discovery,'lookup',lambda data,tools:seen.append(data) or {'status':'synthetic'})
    r,e=server.invoke('search_products',{'model_code':'1514','size':38,'check_stock':True,'stock_request_id':'a'*32,'heel_cm':5.0})
    assert not e and seen[0]['heel_cm']==5 and seen[0]['model_code']=='1514'

def test_schema_number_accepts_integer_without_coercing(monkeypatch):
    import product_discovery
    seen=[]
    monkeypatch.setattr(product_discovery,'lookup',lambda data,tools:seen.append(data.copy()) or {'status':'synthetic'})
    args={'size':42,'heel_cm':3,'check_stock':True}
    result,error=server.invoke('search_products',args)
    assert not error and seen[0]==args and type(seen[0]['heel_cm']) is int


def test_bad_number_types_are_not_repaired(monkeypatch):
    import product_discovery
    monkeypatch.setattr(product_discovery,'lookup',lambda *a:(_ for _ in ()).throw(AssertionError('must reject')))
    for value in ('3',True,float('nan'),float('inf'),-1,16):
        result,error=server.invoke('search_products',{'size':42,'heel_cm':value,'check_stock':True})
        assert error and result['reason']=='invalid_heel_cm'


def test_huge_integer_fails_as_argument_error_not_tool_unavailable():
    result,error=server.invoke('quote_variant',{'product_id':10**500,'variant_id':100001})
    assert error and result['status']=='invalid_arguments' and result['reason']=='invalid_product_id'
