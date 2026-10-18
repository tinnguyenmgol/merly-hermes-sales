"""Real Compose CLI config (no daemon) plus a model of Coolify's empty-string DB override.
Only synthetic values. This is not execution of the deployed Coolify parser.
Enable with MERLY_OFFLINE_COMPOSE_BINARY pointing to an audited standalone binary.
"""
import json,os,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
BINARY=os.getenv('MERLY_OFFLINE_COMPOSE_BINARY')
pytestmark=pytest.mark.skipif(not BINARY,reason='standalone Compose binary required; no daemon used')

def render(tmp_path,value,gateway_value,reserved=None):
    # Mirrors applicationParser's literal-empty compatibility override.
    gateway_value=value if gateway_value=='' and value else gateway_value
    envfile=tmp_path/'platform.env'
    envfile.write_text(('' if value is None else 'HARAVAN_ACCESS_TOKEN='+value+'\n') + ('' if reserved is None else 'MERLY_GATEWAY_HARAVAN_EMPTY='+reserved+'\n'))
    services={
      'gateway':{'image':'busybox:1.37.0','env_file':[str(envfile)],'environment':{'HARAVAN_ACCESS_TOKEN':gateway_value}},
      'backend':{'image':'busybox:1.37.0','env_file':[str(envfile)],'environment':{'HARAVAN_ACCESS_TOKEN':'${HARAVAN_ACCESS_TOKEN:-}'}}
    }
    compose=tmp_path/'compose.json';compose.write_text(json.dumps({'services':services}))
    env=dict(os.environ);env.pop('HARAVAN_ACCESS_TOKEN',None);env.pop('MERLY_GATEWAY_HARAVAN_EMPTY',None)
    p=subprocess.run([BINARY,'--project-name','merly-offline-test','--env-file',str(envfile),'-f',str(compose),'config','--format','json'],env=env,cwd=tmp_path,capture_output=True,text=True,timeout=20,check=True)
    return json.loads(p.stdout)['services']

@pytest.mark.parametrize('value',[None,'','synthetic-haravan-not-a-real-token'])
def test_runtime_empty_after_coolify_and_compose(tmp_path,value):
    expression=json.loads((ROOT/'compose.hermes.json').read_text())['services']['sales-gateway']['environment']['HARAVAN_ACCESS_TOKEN']
    result=render(tmp_path,value,expression)
    assert result['gateway']['environment']['HARAVAN_ACCESS_TOKEN']==''
    assert result['backend']['environment']['HARAVAN_ACCESS_TOKEN']==(value or '')

def test_old_literal_empty_reproduces_secret_injection(tmp_path):
    value='synthetic-haravan-not-a-real-token'
    result=render(tmp_path,value,'')
    assert result['gateway']['environment']['HARAVAN_ACCESS_TOKEN']==value


def test_reserved_empty_still_masks_platform_token(tmp_path):
    result=render(tmp_path,'synthetic-token','${MERLY_GATEWAY_HARAVAN_EMPTY:-}',reserved='')
    assert result['gateway']['environment']['HARAVAN_ACCESS_TOKEN']==''


def test_reserved_nonempty_does_not_silently_bypass_guard(tmp_path):
    result=render(tmp_path,'synthetic-token','${MERLY_GATEWAY_HARAVAN_EMPTY:-}',reserved='synthetic-misconfiguration')
    assert result['gateway']['environment']['HARAVAN_ACCESS_TOKEN']=='synthetic-misconfiguration'
    # run_sales.main must reject any nonempty value (tested in startup guard suite).
