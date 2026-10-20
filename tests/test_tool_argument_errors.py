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
    assert set(r['stock_requirements']['required'])=={'model_code','size'}

def test_unknown_fields_values_and_names_not_echoed(capsys):
    r,e=server.invoke('search_products',{'private-customer-name':'sensitive-fixture-text'})
    assert e and r['reason']=='unknown_fields'
    output=json.dumps(r)+capsys.readouterr().err
    assert 'sensitive-fixture-text' not in output and 'private-customer-name' not in output

def test_scope_constraints_not_silently_dropped():
    r,e=server.invoke('search_products',{'model_code':'1514','size':38,'check_stock':True,'stock_request_id':'a'*32,'heel_cm':5.0})
    assert e and r['reason']=='verify_specs_before_stock_scope'
