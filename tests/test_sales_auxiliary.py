import json
from pathlib import Path
import pytest
import run_sales
Y=pytest.importorskip('hermes_yaml')

def test_existing_volume_title_disable_private_idempotent(tmp_path):
    c=json.loads(Path('hermes-config.template.json').read_text())
    c['auxiliary']={'title_generation':{'enabled':True,'language':'vi'},'other':{'provider':'preserve'}}
    p=tmp_path/'config.yaml';p.write_text(Y.safe_dump(c))
    assert run_sales.ensure_sales_auxiliary(tmp_path)
    changed=Y.safe_load(p.read_text());c['auxiliary']['title_generation']['enabled']=False
    assert changed==c and p.stat().st_mode&0o777==0o600
    assert not run_sales.ensure_sales_auxiliary(tmp_path)
    assert len(list(tmp_path.glob('config.before-sales-auxiliary-*')))==1

def test_template_disables_native_auto_title(monkeypatch):
    from agent import title_generator as title
    config=json.loads(Path('hermes-config.template.json').read_text())
    monkeypatch.setattr(title,'_title_config',lambda:config['auxiliary']['title_generation'])
    assert not title._auto_title_enabled()
