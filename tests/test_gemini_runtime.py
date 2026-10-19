"""Synthetic credentials only; no model/Google API requests."""
import json
from pathlib import Path
import pytest
import run_sales
Y=pytest.importorskip('hermes_yaml')
ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def config(tmp_path,monkeypatch):
    for k in ('GEMINI_API_KEY','GOOGLE_API_KEY','MERLY_GEMINI_MODEL'):monkeypatch.delenv(k,raising=False)
    c=json.loads((ROOT/'hermes-config.template.json').read_text())
    (tmp_path/'config.yaml').write_text(Y.safe_dump(c))
    return tmp_path

def test_no_model_choice_leaves_existing_config(config):
    before=(config/'config.yaml').read_bytes()
    assert run_sales.ensure_gemini_model(config) is False
    assert (config/'config.yaml').read_bytes()==before

def test_gemini_setup_private_backup_idempotent(config,monkeypatch):
    monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-test-offline')
    monkeypatch.setenv('GEMINI_API_KEY','synthetic-gemini-not-a-real-key')
    p=config/'config.yaml';before=Y.safe_load(p.read_text())
    assert run_sales.ensure_gemini_model(config)
    changed=Y.safe_load(p.read_text());assert changed.pop('model')=={'provider':'gemini','default':'gemini-test-offline'}
    assert changed==before and 'synthetic-gemini' not in p.read_text()
    assert len(list(config.glob('config.before-gemini-*.yaml')))==1
    assert p.stat().st_mode&0o777==0o600
    assert run_sales.ensure_gemini_model(config) is False

def test_missing_key_does_not_write(config,monkeypatch):
    monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-test-offline');before=(config/'config.yaml').read_bytes()
    with pytest.raises(RuntimeError,match='gemini_runtime_key_missing'):run_sales.ensure_gemini_model(config)
    assert (config/'config.yaml').read_bytes()==before

def test_conflicting_keys_fail_without_change(config,monkeypatch):
    monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-test-offline')
    monkeypatch.setenv('GEMINI_API_KEY','synthetic-a');monkeypatch.setenv('GOOGLE_API_KEY','synthetic-b')
    with pytest.raises(RuntimeError,match='conflicting_gemini_keys'):run_sales.ensure_gemini_model(config)
    assert 'model' not in Y.safe_load((config/'config.yaml').read_text())

def test_other_provider_not_overwritten(config,monkeypatch):
    c=Y.safe_load((config/'config.yaml').read_text());c['model']={'provider':'another-owner-provider','default':'keep'}
    (config/'config.yaml').write_text(Y.safe_dump(c))
    monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-test-offline');monkeypatch.setenv('GEMINI_API_KEY','synthetic-key')
    with pytest.raises(RuntimeError,match='existing_model_provider_requires_review'):run_sales.ensure_gemini_model(config)
    assert Y.safe_load((config/'config.yaml').read_text())==c

@pytest.mark.parametrize('model',['models/gemini-test','gemini-test\n','other-model'])
def test_invalid_id_not_normalized(config,monkeypatch,model):
    monkeypatch.setenv('MERLY_GEMINI_MODEL',model)
    with pytest.raises(RuntimeError,match='invalid_gemini_model_id'):run_sales.ensure_gemini_model(config)

@pytest.mark.parametrize('key',['GEMINI_API_KEY','GOOGLE_API_KEY'])
def test_gateway_refuses_model_key(monkeypatch,key):
    monkeypatch.setenv('PILOT_ROLE','gateway');monkeypatch.delenv('HARAVAN_ACCESS_TOKEN',raising=False)
    monkeypatch.setenv(key,'synthetic-not-real-key')
    with pytest.raises(RuntimeError,match='gateway_must_not_hold_model_key'):run_sales.main()

@pytest.mark.parametrize('key',['GEMINI_API_KEY','GOOGLE_API_KEY'])
def test_real_compose_keeps_key_in_backend_only(tmp_path,key):
    import os,subprocess
    binary=os.getenv('MERLY_OFFLINE_COMPOSE_BINARY')
    if not binary:pytest.skip('standalone Compose binary required; no daemon')
    c=json.loads((ROOT/'compose.hermes.json').read_text())
    values={'MERLY_SALES_API_KEY':'synthetic-sales-'+('x'*32),'PILOT_ACCESS_KEY':'synthetic-pilot-'+('x'*32),'PILOT_SESSION_SECRET':'synthetic-session-'+('x'*32),key:'synthetic-gemini-key-not-real','MERLY_GEMINI_MODEL':'gemini-test-offline'}
    envfile=tmp_path/'platform.env';envfile.write_text(''.join(k+'='+v+'\n' for k,v in values.items()))
    for service in c['services'].values():
        service['env_file']=[str(envfile)]
        service['environment']={k:(values[k] if v=='' and values.get(k) else v) for k,v in service['environment'].items()}
    path=tmp_path/'compose.json';path.write_text(json.dumps(c))
    env=dict(os.environ)
    for name in [*values,'GEMINI_API_KEY','GOOGLE_API_KEY','MERLY_GATEWAY_PROVIDER_EMPTY']:env.pop(name,None)
    out=subprocess.run([binary,'--project-name','gemini-offline','--env-file',str(envfile),'-f',str(path),'config','--format','json'],env=env,cwd=tmp_path,text=True,capture_output=True,check=True,timeout=20)
    services=json.loads(out.stdout)['services']
    assert services['hermes-sales']['environment'][key]==values[key]
    assert services['hermes-sales']['environment']['MERLY_GEMINI_MODEL']=='gemini-test-offline'
    for k in ('GEMINI_API_KEY','GOOGLE_API_KEY'):assert services['sales-gateway']['environment'][k]==''
