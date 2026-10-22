"""Bounded read-only recovery; fixture data only, no real provider/Haravan calls."""
import copy,json,time
import pytest
import direct_stock as d,hermes_client as c,stock_report as s
from test_stock_options import source
from test_client import approved
from test_integrated_stock_v2 import wire,fresh,ARGS

def failed():return {'mode':'unverified','operation_status':'failed','model_code':'1514','size':38,'variants':[]}
def items(args=None):return [{'type':'function_call','name':'mcp__merly__search_products','arguments':json.dumps(args or ARGS)}]
def evidence(source):return s.classify(s.validate(fresh(),None,ARGS,turn_started=time.time()-1))

def test_valid_scope_uses_direct_evidence(source):
    calls=[];good=evidence(source)
    def probe(scope,timeout):calls.append((scope,timeout));return {'stock_options':good}
    r=d.recover(failed(),items(),probe,time.time())
    assert r['resolution_path']=='direct_haravan' and len(r['variants'])==20
    assert calls[0][0]=={'model_code':'1514','size':38} and 0<calls[0][1]<=30

@pytest.mark.parametrize('extra',[{'heel_cm':5},{'category':'sandal'},{'occasion':'party'},{'quantity':2},{'size':'38'},{'model_code':1514},{'unknown':'value'},{'color':''}])
def test_never_coerces_scope_or_drops_meaningful_criteria(extra):
    calls=[]
    r=d.recover(failed(),items({**ARGS,**extra}),lambda *a,**k:calls.append(1),time.time())
    assert not calls and r['operation_status']=='failed'

def test_null_unused_criteria_do_not_become_fake_filters(source):
    seen=[];good=evidence(source)
    def probe(scope,timeout):seen.append(scope);return {'stock_options':good}
    r=d.recover(failed(),items({**ARGS,'color':None,'heel_cm':None}),probe,time.time())
    assert seen==[{'model_code':'1514','size':38}] and r['complete']

def test_valid_report_never_triggers_extra_read(source):
    good=evidence(source)
    assert d.recover(good,items(),lambda *a,**k:pytest.fail('unnecessary read'),time.time()) is good

def test_failed_direct_read_and_no_budget_stay_failure():
    def fail(*a,**k):raise RuntimeError('synthetic-private-error')
    r=d.recover(failed(),items(),fail,time.time())
    assert r['operation_status']=='failed' and r['direct_read_failed']
    r=d.recover(failed(),items(),lambda *a,**k:pytest.fail('budget expired'),time.time()-64)
    assert r['operation_status']=='failed'

def test_at_most_one_direct_attempt_for_multiple_scopes(source):
    other={**failed(),'model_code':'1676'};report={'mode':'groups','groups':[failed(),other]}
    calls=[];good=evidence(source)
    def probe(scope,timeout):calls.append(scope);return {'stock_options':good}
    r=d.recover(report,items()+items({**ARGS,'model_code':'1676'}),probe,time.time())
    assert len(calls)==1 and r['groups'][1]['operation_status']=='failed'

def test_client_does_not_hide_tool_failure_with_gateway_lookup(source,approved,monkeypatch):
    monkeypatch.setattr(c,'audit',lambda:True);requests=[];probes=[]
    def request(path,payload):
        requests.append(path);output=wire(fresh());output[1]['output']='{"error":"invalid tool arguments"}'
        return {'id':'resp_direct_recovery','status':'completed','output':output}
    def probe(scope,timeout):probes.append(scope);return {'stock_options':evidence(source)}
    monkeypatch.setattr(c,'request',request);monkeypatch.setattr(c,'probe_stock',probe)
    r=c.chat('synthetic explicit stock question','isolated-fixture')
    assert requests==['/responses'] and probes==[]
    assert r['stock_options']['mode']=='unverified'
    assert r['lookup_incomplete'] and r['answer_mode']=='evidence_guard'

def test_mcp_source_failure_uses_working_parent_api_reader(source):
    report={**evidence(source),'variants':[],'complete':False,'operation_status':'source_error'}
    calls=[];good=evidence(source)
    def probe(scope,timeout):calls.append(scope);return {'stock_options':good}
    r=d.recover(report,items(),probe,time.time())
    assert r['complete'] and len(r['variants'])==20 and len(calls)==1
