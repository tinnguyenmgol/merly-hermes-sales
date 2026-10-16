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
    for name in ['gateway.py','hermes_client.py','mcp_server.py','merly_tools.py']:
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
