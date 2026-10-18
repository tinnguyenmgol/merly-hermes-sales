import ast,json,shlex,fnmatch
from pathlib import Path
import merly_tools,audit_instance
ROOT=Path(__file__).resolve().parents[1]

def test_exact_tool_contract():
    schemas=json.loads((ROOT/'tool-schema.json').read_text())
    assert {p['post']['operationId'] for p in schemas['paths'].values()}==set(merly_tools.TOOLS)
    config=json.loads((ROOT/'hermes-config.template.json').read_text());audit_instance.check_config(config)
    assert config['tools']['tool_search']['enabled']=='off'
    assert config['skills']['project_discovery'] is False

def test_no_dify_runtime_dependency():
    for name in ['sales_gateway.py','hermes_client.py','mcp_server.py','merly_tools.py']:
        content=(ROOT/name).read_text();ast.parse(content)
        assert 'dify_client' not in content and 'assistant_engine' not in content and 'sales_chat' not in content

def test_build_context_complete():
    patterns=(ROOT/'.dockerignore').read_text().splitlines()
    def allowed(name):
        result=True
        for p in patterns:
            if fnmatch.fnmatchcase(name,p.lstrip('!').rstrip('/')):result=p.startswith('!')
        return result
    for line in (ROOT/'Dockerfile.adapter').read_text().splitlines():
        if line.startswith('COPY '):
            for source in shlex.split(line)[1:-1]:assert (ROOT/source).exists() and allowed(source.rstrip('/')),source
    assert not allowed('.env') and not allowed('sales-audit/inventory.json')

def test_approvals_default_off():
    text=(ROOT/'.env.example').read_text()
    for name in ['HERMES_SALES_ISOLATION_APPROVED','HERMES_CUSTOMER_DATA_APPROVED','HERMES_MODEL_COST_APPROVED']:assert name+'=0' in text

def test_runtime_image_context_complete():
    patterns=(ROOT/'.dockerignore').read_text().splitlines()
    def allowed(name):
        result=True
        for p in patterns:
            if fnmatch.fnmatchcase(name,p.lstrip('!').rstrip('/')):result=p.startswith('!')
        return result
    for line in (ROOT/'Dockerfile.hermes').read_text().splitlines():
        if line.startswith('COPY '):
            for source in shlex.split(line)[1:-1]:assert (ROOT/source).exists() and allowed(source.rstrip('/')),source
    pin=json.loads((ROOT/'HERMES-SOURCE.json').read_text())
    assert pin['commit'] in (ROOT/'Dockerfile.hermes').read_text()
    assert len(pin['archive_sha256'])==64

def test_deployment_new_resources_only():
    services=json.loads((ROOT/'compose.hermes.json').read_text())['services']
    assert 'ports' not in services['hermes-sales']
    assert services['sales-gateway']['environment']['HARAVAN_ACCESS_TOKEN']==''
    for role in services.values():
        assert role['cap_drop']==['ALL'] and role['mem_limit']
        for volume in role['volumes']:assert not any(x in volume for x in ['/opt/data','docker.sock','coolify-db'])
    assert all(port.startswith('127.0.0.1:') for port in services['sales-gateway']['ports'])
