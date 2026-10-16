import json,time
from pathlib import Path
import pytest
import hermes_client as c
import safety,audit_instance

@pytest.fixture
def approved(tmp_path,monkeypatch):
    for k,v in {'HERMES_SALES_API_BASE':'https://sales.example.invalid/v1','HERMES_SALES_API_KEY':'K'*40,'HERMES_SALES_ISOLATION_APPROVED':'1','HERMES_CUSTOMER_DATA_APPROVED':'1','HERMES_MODEL_COST_APPROVED':'1'}.items():monkeypatch.setenv(k,v)
    p=tmp_path/'audit.json'
    record={'created_at':time.time(),'api_base':c.endpoint(),'tools':sorted(c.EXPECTED),'memory_enabled':False,'user_profile_enabled':False}
    p.write_text(json.dumps({'record':record,'signature':safety.digest(record,'K'*40)}));monkeypatch.setenv('HERMES_SALES_ATTESTATION',str(p))
    return p

def responses(status='completed'):
    return {'id':'resp_test','status':status,'output':[{'type':'reasoning','summary':[{'text':'PRIVATE'}]},{'type':'message','phase':'commentary','content':[{'type':'output_text','text':'PROGRESS'}]},{'type':'message','role':'assistant','content':[{'type':'output_text','text':'FINAL'}]}]}

def test_response_contract_and_no_reasoning_leak(approved,monkeypatch):
    calls=[]
    def request(path,payload=None):
        calls.append((path,payload))
        if path=='/capabilities':return {'platform':'hermes-agent','features':{'responses_api':True}}
        if path=='/toolsets':return {'data':[{'name':'terminal','enabled':False,'tools':['terminal']}]}
        return responses()
    monkeypatch.setattr(c,'request',request)
    out=c.chat('có mẫu nào cao 5cm ko','merly-sales:web:opaque','resp_previous')
    assert out['reply']=='FINAL'
    payload=calls[-1][1]
    assert payload['input']=='có mẫu nào cao 5cm ko' and payload['previous_response_id']=='resp_previous'
    assert payload['store'] is True and payload['stream'] is False

@pytest.mark.parametrize('status',['failed','cancelled','in_progress','incomplete'])
def test_unsuccessful_not_completed(approved,monkeypatch,status):
    monkeypatch.setattr(c,'audit',lambda:True);monkeypatch.setattr(c,'request',lambda *a:responses(status))
    with pytest.raises(c.HermesError,match='turn_not_completed'):c.chat('hello','x')

def test_dangerous_instance_rejected(approved,monkeypatch):
    monkeypatch.setattr(c,'request',lambda path:{'platform':'hermes-agent','features':{'responses_api':True}} if path=='/capabilities' else {'data':[{'name':'terminal','enabled':True,'tools':['terminal']}]})
    with pytest.raises(c.HermesError,match='unsafe_enabled_toolset'):c.audit()

@pytest.mark.parametrize('base',['https://owner.invalid/p/default/v1','https://u:secret@host/v1','https://host/v1?key=x','http://localhost:8642/v1'])
def test_default_or_unsafe_endpoints_blocked(approved,monkeypatch,base):
    monkeypatch.setenv('HERMES_SALES_API_BASE',base);monkeypatch.delenv('HERMES_ALLOW_HTTP',raising=False)
    with pytest.raises(c.HermesError):c.endpoint()

def test_tampered_inventory_rejected(approved):
    data=json.loads(approved.read_text());data['record']['tools'].append('terminal');approved.write_text(json.dumps(data))
    with pytest.raises(safety.AuditError):safety.verify_attestation(c.endpoint(),'K'*40)

def test_expired_inventory_rejected(approved):
    data=json.loads(approved.read_text());record=data['record'];record['created_at']-=86401;data['signature']=safety.digest(record,'K'*40);approved.write_text(json.dumps(data))
    with pytest.raises(safety.AuditError):safety.verify_attestation(c.endpoint(),'K'*40)

def test_config_disables_cross_customer_memory():
    config=json.loads(Path('hermes-config.template.json').read_text());audit_instance.check_config(config)
    config['memory']['user_profile_enabled']=True
    with pytest.raises(ValueError):audit_instance.check_config(config)

def test_http_headers_not_payload_scope(approved,monkeypatch):
    import io
    class Opener:
        def open(self,req,timeout):
            assert req.get_header('X-hermes-session-key')=='merly-sales:web:opaque'
            body=json.loads(req.data);assert '_session_scope' not in body
            assert req.get_header('Authorization')=='Bearer '+'K'*40
            return io.BytesIO(json.dumps(responses()).encode())
    monkeypatch.setattr(c.urllib.request,'build_opener',lambda *a:Opener())
    assert c.request('/responses',{'input':'hello','_session_scope':'merly-sales:web:opaque'})['status']=='completed'
