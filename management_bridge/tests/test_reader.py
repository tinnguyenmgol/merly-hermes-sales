import io,json,sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import reader

def test_fixed_get_only_and_private_projection(monkeypatch):
    monkeypatch.setenv('COOLIFY_DIAGNOSTICS_TOKEN','SYNTHETIC_DIAGNOSTIC_KEY')
    class Opener:
        def open(self,req,timeout):
            assert req.get_method()=='GET'
            assert req.full_url=='https://panel.merlyshoes.com/api/v1/deployments/applications/f3rhymt285isnfqa5pjmcnbx?skip=0&take=1'
            assert 'SYNTHETIC' not in req.full_url
            assert req.get_header('Authorization')=='Bearer SYNTHETIC_DIAGNOSTIC_KEY'
            return io.BytesIO(json.dumps({'deployments':[{'deployment_uuid':'fixture123','status':'failed','configuration_snapshot':{'PASSWORD':'HIDDEN_CONFIG'},'logs':json.dumps([{'output':'ERROR: source_checksum_mismatch'},{'output':'HARAVAN_ACCESS_TOKEN=PRIVATE_VALUE'},{'output':'Bearer SYNTHETIC_DIAGNOSTIC_KEY'}])}]}).encode())
    monkeypatch.setattr(reader.urllib.request,'build_opener',lambda *a:Opener())
    result=reader.build_log();text=json.dumps(result)
    assert 'source_checksum_mismatch' in text
    for secret in ['PRIVATE_VALUE','SYNTHETIC_DIAGNOSTIC_KEY','HIDDEN_CONFIG']:assert secret not in text
    assert result['sensitive_lines_hidden']==2

@pytest.mark.parametrize('skip,take',[(-1,1),(10,1),(0,4),(True,1),('0',1)])
def test_no_arbitrary_resource_or_window(skip,take):
    with pytest.raises(reader.ReadError):reader.fetch(skip,take)

def test_missing_key_no_network(monkeypatch):
    monkeypatch.delenv('COOLIFY_DIAGNOSTICS_TOKEN',raising=False)
    monkeypatch.setattr(reader.urllib.request,'build_opener',lambda *a:pytest.fail('Must not connect'))
    with pytest.raises(reader.ReadError,match='missing_token'):reader.build_log()

def test_missing_logs_are_not_empty_success(monkeypatch):
    monkeypatch.setattr(reader,'fetch',lambda **kw:[{'status':'failed'}])
    assert reader.build_log()['status']=='logs_missing_or_redacted'

def test_plain_log_bounds(monkeypatch):
    monkeypatch.setattr(reader,'fetch',lambda **kw:[{'logs':'\n'.join('line'+str(i) for i in range(500))}])
    result=reader.build_log(lines=20)
    assert result['truncated'] and result['lines_returned']==20 and 'line499' in result['log']

def test_no_redirects():assert reader.NoRedirect().redirect_request(None,None,None,None,None,None) is None
