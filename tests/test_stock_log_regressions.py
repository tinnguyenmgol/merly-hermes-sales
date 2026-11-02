"""Synthetic transports reproduce log failure classes, not production data."""
import time,json
import pytest
import mcp_server,stock_report,turn_contract as t,state
from product_measurements import search_scope
from test_stock_options import source
from test_height_evidence_contract import heels,presented
from test_client import approved
from agent_answer import present

@pytest.mark.parametrize('token,expected',[('7',7),('0',0),('5.5',5.5),('14.25',14.25),('15.0',15)])
def test_choice_mapped_to_canonical_scope(token,expected):
    assert search_scope({'size':42,'heel_selection':token})=={'size':42,'heel_cm':expected}

def test_unspecified_not_coerced_to_flat_or_previous():
    assert search_scope({'size':42,'heel_selection':'unspecified'})=={'size':42}

@pytest.mark.parametrize('bad',[None,7,'7cm','7,5',' 7','7 ','NaN','16','-1','7e0',''])
def test_bad_literal_no_source(monkeypatch,bad):
    monkeypatch.setattr(mcp_server.merly_tools.catalog,'snapshot',lambda:pytest.fail('source read'))
    result,error=mcp_server.invoke('search_products',{'size':42,'heel_selection':bad})
    assert error and result['status']=='invalid_arguments'

@pytest.mark.parametrize('legacy',[{'heel_cm':7},{'heel_mode':'exact'}])
def test_choices_cannot_silently_override(legacy):
    with pytest.raises(ValueError,match='conflicting_heel_selection'):search_scope({'heel_selection':'7',**legacy})

def test_new_scope_real_tool_output_extraction(heels):
    out=presented({'size':42,'heel_selection':'7'},'Các mẫu gót 7cm đã tra.')
    assert out['answer_mode']=='native' and out['stock_options']['criteria']['heel_cm']==7
    assert not out['_guard_reasons']

@pytest.mark.parametrize('bad',['7cm','16'])
def test_invalid_choice_cannot_crash_trace_extraction(heels,bad):
    args={'size':42,'heel_selection':bad};result,error=mcp_server.invoke('search_products',args);assert error
    items=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'bad','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'bad','output':json.dumps(result)}]
    r,requested=stock_report.extract(items,None,time.time())
    assert requested and r['mode']=='unverified'

@pytest.mark.parametrize('positive',[True,False])
def test_partial_source_no_second_inference_or_charge(heels,approved,monkeypatch,positive):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1')
    if positive:monkeypatch.setattr(mcp_server.merly_tools.catalog,'status',lambda:{'ready':True,'age_seconds':301})
    else:monkeypatch.setattr(mcp_server.merly_tools.h,'inventory',lambda *a:[])
    a=presented({'size':42,'heel_selection':'7'},'Chỉ có mẫu này còn hàng.')
    assert a['_guard_reasons'] and a['stock_options']['complete'] is False
    monkeypatch.setattr(state,'reserve_checked',lambda *a:pytest.fail('no repair budget charge'))
    out=t.recover(a,{'instructions':'original'},'user',time.time(),time.monotonic()+50,lambda *a:pytest.fail('no second inference'),present)
    assert out['_repair_attempts']==0 and out['_repair_skipped_reason']=='source_evidence_incomplete'
    assert out['answer_mode']=='evidence_guard'

def test_argument_error_remains_correctable():
    a={'_guard_reasons':['rejected_tool_evidence','unverified_inventory'],'stock_options':{'mode':'unverified','reason_code':'tool_invalid_arguments'}}
    assert not t.source_evidence_incomplete(a)


def test_partial_metadata_checks_canonical_selection_scope(heels):
    from test_stock_options import product
    p=product(999,1);p['title']='Mẫu chưa có thông số chiều cao';p['variants'][0].update(option1='Đen',option2='42')
    heels['products'].append(p)
    out=presented({'size':42,'heel_selection':'7'},'Các mẫu gót 7cm đã tra.')
    assert out['stock_options']['mode']=='discovery'
    assert 'heel_cm' in out['stock_options']['unverified_criteria']
    assert out['stock_options']['criteria']['heel_cm']==7
    assert out['stock_options']['coverage']['unknown_spec_products']==1


def test_metadata_shape_not_measurement_values():
    from tool_payload import describe
    r=describe({'status':'invalid_arguments'},'mcp__merly__search_products',{'size':42,'heel_selection':'PRIVATE_TOKEN_SENTINEL'})
    assert r['heel_argument']=='invalid' and 'heel_selection' in r['argument_fields']
    assert 'PRIVATE_TOKEN_SENTINEL' not in json.dumps(r)


def test_pinned_auxiliary_rejects_paid_fallback_before_credentials(monkeypatch):
    from agent import auxiliary_client as aux
    monkeypatch.setattr(aux,'_aux_openrouter_settings',lambda:(True,'vendor/paid-model-fixture'))
    monkeypatch.setattr(aux,'_select_pool_entry',lambda *a:pytest.fail('must block before credential lookup'))
    assert aux._try_openrouter()==(None,None)


def test_startup_audit_survives_adapter_path_removal(tmp_path):
    import subprocess,sys
    from pathlib import Path
    from test_model_size_schema import visible
    root=Path.cwd();p=tmp_path/'definitions.json';p.write_text(json.dumps(visible()))
    code='''import audit_instance,sys,json,os
from pathlib import Path
root=Path.cwd().resolve()
definitions=json.loads(Path(sys.argv[1]).read_text())
sys.path[:]=[p for p in sys.path if Path(p or os.getcwd()).resolve()!=root]
sys.modules.pop('product_measurements',None)
sys.modules.pop('catalog_query',None)
audit_instance.check_model_definitions(definitions)
print('isolated_startup_schema_verified')
'''
    r=subprocess.run([sys.executable,'-c',code,str(p)],cwd=root,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert 'isolated_startup_schema_verified' in r.stdout

