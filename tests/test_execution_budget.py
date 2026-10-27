"""Managed runtime policy, not customer-phrase routing. All files are synthetic."""
import copy,json
from pathlib import Path
import pytest
import run_sales as r
Y=pytest.importorskip('hermes_yaml')
ROOT=Path(__file__).resolve().parents[1]


def setup(home,turns=4,seconds=40):
    c=json.loads((ROOT/'hermes-config.template.json').read_text())
    c['agent'].update(max_turns=turns,run_budget_seconds=seconds)
    c['model']={'provider':'custom','default':'MODEL_UNCHANGED','temperature':.2}
    p=home/'config.yaml';p.write_text(Y.safe_dump(c));return p,c

@pytest.mark.parametrize('turns',[1,4,6,8,16,500,'unlimited',None])
def test_sync_only_owned_budget_fields_and_preserve_model(tmp_path,turns):
    p,c=setup(tmp_path,turns,100);before=p.read_bytes()
    assert r.ensure_sales_execution_budget(tmp_path)
    expected=copy.deepcopy(c);expected['agent'].update(max_turns=8,run_budget_seconds=40)
    assert Y.safe_load(p.read_text())==expected
    backups=list(tmp_path.glob('config.before-sales-execution-budget-*'))
    assert len(backups)==1 and backups[0].read_bytes()==before
    assert p.stat().st_mode&0o777==0o600 and backups[0].stat().st_mode&0o777==0o600
    assert not r.ensure_sales_execution_budget(tmp_path)
    assert len(list(tmp_path.glob('config.before-sales-execution-budget-*')))==1


def test_new_volume_no_write_or_backup(tmp_path):
    p,c=setup(tmp_path,8,40);before=p.read_bytes()
    assert r.sales_execution_budget()=={'max_turns':8,'run_budget_seconds':40}
    assert not r.ensure_sales_execution_budget(tmp_path)
    assert p.read_bytes()==before and not list(tmp_path.glob('config.before-*'))


def test_budget_does_not_follow_other_profile_symlink(tmp_path):
    other=tmp_path/'other.yaml';other.write_text('UNTOUCHED');(tmp_path/'config.yaml').symlink_to(other)
    with pytest.raises(RuntimeError,match='symlink'):r.ensure_sales_execution_budget(tmp_path)
    assert other.read_text()=='UNTOUCHED'


def test_inline_model_key_is_not_copied_into_new_backup(tmp_path):
    p,c=setup(tmp_path);c['model']['api_key']='SYNTHETIC_INLINE_SECRET';p.write_text(Y.safe_dump(c));before=p.read_bytes()
    with pytest.raises(RuntimeError,match='inline_key'):r.ensure_sales_execution_budget(tmp_path)
    assert p.read_bytes()==before and not list(tmp_path.glob('config.before-*'))

@pytest.mark.parametrize('field,value',[('max_turns',0),('max_turns',17),('max_turns',True),('max_turns','8'),('run_budget_seconds',0),('run_budget_seconds',45),('run_budget_seconds',100),('run_budget_seconds',True),('run_budget_seconds','40'),('run_budget_seconds',float('inf'))])
def test_invalid_or_unbounded_source_policy_never_rewrites_volume(tmp_path,monkeypatch,field,value):
    home=tmp_path/'sales';home.mkdir();p,c=setup(home);before=p.read_bytes()
    source=tmp_path/'source';source.mkdir();template=json.loads((ROOT/'hermes-config.template.json').read_text());template['agent'][field]=value
    (source/'hermes-config.template.json').write_text(json.dumps(template));monkeypatch.setattr(r,'ROOT',source)
    with pytest.raises(RuntimeError,match='invalid_sales_'):r.ensure_sales_execution_budget(home)
    assert p.read_bytes()==before and not list(home.glob('config.before-*'))

@pytest.mark.parametrize('original',[
 'CUSTOM_PREFIX\r\nTối đa ba vòng công cụ/lượt. Nguồn lỗi không tự lặp vô hạn.\r\nCUSTOM_SUFFIX',
 'CUSTOM_PREFIX\r\nCUSTOM_SUFFIX',
 'CUSTOM_PREFIX\n<!-- MERLY_EXECUTION_POLICY_BEGIN -->old block<!-- MERLY_EXECUTION_POLICY_END -->\nCUSTOM_SUFFIX'])
