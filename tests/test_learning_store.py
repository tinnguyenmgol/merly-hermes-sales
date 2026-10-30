"""Metadata workflow and retention; no real customer data or model calls."""
import sys,json,sqlite3
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'learning-service'))
from learning_store import Store,ReviewError,TTL
from learning_contract import validate,InvalidEvent,capture

def event(diag='0123456789abcdef'):
    return {'diagnostic_id':diag,'outcome':'guarded','reason_codes':['unsupported_stock_claim'],'criterion_fields':['size'],'tools':['mcp__merly__quote_variant'],'tool_statuses':['ok']}

@pytest.fixture
def store(tmp_path):return Store(tmp_path/'private')

def test_full_review_cycle_export_and_revocation(store):
    cid=store.ingest(event())['case_id'];draft=store.propose(cid)
    assert draft['recipe_id']=='money_roles' and draft['proposal_is_hypothesis']
    with pytest.raises(ReviewError,match='approval_required'):store.export(draft['lesson_id'])
    with pytest.raises(ReviewError,match='owner_confirmation_required'):store.review(draft['lesson_id'],'approve')
    lid=draft['lesson_id'];store.review(lid,'approve',True);packet=store.export(lid)
    assert packet['synthetic_only'] and packet['deployment_authorized'] is False
    assert packet['verification_status']=='pending_offline_and_live_tests'
    assert len(packet['cases'])==2 and all(len(c['messages'])<=5 for c in packet['cases'])
    assert '0123456789abcdef' not in json.dumps(packet)
    path=Path(store.export_file(lid));assert path.is_file() and path.stat().st_mode&0o777==0o600
    with pytest.raises(FileExistsError):store.export_file(lid)
    store.review(lid,'revoke',True);assert not path.exists()
    with pytest.raises(ReviewError):store.export(lid)
    with store.db() as db:assert [r[0] for r in db.execute('SELECT action FROM audit')]==['approve','revoke']

def test_expiration_removes_cases_lessons_audit_and_local_exports(tmp_path):
    now=[1700000000.0];store=Store(tmp_path/'private',clock=lambda:now[0])
    cid=store.ingest(event())['case_id'];lid=store.propose(cid)['lesson_id'];store.review(lid,'approve',True)
    path=Path(store.export_file(lid));now[0]+=TTL
    assert store.purge()==1 and not path.exists()
    assert store.list_cases()==[]
    with pytest.raises(ReviewError,match='not_found'):store.lesson(lid)
    with store.db() as db:
        assert db.execute('SELECT count(*) FROM lessons').fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM audit').fetchone()[0]==0
        assert db.execute('PRAGMA journal_mode').fetchone()[0]=='delete'
        assert db.execute('PRAGMA secure_delete').fetchone()[0]==1
    assert b'0123456789abcdef' not in store.path.read_bytes()

def test_duplicate_does_not_extend_retention_or_overwrite_evidence(tmp_path):
    now=[1700000000.0];store=Store(tmp_path/'private',clock=lambda:now[0]);first=store.ingest(event());expiry=store.case(first['case_id'])['expires_at']
    now[0]+=100;assert store.ingest(event())=={'case_id':first['case_id'],'created':False}
    assert store.case(first['case_id'])['expires_at']==expiry
    changed=event();changed['criterion_fields']=['heel_cm']
    with pytest.raises(ReviewError,match='diagnostic_conflict'):store.ingest(changed)
    assert store.case(first['case_id'])['event']['criterion_fields']==['size']

def test_cases_stay_separate_and_drafts_cannot_be_swapped(store):
    a=store.ingest(event())['case_id'];b=store.ingest(event('fedcba9876543210'))['case_id']
    la=store.propose(a,'constraint_preservation');lb=store.propose(b,'source_metadata')
    assert a!=b and la['lesson_id']!=lb['lesson_id']
    store.review(la['lesson_id'],'approve',True)
    with pytest.raises(ReviewError,match='approval_required'):store.export(lb['lesson_id'])
    assert store.propose(a)['lesson_id']==la['lesson_id']

@pytest.mark.parametrize('key',['message','reply','transcript','customer_id','phone','email','address','token','Authorization','source_links','instructions','approve','command'])
def test_raw_data_and_control_fields_never_enter_database(store,key):
    data=event();data[key]='PRIVATE_RAW_SENTINEL'
    with pytest.raises(InvalidEvent):store.ingest(data)
    assert store.list_cases()==[] and b'PRIVATE_RAW_SENTINEL' not in store.path.read_bytes()

@pytest.mark.parametrize('key',['reason_codes','criterion_fields','tools','tool_statuses'])
def test_arbitrary_values_in_metadata_are_rejected(store,key):
    data=event();data[key]=['PRIVATE_SECRET_SENTINEL']
    with pytest.raises(InvalidEvent):store.ingest(data)
    assert b'PRIVATE_SECRET_SENTINEL' not in store.path.read_bytes()

