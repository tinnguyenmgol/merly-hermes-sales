"""Pinned SDK/protocol, synthetic data, no paid inference."""
import asyncio,copy,json,time
from pathlib import Path
import pytest
import mcp_server,tool_payload,turn_contract,dialogue,run_sales,state
from agent.tool_guardrails import ToolCallGuardrailConfig as Config,ToolCallGuardrailController as Controller,classify_tool_failure
from agent.display import _detect_tool_failure
from tools.mcp_tool_handlers import _render_call_tool_result,_result_is_error
from agent.tool_dispatch_helpers import _maybe_wrap_untrusted
from test_client import approved
NAME='mcp__merly__search_products'

def policy():return json.loads(Path('hermes-config.template.json').read_text())['agent']['tool_loop_guardrails']
def feedback(args):
    import mcp.types as t
    r=asyncio.run(mcp_server.call_tool(None,t.CallToolRequestParams(name='search_products',arguments=args)))
    assert r.is_error is False and not r.content
    raw=_render_call_tool_result(r,'merly');assert _result_is_error(raw) is False
    wrapped=_maybe_wrap_untrusted(NAME,raw)
    assert classify_tool_failure(NAME,wrapped)[0] and _detect_tool_failure(NAME,wrapped)[0]
    assert tool_payload.unpack(wrapped,NAME)['reason']=='missing_required_fields'
    return wrapped

def test_api_warn_only_default_is_explicitly_overridden_for_sales():
    assert Config.from_mapping({},platform='api_server').hard_stop_enabled is False
    assert Config.from_mapping(policy(),platform='api_server').hard_stop_enabled is True

def test_varied_invalid_calls_stop_per_turn_without_breaking_transport():
    guard=Controller(Config.from_mapping(policy(),platform='api_server'))
    for i in range(3):
        args={'query':'style '+str(i),'color':'Đen','heel_selection':'unspecified'}
        assert guard.before_call(NAME,args).allows_execution
        result=feedback(args);decision=guard.after_call(NAME,args,result)
        guard.observe_call(NAME,args,result,failed=True)
        if i<2:assert not decision.should_halt
    assert decision.should_halt and decision.code=='same_tool_failure_halt'
    assert Controller(Config.from_mapping(policy(),platform='api_server')).halt_decision is None
    guard.reset_for_turn();assert guard.halt_decision is None

def test_success_between_errors_does_not_halt_normal_progress():
    guard=Controller(Config.from_mapping(policy(),platform='api_server'))
    for _ in range(3):
        args={'color':'Đen','heel_selection':'unspecified'}
        assert not guard.after_call(NAME,args,feedback(args)).should_halt
        assert not guard.after_call(NAME,{'size':42},'{"result":{"status":"ok"}}',failed=False).should_halt

def test_exhausted_arguments_do_not_start_second_run(approved,monkeypatch):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1')
    d={'tool':NAME,'source_status':'invalid_arguments','has_stock_report':False}
    a={'reply':'internal','_guard_reasons':['rejected_tool_evidence'],'_tool_diagnostics':[d,d],'_tools_used':[NAME]}
    monkeypatch.setattr(state,'reserve_checked',lambda *a:pytest.fail('no second reservation'))
    out=turn_contract.recover(a,{'instructions':'original'},'user',time.time(),time.monotonic()+50,lambda *a:pytest.fail('no second API'),None)
    assert out['_repair_attempts']==0 and out['_repair_skipped_reason']=='repeated_argument_failures'
    assert out['lookup_incomplete'] and out['answer_mode']=='evidence_guard'

@pytest.mark.parametrize('change',[{'needs_clarification':True},{'_guard_reasons':[]},{'_tool_diagnostics':[{'tool':NAME,'source_status':'invalid_arguments','has_stock_report':False}]},{'_tool_diagnostics':[{'tool':NAME,'source_status':'invalid_arguments','has_stock_report':True}]*2}])
def test_stop_does_not_hide_question_single_error_or_source(change):
    a={'_guard_reasons':['rejected_tool_evidence'],'_tool_diagnostics':[{'tool':NAME,'source_status':'invalid_arguments','has_stock_report':False}]*2,**change}
    assert not turn_contract.repeated_argument_failures(a)

