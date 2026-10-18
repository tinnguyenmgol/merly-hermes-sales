"""Offline Compose env precedence model and real startup guard; no real secrets."""
import json
from pathlib import Path
import pytest
import run_sales

class ExecReached(Exception):pass

def test_explicit_empty_masks_platform_env():
    services=json.loads((Path(__file__).resolve().parents[1]/'compose.hermes.json').read_text())['services']
    platform_env={'HARAVAN_ACCESS_TOKEN':'synthetic-offline-test-value'}
    effective={**platform_env,**services['sales-gateway']['environment']}
    assert effective['HARAVAN_ACCESS_TOKEN']==''
    assert services['hermes-sales']['environment']['HARAVAN_ACCESS_TOKEN']=='${HARAVAN_ACCESS_TOKEN:-}'


def test_gateway_still_refuses_haravan_secret(monkeypatch):
    monkeypatch.setenv('PILOT_ROLE','gateway')
    monkeypatch.setenv('HARAVAN_ACCESS_TOKEN','synthetic-offline-test-value')
    def unexpected(*args):pytest.fail('gateway executed despite forbidden token')
    monkeypatch.setattr(run_sales.os,'execvp',unexpected)
    with pytest.raises(RuntimeError,match='gateway_must_not_hold_haravan_token'):run_sales.main()


def test_gateway_starts_when_secret_explicitly_empty(monkeypatch):
    monkeypatch.setenv('PILOT_ROLE','gateway');monkeypatch.setenv('HARAVAN_ACCESS_TOKEN','')
    def execute(command,args):
        assert command==run_sales.sys.executable
        assert args[-1]=='sales_gateway:application'
        assert 'gunicorn' in args
        raise ExecReached()
    monkeypatch.setattr(run_sales.os,'execvp',execute)
    with pytest.raises(ExecReached):run_sales.main()
