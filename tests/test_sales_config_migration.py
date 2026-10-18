"""Existing-volume migration; private temp files only, never real credentials."""
import json
from pathlib import Path
import pytest
import run_sales
ROOT=Path(__file__).resolve().parents[1]
yaml=pytest.importorskip('hermes_yaml')

def original_config():
    c=json.loads((ROOT/'hermes-config.template.json').read_text())
    c['mcp_servers']['merly'].pop('env',None)
    c['model']={'provider':'unchanged-provider','default':'unchanged-model'}
    return c

def test_existing_volume_migrates_only_child_environment(tmp_path):
    c=original_config();p=tmp_path/'config.yaml';p.write_text(yaml.safe_dump(c))
    before=p.read_bytes();assert run_sales.ensure_merly_child_env(tmp_path) is True
    new=yaml.safe_load(p.read_text());env=new['mcp_servers']['merly'].pop('env')
    assert new==c
    assert env=={'HARAVAN_ACCESS_TOKEN':'${HARAVAN_ACCESS_TOKEN}','CATALOG_CACHE_PATH':'${CATALOG_CACHE_PATH}'}
    backup=list(tmp_path.glob('config.before-merly-env-*.yaml'));assert len(backup)==1 and backup[0].read_bytes()==before
    assert p.stat().st_mode&0o777==0o600 and backup[0].stat().st_mode&0o777==0o600
    assert run_sales.ensure_merly_child_env(tmp_path) is False
    assert len(list(tmp_path.glob('config.before-merly-env-*.yaml')))==1

def test_conflicting_literal_secret_not_silently_overwritten(tmp_path):
    c=original_config();c['mcp_servers']['merly']['env']={'HARAVAN_ACCESS_TOKEN':'synthetic-not-real'}
    p=tmp_path/'config.yaml';p.write_text(yaml.safe_dump(c));before=p.read_bytes()
    with pytest.raises(RuntimeError,match='conflicting_merly_child_environment'):run_sales.ensure_merly_child_env(tmp_path)
    assert p.read_bytes()==before and not list(tmp_path.glob('config.before-merly-env-*'))

def test_unexpected_child_env_fails_without_rewriting(tmp_path):
    c=original_config();c['mcp_servers']['merly']['env']={'OTHER_KEY':'synthetic-not-real'}
    p=tmp_path/'config.yaml';p.write_text(yaml.safe_dump(c));before=p.read_bytes()
    with pytest.raises(RuntimeError,match='unexpected_merly_child_environment'):run_sales.ensure_merly_child_env(tmp_path)
    assert p.read_bytes()==before

def test_new_template_requires_no_migration(tmp_path):
    c=json.loads((ROOT/'hermes-config.template.json').read_text());p=tmp_path/'config.yaml';p.write_text(yaml.safe_dump(c))
    assert run_sales.ensure_merly_child_env(tmp_path) is False
