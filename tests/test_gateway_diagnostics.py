import json,urllib.error
import pytest
import hermes_client as c
from test_client import approved
from test_gateway import configured,call

@pytest.mark.parametrize('code',['hermes_timeout','turn_not_completed','missing_final_message','hermes_http_502'])
def test_safe_diagnostic_matches_server_log(configured,monkeypatch,caplog,code):
    def fail(*a):raise c.HermesError(code)
    monkeypatch.setattr(c,'chat',fail)
    out=call('private-fixture-message')
    body=out['body'];assert out['status'].startswith('503') and 'reply' not in body
    assert body['reason_code']==code and len(body['diagnostic_id'])==16
    assert body['diagnostic_id'] in caplog.text and 'elapsed_ms' in caplog.text
    assert 'private-fixture-message' not in caplog.text and 'P'*40 not in caplog.text
    assert body['retry_automatically'] is False

def test_untrusted_exception_text_is_not_exposed(configured,monkeypatch,caplog):
    def fail(*a):raise c.HermesError('sensitive-fixture-token-and-customer-text')
    monkeypatch.setattr(c,'chat',fail)
    out=call('another-private-message')
    assert out['body']['reason_code']=='unclassified_hermes_error'
    assert 'sensitive-fixture' not in json.dumps(out)+caplog.text

@pytest.mark.parametrize('wrapped',[False,True])
def test_timeout_distinct_from_network_error(approved,monkeypatch,wrapped):
    class Opener:
        def open(self,*a,**k):
            if wrapped:raise urllib.error.URLError(TimeoutError('private-connection-details'))
            raise TimeoutError('private-connection-details')
    monkeypatch.setattr(c.urllib.request,'build_opener',lambda *a:Opener())
    with pytest.raises(c.HermesError,match='^hermes_timeout$'):c.request('/responses',{'input':'private'})

def test_provider_reason_logged_without_provider_text(configured,monkeypatch,caplog):
    def fail(*a):
        exc=c.HermesError('turn_not_completed');exc.response_status='failed';exc.provider_reason='provider_billing';raise exc
    monkeypatch.setattr(c,'chat',fail)
    out=call('private-fixture-message')
    assert out['body']['provider_reason']=='provider_billing'
    assert '"provider_reason": "provider_billing"' in caplog.text and out['body']['diagnostic_id'] in caplog.text

def test_untrusted_provider_reason_is_dropped(configured,monkeypatch,caplog):
    def fail(*a):
        exc=c.HermesError('turn_not_completed');exc.provider_reason='sk-or-secret-from-provider';raise exc
    monkeypatch.setattr(c,'chat',fail)
    out=call('x')
    assert out['body']['provider_reason']=='not_available' and 'sk-or-secret' not in caplog.text
