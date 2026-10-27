"""Public HTTP errors expose fixed categories and correlation IDs, not secrets."""
import json,re,logging
import pytest
import hermes_client as c,public_chat as p
from test_public_chat import public,req,session
from test_gateway import configured

@pytest.mark.parametrize('reason,category',[
 ('hermes_timeout','timeout'),('hermes_http_504','timeout'),
 ('missing_final_message','response_incomplete'),('turn_not_completed','response_incomplete'),
 ('invalid_answer','response_incomplete'),('response_limit','response_incomplete'),
 ('hermes_http_401','configuration'),('sales_runtime_attestation_required','configuration'),
 ('hermes_http_429','upstream_limit'),('hermes_unavailable','request_failed'),
 ('PRIVATE_UNKNOWN_ERROR_SENTINEL','request_failed')])
def test_failed_turn_has_safe_category_and_matching_log_id(public,monkeypatch,caplog,reason,category):
    def fail(*args):raise c.HermesError(reason)
    monkeypatch.setattr(c,'chat',fail);cookie,csrf=session()
    with caplog.at_level(logging.ERROR,logger='merly.gateway'):
        response=req('/api/public/chat','POST',cookie,csrf,data={'message':'PRIVATE_USER_SENTINEL'})
    data=json.loads(response['raw'])
    assert response['status'].startswith('503') and data['error_category']==category
    assert re.fullmatch('[0-9a-f]{16}',data['diagnostic_id'])
    assert data['diagnostic_id'] in caplog.text
    assert data['retry_automatically'] is False
    assert 'reason_code' not in data and reason not in response['raw'].decode()
    assert 'PRIVATE_USER_SENTINEL' not in caplog.text
    assert ('P'*40) not in response['raw'].decode() and ('T'*40) not in response['raw'].decode()

@pytest.mark.parametrize('value',[None,{},[],1,True,'constructor','__proto__'])
def test_unknown_reason_does_not_become_public_text(value):
    assert p.error_category({'reason_code':value})=='request_failed'
