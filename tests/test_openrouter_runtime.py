"""Synthetic keys only: config, migrations, isolation, real Compose interpolation."""
import copy,json,os,subprocess
from pathlib import Path
import pytest
import run_sales
Y=pytest.importorskip('hermes_yaml')
ROOT=Path(__file__).resolve().parents[1]
KEY='synthetic-openrouter-key-not-valid'
@pytest.fixture
def config(tmp_path,monkeypatch):
    for k in ('OPENROUTER_API_KEY','MERLY_OPENROUTER_MODEL','MERLY_SALES_PROVIDER','MERLY_GEMINI_MODEL','GOOGLE_API_KEY','GEMINI_API_KEY'):monkeypatch.delenv(k,raising=False)
    c=json.loads((ROOT/'hermes-config.template.json').read_text())
    c['model']={'provider':'gemini','default':'gemini-offline-test'}
    (tmp_path/'config.yaml').write_text(Y.safe_dump(c))
    return tmp_path

def test_key_only_switches_existing_gemini_and_is_idempotent(config,monkeypatch):
    p=config/'config.yaml';before=Y.safe_load(p.read_text());monkeypatch.setenv('OPENROUTER_API_KEY',KEY)
    monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-stale-setting');monkeypatch.setenv('GEMINI_API_KEY','synthetic-stale-google-key')
    assert run_sales.ensure_sales_model(config)
    c=Y.safe_load(p.read_text());assert c.pop('model')=={'provider':'openrouter','default':'deepseek/deepseek-v4.1-flash-1017','base_url':'https://openrouter.ai/api/v1','api_mode':'chat_completions'}
    before.pop('model');assert c==before
    assert p.stat().st_mode&0o777==0o600
    backups=list(config.glob('config.before-openrouter-*'));assert len(backups)==1
    assert all(KEY not in f.read_text() for f in [p,*backups])
    assert not run_sales.ensure_sales_model(config)
    assert len(list(config.glob('config.before-openrouter-*')))==1

def test_without_key_no_implicit_switch(config):
    p=config/'config.yaml';before=p.read_bytes()
    assert not run_sales.ensure_sales_model(config);assert p.read_bytes()==before

def test_explicit_openrouter_missing_key_fails_closed(config,monkeypatch):
    monkeypatch.setenv('MERLY_SALES_PROVIDER','openrouter');before=(config/'config.yaml').read_bytes()
    with pytest.raises(RuntimeError,match='openrouter_runtime_key_missing'):run_sales.ensure_sales_model(config)
    assert (config/'config.yaml').read_bytes()==before

@pytest.mark.parametrize('model',['bad model','openai/gpt\n','/gpt','openai/gpt?key=x','https://evil.invalid/x'])
def test_invalid_model_is_not_repaired(config,monkeypatch,model):
    monkeypatch.setenv('OPENROUTER_API_KEY',KEY);monkeypatch.setenv('MERLY_OPENROUTER_MODEL',model)
    with pytest.raises(RuntimeError,match='invalid_openrouter_model_id'):run_sales.ensure_sales_model(config)

@pytest.mark.parametrize('key',['short',KEY+'\n',' '+KEY])
def test_invalid_key_not_written_or_logged(config,monkeypatch,key):
    monkeypatch.setenv('OPENROUTER_API_KEY',key)
    with pytest.raises(RuntimeError) as exc:run_sales.ensure_sales_model(config)
    assert key not in str(exc.value) and KEY not in (config/'config.yaml').read_text()

def test_gateway_refuses_openrouter_key(config,monkeypatch):
    monkeypatch.setenv('PILOT_ROLE','gateway');monkeypatch.setenv('OPENROUTER_API_KEY',KEY)
    monkeypatch.delenv('HARAVAN_ACCESS_TOKEN',raising=False)
    with pytest.raises(RuntimeError,match='gateway_must_not_hold_model_key'):run_sales.main()

def test_unrelated_provider_and_inline_secret_require_review(config,monkeypatch):
    p=config/'config.yaml';c=Y.safe_load(p.read_text());c['model']={'provider':'owner-custom','default':'keep'};p.write_text(Y.safe_dump(c))
    monkeypatch.setenv('OPENROUTER_API_KEY',KEY)
    with pytest.raises(RuntimeError,match='existing_model_provider_requires_review'):run_sales.ensure_sales_model(config)
    assert Y.safe_load(p.read_text())==c
    c['model']={'provider':'gemini','api_key':'synthetic-inline-secret'};p.write_text(Y.safe_dump(c))
    with pytest.raises(RuntimeError,match='model_inline_key_requires_review'):run_sales.ensure_sales_model(config)
    assert not list(config.glob('config.before-openrouter-*'))

