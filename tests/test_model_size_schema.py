"""Model-visible schema checks, not inference quality claims."""
import asyncio,copy,json
import pytest
import mcp_server,audit_instance
from tools.mcp_tool_schema import _convert_mcp_schema
from tool_payload import describe


def visible():
    rows=asyncio.run(mcp_server.list_tools(None,None)).tools
    return [{'type':'function','function':_convert_mcp_schema('merly',row)} for row in rows]


def test_size_required_survives_real_pinned_hermes_schema_conversion():
    defs=visible();audit_instance.check_model_definitions(defs)
    search=next(d['function'] for d in defs if d['function']['name']=='mcp__merly__search_products')
    assert search['parameters']['required']==['size','heel_mode']
    assert search['parameters']['properties']['size']['type']=='integer'

@pytest.mark.parametrize('change',['optional','missing_property','wrong_type','wrong_min','wrong_max'])
def test_startup_refuses_wrong_actual_model_schema(change):
    defs=visible();schema=next(d['function']['parameters'] for d in defs if d['function']['name']=='mcp__merly__search_products')
    if change=='optional':schema.pop('required')
    elif change=='missing_property':schema['properties'].pop('size')
    elif change=='wrong_type':schema['properties']['size']['type']='string'
    elif change=='wrong_min':schema['properties']['size']['minimum']=1
    else:schema['properties']['size']['maximum']=99
    with pytest.raises(ValueError,match='model_size'):audit_instance.check_model_definitions(defs)

@pytest.mark.parametrize('args,state',[
 ({},'missing'),({'query':'PRIVATE_CUSTOMER_SENTINEL'},'missing'),
 ({'size':42},'valid_integer'),({'size':'42'},'invalid_type_or_range'),
 ({'size':True},'invalid_type_or_range'),({'size':None},'invalid_type_or_range'),
 ({'size':99},'invalid_type_or_range')])
def test_argument_shape_diagnostics_never_log_values(args,state):
    value={'status':'needs_clarification'}
    r=describe(value,'mcp__merly__search_products',json.dumps(args))
    assert r['size_argument']==state
    assert r['argument_fields']==[k for k in ('query','size') if k in args]
    assert 'PRIVATE_CUSTOMER_SENTINEL' not in json.dumps(r)
    assert '42' not in json.dumps(r)


def test_decoder_diagnostic_contains_reason_not_payload():
    r=describe('PRIVATE_SECRET_SENTINEL not-json','mcp__merly__search_products','not-json')
    assert r['decode_reason']=='invalid_json' and r['size_argument']=='unreadable_arguments'
    assert 'PRIVATE_SECRET_SENTINEL' not in json.dumps(r)


def test_required_schema_does_not_invent_a_size_for_invalid_legacy_call(monkeypatch):
    monkeypatch.setattr(mcp_server.merly_tools,'dispatch',lambda *a:pytest.fail('no source access'))
    result,error=mcp_server.invoke('search_products',{'color':'Đen'})
    assert not error and result['missing_fields']==['size'] and not result['source_read_attempted']