def test_capacity_is_bounded_and_owner_confirmation_is_strict(tmp_path):
    store=Store(tmp_path/'private',capacity=1);cid=store.ingest(event())['case_id']
    with pytest.raises(ReviewError,match='capacity'):store.ingest(event('fedcba9876543210'))
    lid=store.propose(cid)['lesson_id']
    with pytest.raises(ReviewError):store.review(lid,'approve',1)
    store.review(lid,'reject',True)
    with pytest.raises(ReviewError,match='invalid_transition'):store.review(lid,'approve',True)

def test_state_and_export_permissions_and_no_symlink_escape(tmp_path):
    store=Store(tmp_path/'private')
    assert store.directory.stat().st_mode&0o777==0o700
    assert store.path.stat().st_mode&0o777==0o600
    bad=tmp_path/'linked';bad.symlink_to(store.directory,target_is_directory=True)
    with pytest.raises(ReviewError):Store(bad)
    cid=store.ingest(event())['case_id'];lid=store.propose(cid)['lesson_id'];store.review(lid,'approve',True)
    victim=tmp_path/'victim';victim.write_text('UNCHANGED');(store.exports/(lid+'.json')).symlink_to(victim)
    with pytest.raises(FileExistsError):store.export_file(lid)
    assert victim.read_text()=='UNCHANGED'

@pytest.mark.parametrize('bad',[' '+('a'*32),'../file','A'*32,'a'*31])
def test_identifiers_are_not_normalized(store,bad):
    with pytest.raises(ReviewError):store.case(bad)

def test_capture_drops_everything_except_fixed_metadata():
    marker='PRIVATE_RAW_SENTINEL'
    result=capture('0123456789abcdef',{'reply':marker,'customer_id':marker,'answer_mode':'evidence_guard'}, {'guard_reasons':['unsupported_stock_claim',marker],'tools_used':['mcp__merly__quote_variant',marker],'lookup_diagnostics':[{'criteria_fields':['heel_cm',marker]}],'tool_diagnostics':[{'source_status':'ok','argument_fields':['size',marker],'raw':marker}]})
    assert marker not in json.dumps(result) and result['criterion_fields']==['heel_cm','size']
    assert capture('0123456789abcdef',{'answer_mode':'native','lookup_incomplete':True}) is None
    failed=capture('0123456789abcdef',{},failure=marker)
    assert failed['reason_codes']==['other_failure'] and marker not in json.dumps(failed)


def test_on_demand_analysis_is_idempotent_and_owner_can_revise_only_draft(store):
    cid=store.ingest(event())['case_id']
    first=store.analyze();assert first['drafts_created']==1 and first['model_calls']==0
    assert store.analyze()['drafts_created']==0
    lid=first['proposals'][0]['lesson_id']
    revised=store.propose(cid,'constraint_preservation')
    assert revised['lesson_id']==lid and revised['recipe_id']=='constraint_preservation'
    store.review(lid,'approve',True)
    with pytest.raises(ReviewError,match='invalid_transition'):store.propose(cid,'policy_review')


def test_approved_content_is_frozen_across_recipe_code_changes(store,monkeypatch):
    import recipes
    cid=store.ingest(event())['case_id'];lid=store.propose(cid,'money_roles')['lesson_id']
    reviewed=store.lesson(lid)['instruction_candidate'];store.review(lid,'approve',True)
    monkeypatch.setitem(recipes.RECIPES['money_roles'],'lesson','UNREVIEWED_CHANGED_LESSON')
    assert store.lesson(lid)['instruction_candidate']==reviewed
    assert store.export(lid)['instruction_candidate']==reviewed


def test_reviewed_known_fix_runs_actual_schema_regression_and_countercase(store):
    import copy,audit_instance
    from test_model_size_schema import visible
    cid=store.ingest(event())['case_id'];lid=store.propose(cid,'tool_schema_completeness')['lesson_id']
    store.review(lid,'approve',True);packet=store.export(lid)
    assert packet['recipe_id']=='tool_schema_completeness' and len(packet['cases'])==2
    # Existing fixed code is exercised, not an invented pass observation.
    definitions=visible();audit_instance.check_model_definitions(definitions)
    broken=copy.deepcopy(definitions)
    search=next(d['function'] for d in broken if d['function']['name']=='mcp__merly__search_products')
    search['parameters'].pop('required')
    with pytest.raises(ValueError,match='model_size_must_be_required'):audit_instance.check_model_definitions(broken)
    # This offline demonstration is NOT a production deployment or live pass.
    assert packet['verification_status']=='pending_offline_and_live_tests' and packet['deployment_authorized'] is False


def test_staff_mark_preserves_existing_automatic_evidence(store):
    cid=store.ingest(event())['case_id']
    mark=store.mark('0123456789abcdef')
    assert mark['case_id']==cid and mark['existing_evidence_preserved']
    assert store.case(cid)['event']==event()