def test_real_compose_coolify_envfile_isolation(config):
    binary=os.getenv('MERLY_OFFLINE_COMPOSE_BINARY')
    if not binary:pytest.skip('standalone Compose binary required, no daemon')
    c=json.loads((ROOT/'compose.hermes.json').read_text())
    values={'MERLY_SALES_API_KEY':'synthetic-sales-'+'x'*32,'PILOT_ACCESS_KEY':'synthetic-pilot-'+'x'*32,'PILOT_SESSION_SECRET':'synthetic-session-'+'x'*32,'OPENROUTER_API_KEY':KEY,'GEMINI_API_KEY':'synthetic-google-stale'}
    envfile=config/'platform.env';envfile.write_text(''.join(k+'='+v+'\n' for k,v in values.items()))
    for service in c['services'].values():service['env_file']=[str(envfile)]
    p=config/'compose.json';p.write_text(json.dumps(c));env=dict(os.environ)
    for k in [*values,'MERLY_GATEWAY_PROVIDER_EMPTY','MERLY_OPENROUTER_MODEL']:env.pop(k,None)
    out=subprocess.run([binary,'--project-name','openrouter-offline','--env-file',str(envfile),'-f',str(p),'config','--format','json'],cwd=config,env=env,text=True,capture_output=True,check=True,timeout=20)
    services=json.loads(out.stdout)['services'];backend=services['hermes-sales']['environment'];gateway=services['sales-gateway']['environment']
    assert backend['OPENROUTER_API_KEY']==KEY and backend['MERLY_OPENROUTER_MODEL']=='deepseek/deepseek-v4.1-flash-1017'
    assert all(gateway[k]=='' for k in ('OPENROUTER_API_KEY','GOOGLE_API_KEY','GEMINI_API_KEY'))

def test_explicit_gemini_choice_not_overridden(config,monkeypatch):
    monkeypatch.setenv('MERLY_SALES_PROVIDER','gemini');monkeypatch.setenv('OPENROUTER_API_KEY',KEY)
    assert not run_sales.ensure_sales_model(config)
    assert Y.safe_load((config/'config.yaml').read_text())['model']['provider']=='gemini'

def test_removing_key_does_not_silently_revert_to_gemini(config,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY',KEY);assert run_sales.ensure_sales_model(config)
    monkeypatch.delenv('OPENROUTER_API_KEY');monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-stale')
    with pytest.raises(RuntimeError,match='openrouter_runtime_key_missing'):run_sales.ensure_sales_model(config)
    assert Y.safe_load((config/'config.yaml').read_text())['model']['provider']=='openrouter'

@pytest.mark.parametrize('selected',['deepseek/deepseek-v4.1-flash-1017','openai/gpt-oss-20b'])
def test_explicit_model_override_remains_exact(config,monkeypatch,selected):
    monkeypatch.setenv('OPENROUTER_API_KEY',KEY)
    monkeypatch.setenv('MERLY_OPENROUTER_MODEL',selected)
    assert run_sales.ensure_sales_model(config)
    assert Y.safe_load((config/'config.yaml').read_text())['model']['default']==selected

def test_existing_openrouter_volume_switches_default_once(config,monkeypatch):
    p=config/'config.yaml';data=Y.safe_load(p.read_text())
    data['model']={'provider':'openrouter','default':'openai/gpt-oss-20b','base_url':'https://openrouter.ai/api/v1','api_mode':'chat_completions'}
    p.write_text(Y.safe_dump(data));monkeypatch.setenv('OPENROUTER_API_KEY',KEY)
    assert run_sales.ensure_sales_model(config)
    after=Y.safe_load(p.read_text())
    assert after['model']['default']=='deepseek/deepseek-v4.1-flash-1017'
    assert {k:v for k,v in after.items() if k!='model'}=={k:v for k,v in data.items() if k!='model'}
    assert not run_sales.ensure_sales_model(config)