def test_migrate_only_sales_loop_settings_idempotently(tmp_path):
    import hermes_yaml as y
    c=json.loads(Path('hermes-config.template.json').read_text());c['model']={'provider':'custom','default':'UNCHANGED'}
    c['agent'].pop('stall_guards');c['agent']['tool_loop_guardrails']={'hard_stop_enabled':False,'loop_caps':{'max_web_searches':7},'warn_after':{'operator_setting':4}}
    p=tmp_path/'config.yaml';p.write_text(y.safe_dump(c));before=p.read_bytes()
    assert run_sales.ensure_sales_loop_guardrails(tmp_path)
    after=y.safe_load(p.read_text())
    assert after['model']==c['model'] and after['agent']['max_turns']==8
    assert after['agent']['tool_loop_guardrails']['loop_caps']=={'max_web_searches':7}
    assert after['agent']['tool_loop_guardrails']['warn_after']['operator_setting']==4
    assert after['agent']['tool_loop_guardrails']['hard_stop_enabled'] is True
    assert p.stat().st_mode&0o777==0o600
    assert not run_sales.ensure_sales_loop_guardrails(tmp_path)
    backups=list(tmp_path.glob('config.before-sales-loop-guardrails-*'))
    assert len(backups)==1 and backups[0].read_bytes()==before

def test_migration_never_follows_symlink(tmp_path):
    target=tmp_path/'other';target.write_text('UNCHANGED');(tmp_path/'config.yaml').symlink_to(target)
    with pytest.raises(RuntimeError,match='symlink'):run_sales.ensure_sales_loop_guardrails(tmp_path)
    assert target.read_text()=='UNCHANGED'

def displayed(size=42):
    return {'reply':'shown','stock_options':{'mode':'all_options','model_code':'fixture','size':size,'variants':[{'product_id':1,'variant_id':2,'known_available':1,'size':str(size)}]}}

def test_reference_is_session_local_not_a_current_choice(approved):
    dialogue.record('one','synthetic first turn',displayed())
    text=dialogue.size_reference_context('one')
    assert '"last_displayed_variant_size": 42' in text
    assert '"current_selection_confirmed": false' in text and '"current_stock_confirmed": false' in text
    assert not dialogue.size_reference_context('two')
    dialogue.record('one','new turn',{'reply':'no verified cards yet'})
    assert dialogue.size_reference_context('one')==text
    dialogue.record('one','new size',displayed(40))
    assert '"last_displayed_variant_size": 40' in dialogue.size_reference_context('one')

def test_reference_expires_and_does_not_parse_customer_text(approved,monkeypatch):
    dialogue.record('one','I choose size 42',{'reply':'no cards'})
    assert not dialogue.size_reference_context('one')
    dialogue.record('one','synthetic',displayed())
    now=dialogue.time.time();monkeypatch.setattr(dialogue.time,'time',lambda:now+dialogue.TTL+1)
    assert not dialogue.size_reference_context('one')


def test_ambiguous_unknown_or_catalog_only_sizes_are_not_promoted():
    a=displayed();a['quotes']=[{'product_id':3,'variant_id':4,'known_available':1,'size':'40'}]
    assert dialogue._size_reference(a) is None
    a['quotes'][0]['size']=None
    assert dialogue._size_reference(a) is None
    assert dialogue._size_reference({'reply':'catalog','products':[{'size':'42'}]}) is None


def test_new_user_size_is_not_overridden_and_private_reference_not_logged(approved,monkeypatch):
    import hermes_client as client
    dialogue.record('reference-client','first turn',displayed())
    monkeypatch.setattr(client,'audit',lambda:True);seen=[]
    from test_client import responses
    monkeypatch.setattr(client,'request',lambda path,p:seen.append(copy.deepcopy(p)) or responses())
    out=client.chat('Giờ chuyển sang size 40.','merly-sales:web:reference-client')
    assert seen[0]['input']=='Giờ chuyển sang size 40.'
    assert '"last_displayed_variant_size": 42' in seen[0]['instructions']
    assert 'Latest changes override old references' in seen[0]['instructions']
    assert len(seen[0]['conversation_history'])==2 and out['_history_messages']==2
    assert out['_size_reference_attached'] is True


def test_migration_refuses_inline_model_key_without_copying_it(tmp_path):
    import hermes_yaml as y
    c=json.loads(Path('hermes-config.template.json').read_text());c['model']={'api_key':'SYNTHETIC_INLINE_MARKER'}
    p=tmp_path/'config.yaml';p.write_text(y.safe_dump(c));before=p.read_bytes()
    with pytest.raises(RuntimeError,match='inline_key'):run_sales.ensure_sales_loop_guardrails(tmp_path)
    assert p.read_bytes()==before and not list(tmp_path.glob('config.before-*'))