def test_prompt_migration_preserves_custom_text_and_removes_stale_soft_cap(tmp_path,original):
    p=tmp_path/'SOUL.md';p.write_bytes(original.encode())
    assert r.ensure_sales_execution_prompt(tmp_path)
    updated=p.read_text()
    assert updated.startswith('CUSTOM_PREFIX') and 'CUSTOM_SUFFIX' in updated
    assert updated.count('<!-- MERLY_EXECUTION_POLICY_BEGIN -->')==1
    assert 'Tối đa ba vòng công cụ/lượt.' not in updated
    assert not r.ensure_sales_execution_prompt(tmp_path)
    assert p.stat().st_mode&0o777==0o600 and not list(tmp_path.glob('.merly-execution-*'))


def test_current_source_prompt_needs_no_rewrite(tmp_path):
    p=tmp_path/'SOUL.md';original=(ROOT/'SYSTEM-PROMPT.md').read_bytes();p.write_bytes(original)
    assert not r.ensure_sales_execution_prompt(tmp_path) and p.read_bytes()==original

@pytest.mark.parametrize('content',[
 '<!-- MERLY_EXECUTION_POLICY_BEGIN -->missing end',
 '<!-- MERLY_EXECUTION_POLICY_END --><!-- MERLY_EXECUTION_POLICY_BEGIN -->',
 '<!-- MERLY_EXECUTION_POLICY_BEGIN --><!-- MERLY_EXECUTION_POLICY_BEGIN --><!-- MERLY_EXECUTION_POLICY_END -->',
 'Tối đa ba vòng công cụ/lượt. Tối đa ba vòng công cụ/lượt. '])
def test_ambiguous_prompt_does_not_get_silently_rewritten(tmp_path,content):
    p=tmp_path/'SOUL.md';p.write_text(content);before=p.read_bytes()
    with pytest.raises(RuntimeError):r.ensure_sales_execution_prompt(tmp_path)
    assert p.read_bytes()==before


def test_prompt_does_not_follow_other_profile_symlink(tmp_path):
    other=tmp_path/'other.md';other.write_text('UNTOUCHED');(tmp_path/'SOUL.md').symlink_to(other)
    with pytest.raises(RuntimeError,match='symlink'):r.ensure_sales_execution_prompt(tmp_path)
    assert other.read_text()=='UNTOUCHED'


def test_entrypoint_migrates_existing_volume_before_launch(tmp_path,monkeypatch,capsys):
    import signal,types,stock_probe
    home=tmp_path/'dedicated-sales';home.mkdir();p,c=setup(home)
    (home/'SOUL.md').write_text('CUSTOM\nTối đa ba vòng công cụ/lượt. Nguồn lỗi không tự lặp vô hạn.')
    for key,value in {'PILOT_ROLE':'hermes','HERMES_HOME':str(home),'API_SERVER_KEY':'S'*40,'HERMES_SALES_API_BASE':'http://fixture.invalid/v1'}.items():monkeypatch.setenv(key,value)
    monkeypatch.setattr(r,'ensure_sales_model',lambda _:False)
    monkeypatch.setattr(r.subprocess,'run',lambda *a,**kw:types.SimpleNamespace(returncode=0))
    monkeypatch.setattr(r.threading.Thread,'start',lambda _:None)
    monkeypatch.setattr(signal,'signal',lambda *a:None)
    monkeypatch.setattr(stock_probe,'start',lambda:None)
    launched=[]
    def launch(args,**kwargs):
        active=Y.safe_load(p.read_text())
        assert active['agent']['max_turns']==8 and active['agent']['run_budget_seconds']==40
        assert active['model']==c['model']
        assert 'Tối đa ba vòng công cụ/lượt.' not in (home/'SOUL.md').read_text()
        launched.append(args)
        return types.SimpleNamespace(wait=lambda:0,send_signal=lambda _:None)
    monkeypatch.setattr(r.subprocess,'Popen',launch)
    with pytest.raises(SystemExit) as result:r.main()
    assert result.value.code==0 and len(launched)==1
    log=json.loads(capsys.readouterr().out)
    assert log=={'status':'sales_execution_policy_ready','max_turns':8,'run_budget_seconds':40,'config_migrated':True,'prompt_migrated':True}
