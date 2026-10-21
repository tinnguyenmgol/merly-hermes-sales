import io,json
import pytest
import sales_gateway as gateway
import state,hermes_client as client

def call(message,key='P'*40,cookie='',extra=None):
    data={'message':message};data.update(extra or {});raw=json.dumps(data).encode();out={}
    env={'REQUEST_METHOD':'POST','PATH_INFO':'/api/chat','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'HTTP_AUTHORIZATION':'Bearer '+key,'HTTP_COOKIE':cookie,'wsgi.input':io.BytesIO(raw)}
    def start(status,headers):out.update(status=status,headers=dict(headers))
    out['body']=json.loads(b''.join(gateway.application(env,start)));return out

@pytest.fixture
def configured(tmp_path,monkeypatch):
    for k,v in {'PILOT_ACCESS_KEY':'P'*40,'PILOT_SESSION_SECRET':'S'*40,'HERMES_PILOT_STATE_DB':str(tmp_path/'sessions.db'),'HERMES_SALES_API_BASE':'https://sales.example.invalid/v1','HERMES_SALES_API_KEY':'T'*40,'HERMES_SALES_ISOLATION_APPROVED':'1','HERMES_CUSTOMER_DATA_APPROVED':'1','HERMES_MODEL_COST_APPROVED':'1'}.items():monkeypatch.setenv(k,v)

def test_context_isolation_raw_input(configured,monkeypatch):
    calls=[]
    def fake(message,user,rid):
        calls.append((message,user,rid));return {'reply':'SYNTHETIC CONTRACT RESPONSE','conversation_id':'resp_'+str(len(calls))}
    monkeypatch.setattr(client,'chat',fake)
    a=call('size 39 chân dài bao nhiêu');cookie=a['headers']['Set-Cookie'].split(';')[0]
    b=call('có mẫu nào cao 5cm ko',cookie=cookie);c=call('size 39');d=call('tư vấn cho người mới')
    assert all(x['status'].startswith('200') for x in (a,b,c,d))
    assert c['body']['engine']=='clarification'
    assert calls[1][0]=='có mẫu nào cao 5cm ko' and calls[1][2]=='resp_1'
    assert calls[0][1]==calls[1][1]!=calls[2][1]
    assert calls[2][2]==''
    assert b['body']['engine']=='hermes' and 'conversation_id' not in b['body']

def test_client_cannot_override_scope(configured):
    assert call('hello',extra={'previous_response_id':'resp_owner'})['status'].startswith('400')
    assert call('hello',key='wrong')['status'].startswith('401')

def test_no_approved_instance_no_calls(configured,monkeypatch):
    monkeypatch.setenv('HERMES_SALES_ISOLATION_APPROVED','0')
    monkeypatch.setattr(client,'chat',lambda *a:pytest.fail('No default-owner fallback'))
    assert call('hello')['status'].startswith('503')

def test_failure_never_becomes_answer(configured,monkeypatch):
    def fail(*a):raise client.HermesError('interrupted')
    monkeypatch.setattr(client,'chat',fail)
    r=call('hello');assert r['status'].startswith('503') and 'reply' not in r['body']

def test_budget_persisted(configured):
    for _ in range(6):assert state.reserve('a') is not None
    assert state.reserve('b') is None
