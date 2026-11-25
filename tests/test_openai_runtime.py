"""OpenAI Platform (Hermes provider openai-api): synthetic keys only, no network."""
import json,os,subprocess,sys
from pathlib import Path
import pytest
import run_sales
Y=pytest.importorskip('hermes_yaml')
ROOT=Path(__file__).resolve().parents[1]
KEY='sk-proj-synthetic-openai-key-not-valid'
OR_KEY='synthetic-openrouter-key-not-valid'

@pytest.fixture
def config(tmp_path,monkeypatch):
    for k in ('OPENAI_API_KEY','MERLY_OPENAI_MODEL','OPENROUTER_API_KEY','MERLY_OPENROUTER_MODEL','MERLY_SALES_PROVIDER','MERLY_GEMINI_MODEL','GOOGLE_API_KEY','GEMINI_API_KEY','OPENAI_BASE_URL'):monkeypatch.delenv(k,raising=False)
    c=json.loads((ROOT/'hermes-config.template.json').read_text())
    (tmp_path/'config.yaml').write_text(Y.safe_dump(c))
    return tmp_path

def model(config):return Y.safe_load((config/'config.yaml').read_text())['model']

def openai_env(monkeypatch,name='gpt-test-mini'):
    monkeypatch.setenv('MERLY_SALES_PROVIDER','openai');monkeypatch.setenv('OPENAI_API_KEY',KEY);monkeypatch.setenv('MERLY_OPENAI_MODEL',name)

def test_switch_from_managed_openrouter_is_idempotent(config,monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY',OR_KEY);assert run_sales.ensure_sales_model(config)
    openai_env(monkeypatch);monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-unused')
    assert run_sales.ensure_sales_model(config)
    assert model(config)=={'provider':'openai-api','default':'gpt-test-mini','base_url':'https://api.openai.com/v1'}
    assert not run_sales.ensure_sales_model(config)
    raw=(config/'config.yaml').read_text();assert KEY not in raw and OR_KEY not in raw
    assert list(config.glob('config.before-openai-*'))

def test_fresh_volume_and_model_change(config,monkeypatch):
    openai_env(monkeypatch);assert run_sales.ensure_sales_model(config)
    monkeypatch.setenv('MERLY_OPENAI_MODEL','gpt-test-other');assert run_sales.ensure_sales_model(config)
    assert model(config)['default']=='gpt-test-other'

def test_existing_openai_kept_without_explicit_provider(config,monkeypatch):
    openai_env(monkeypatch);run_sales.ensure_sales_model(config)
    monkeypatch.delenv('MERLY_SALES_PROVIDER');monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-unused');monkeypatch.setenv('GEMINI_API_KEY','g'*30)
    assert not run_sales.ensure_sales_model(config)
    assert model(config)['provider']=='openai-api'

@pytest.mark.parametrize('env,error',[({'OPENAI_API_KEY':''},'openai_runtime_key_missing'),({'OPENAI_API_KEY':'sk short'},'openai_key_whitespace'),({'MERLY_OPENAI_MODEL':''},'invalid_openai_model_id'),({'MERLY_OPENAI_MODEL':'gpt\nx'},'invalid_openai_model_id')])
def test_invalid_settings_fail_closed(config,monkeypatch,env,error):
    openai_env(monkeypatch)
    for k,v in env.items():monkeypatch.setenv(k,v)
    before=(config/'config.yaml').read_text()
    with pytest.raises(RuntimeError,match=error):run_sales.ensure_sales_model(config)
    assert (config/'config.yaml').read_text()==before

@pytest.mark.parametrize('previous',[{'provider':'another-owner-provider','default':'keep'},{'provider':'openai-api','default':'x','base_url':'https://proxy.example/v1'},{'provider':'openrouter','default':'x/y','base_url':'https://other.example/v1'}])
def test_unmanaged_provider_requires_review(config,monkeypatch,previous):
    c=Y.safe_load((config/'config.yaml').read_text());c['model']=previous;(config/'config.yaml').write_text(Y.safe_dump(c))
    openai_env(monkeypatch)
    with pytest.raises(RuntimeError,match='existing_model_provider_requires_review'):run_sales.ensure_sales_model(config)
    assert model(config)==previous

def test_can_switch_back_to_openrouter_and_gemini(config,monkeypatch):
    openai_env(monkeypatch);run_sales.ensure_sales_model(config)
    monkeypatch.setenv('MERLY_SALES_PROVIDER','openrouter');monkeypatch.setenv('OPENROUTER_API_KEY',OR_KEY)
    assert run_sales.ensure_sales_model(config) and model(config)['provider']=='openrouter' and model(config)['base_url']=='https://openrouter.ai/api/v1'
    openai_env(monkeypatch);run_sales.ensure_sales_model(config)
    monkeypatch.setenv('MERLY_SALES_PROVIDER','gemini');monkeypatch.setenv('MERLY_GEMINI_MODEL','gemini-offline');monkeypatch.setenv('GEMINI_API_KEY','g'*30)
    assert run_sales.ensure_sales_model(config) and model(config)=={'default':'gemini-offline','provider':'gemini'}

def test_gateway_refuses_openai_key(config,monkeypatch):
    monkeypatch.setenv('PILOT_ROLE','gateway');monkeypatch.setenv('OPENAI_API_KEY',KEY)
    with pytest.raises(RuntimeError,match='gateway_must_not_hold_model_key'):run_sales.main()

def test_compose_passes_openai_only_to_backend():
    for name in ('compose.hermes.json','compose.hermes-learning.json'):
        services=json.loads((ROOT/name).read_text())['services']
        assert services['hermes-sales']['environment']['OPENAI_API_KEY']=='${OPENAI_API_KEY:-}'
        assert services['hermes-sales']['environment']['MERLY_OPENAI_MODEL']=='${MERLY_OPENAI_MODEL:-}'
        assert services['sales-gateway']['environment']['OPENAI_API_KEY']=='${MERLY_GATEWAY_PROVIDER_EMPTY:-}'

def test_pinned_hermes_resolves_openai_platform(config,monkeypatch,tmp_path):
    # Real provider resolution in a clean process; an inherited OPENAI_BASE_URL
    # must not redirect traffic away from api.openai.com.
    openai_env(monkeypatch);run_sales.ensure_sales_model(config)
    script='import json,sys,hermes_yaml\nfrom hermes_cli.runtime_provider import resolve_runtime_with_fallback as r\nc=hermes_yaml.safe_load(open(sys.argv[1]).read())\nrt,_=r(c,requested=c["model"]["provider"],target_model=c["model"]["default"],explicit_base_url=c["model"].get("base_url"))\nprint(json.dumps([rt["provider"],rt["base_url"],rt["api_key"]==sys.argv[2]]))'
    env={'PATH':os.environ['PATH'],'HOME':str(tmp_path),'HERMES_HOME':str(tmp_path/'h'),'OPENAI_API_KEY':KEY,'OPENAI_BASE_URL':'https://attacker.example/v1','PYTHONPATH':str(ROOT)}
    out=subprocess.run([sys.executable,'-c',script,str(config/'config.yaml'),KEY],env=env,capture_output=True,text=True,timeout=60)
    assert out.returncode==0,out.stderr[-500:]
    assert json.loads(out.stdout.strip().splitlines()[-1])==['openai-api','https://api.openai.com/v1',True]
