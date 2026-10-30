"""Customer response/model budget is independent of learning delivery."""
import json,logging
import pytest
import learning_events as client,learning_contract
from test_gateway import configured,call
import hermes_client as c


def test_default_disabled_does_not_spawn_worker_or_send(monkeypatch):
    monkeypatch.delenv('MERLY_LEARNING_ENABLED',raising=False)
    monkeypatch.setattr(client,'send',lambda *a:pytest.fail('disabled network'))
    assert client.emit('0123456789abcdef',{'answer_mode':'evidence_guard'}) is False


def test_unavailable_collector_never_retries_or_logs_secret(monkeypatch,caplog):
    calls=[]
    def failed(*args):calls.append(1);raise RuntimeError('PRIVATE_TOKEN_SENTINEL')
    monkeypatch.setattr(client,'send',failed)
    monkeypatch.setenv('MERLY_LEARNING_ENABLED','1');monkeypatch.setenv('MERLY_LEARNING_INGEST_TOKEN','x'*48)
    with caplog.at_level(logging.WARNING):
        assert client.emit('0123456789abcdef',{'answer_mode':'evidence_guard','reply':'PRIVATE_REPLY_SENTINEL'})
        client._QUEUE.join()
    assert calls==[1] and 'PRIVATE_TOKEN_SENTINEL' not in caplog.text and 'PRIVATE_REPLY_SENTINEL' not in caplog.text


def test_capture_preserves_reply_and_model_budget(configured,monkeypatch):
    seen=[];captured=[]
    def chat(*args):
        seen.append(1)
        return {'reply':'Safe fallback','conversation_id':'resp_learning','answer_mode':'evidence_guard','_guard_reasons':['unsupported_stock_claim']}
    monkeypatch.setattr(c,'chat',chat)
    monkeypatch.setattr(client,'emit',lambda diag,answer=None,trace=None,**kw:captured.append(learning_contract.capture(diag,answer,trace,kw.get('failure'))))
    result=call('PRIVATE_CUSTOMER_MESSAGE_SENTINEL')
    assert result['status'].startswith('200') and result['body']['reply']=='Safe fallback' and seen==[1]
    assert len(captured)==1 and captured[0]['reason_codes']==['unsupported_stock_claim']
    assert 'PRIVATE_CUSTOMER_MESSAGE_SENTINEL' not in json.dumps(captured)


def test_transport_failure_captured_without_retry(configured,monkeypatch):
    seen=[];events=[]
    def failed(*args):seen.append(1);raise c.HermesError('hermes_timeout')
    monkeypatch.setattr(c,'chat',failed)
    monkeypatch.setattr(client,'emit',lambda diag,**kw:events.append(learning_contract.capture(diag,kw.get('answer'),kw.get('trace'),kw.get('failure'))))
    result=call('PRIVATE_CUSTOMER_MESSAGE_SENTINEL')
    assert result['status'].startswith('503') and seen==[1]
    assert len(events)==1 and events[0]['reason_codes']==['hermes_timeout']
    assert 'PRIVATE_CUSTOMER_MESSAGE_SENTINEL' not in json.dumps(events)
