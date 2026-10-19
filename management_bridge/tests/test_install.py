import importlib.util,json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('diagnostics_installer',ROOT/'install.py');installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

def test_preserves_servers_and_channels():
    source={'model':{'default':'unchanged'},'mcp_servers':{'workspace':{'url':'https://example.invalid'}},'platform_toolsets':{'telegram':['file','workspace'],'api_server':['workspace']}}
    changed=installer.merge(source,'/python','/safe/server.py')
    assert changed['model']==source['model']
    assert changed['mcp_servers']['workspace']==source['mcp_servers']['workspace']
    assert changed['platform_toolsets']['telegram']==['file','workspace',installer.NAME]
    assert changed['platform_toolsets']['api_server']==source['platform_toolsets']['api_server']
    assert installer.NAME not in source['mcp_servers']

def test_auto_mcp_selection_not_narrowed():
    source={'mcp_servers':{'workspace':{}},'platform_toolsets':{'telegram':['file']}}
    assert installer.merge(source,'/p','/s')['platform_toolsets']['telegram']==['file']

def test_explicit_denial_not_overridden():
    with pytest.raises(ValueError):installer.merge({'platform_toolsets':{'telegram':['no_mcp']}},'/p','/s')

def test_atomic_install_backup(tmp_path):
    original={'model':{'default':'KEEP'},'mcp_servers':{'workspace':{'url':'https://example.invalid'}}}
    (tmp_path/'config.yaml').write_text(json.dumps(original))
    result=installer.install(tmp_path,'/python',json.loads,json.dumps,lambda n:(ROOT/n).read_bytes())
    assert result['status']=='INSTALLED'
    current=json.loads((tmp_path/'config.yaml').read_text());assert current['model']==original['model']
    assert json.loads(next((tmp_path/'config-backups/coolify-diagnostics').glob('*')).read_text())==original
    assert (tmp_path/'integrations/coolify-diagnostics/server.py').exists()
    assert (tmp_path/'integrations/coolify-diagnostics/server.py').stat().st_mode&0o777==0o644
    assert (tmp_path/'integrations/coolify-diagnostics/reader.py').stat().st_mode&0o777==0o644
    assert (tmp_path/'integrations/coolify-diagnostics').stat().st_mode&0o777==0o711
    assert (tmp_path/'config.yaml').stat().st_mode&0o777==0o600

def test_bad_download_no_config_write(tmp_path):
    p=tmp_path/'config.yaml';p.write_text('{}')
    with pytest.raises(ValueError):installer.install(tmp_path,'/python',json.loads,json.dumps,lambda n:b'bad')
    assert p.read_text()=='{}'
