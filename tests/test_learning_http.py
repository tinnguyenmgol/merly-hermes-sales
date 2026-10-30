"""Actual loopback HTTP; ingest cannot review, export or execute instructions."""
import sys,json,threading,urllib.request,urllib.error,io
from pathlib import Path
from wsgiref.simple_server import make_server,WSGIRequestHandler
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'learning-service'))
from learning_server import create_app
from learning_store import Store
from test_learning_store import event
TOKEN='SyntheticOnly_'+'x'*40
class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass

@pytest.fixture
def server(tmp_path):
    store=Store(tmp_path/'private');app=create_app(store,TOKEN)
    srv=make_server('127.0.0.1',0,app,handler_class=Quiet)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    yield 'http://127.0.0.1:'+str(srv.server_port),store
    srv.shutdown();srv.server_close();thread.join(timeout=2)

def request(base,path,data=None,token=TOKEN,raw=None):
    headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
    payload=raw if raw is not None else json.dumps(data).encode() if data is not None else None
    req=urllib.request.Request(base+path,data=payload,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=2) as r:return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:return e.code,json.loads(e.read())


def test_authenticated_ingest_and_duplicate_readback(server):
    base,store=server;status,body=request(base,'/v1/cases',event())
    assert status==201 and store.case(body['case_id'])['event']==event()
    assert request(base,'/v1/cases',event())==(200,{'case_id':body['case_id'],'created':False})
    assert request(base,'/health')[1]=={'status':'ready'}

@pytest.mark.parametrize('path',['/review','/export','/v1/approve','/v1/cases/approve'])
def test_ingest_token_has_no_network_review_capability(server,path):
    base,store=server
    assert request(base,path,{'decision':'approve','owner_confirmed':True})[0]==404
    assert store.list_cases()==[]


def test_unauthorized_and_raw_or_duplicate_json_data_never_saved(server):
    base,store=server
    assert request(base,'/v1/cases',event(),token='WRONG')[0]==401
    raw=event();raw['message']='PRIVATE_RAW_SENTINEL'
    status,body=request(base,'/v1/cases',raw)
    assert status==400 and 'PRIVATE_RAW_SENTINEL' not in json.dumps(body)
    assert request(base,'/v1/cases',raw=b'{"outcome":"guarded","outcome":"failed"}')[0]==400
    assert request(base,'/v1/cases',raw=b'x'*4097)[0]==400
    assert store.list_cases()==[] and b'PRIVATE_RAW_SENTINEL' not in store.path.read_bytes()


def test_gateway_client_delivers_sanitized_event_over_real_http(server,monkeypatch):
    import learning_events as client
    base,store=server
    monkeypatch.setattr(client,'URL',base+'/v1/cases')
    monkeypatch.setenv('MERLY_LEARNING_ENABLED','1');monkeypatch.setenv('MERLY_LEARNING_INGEST_TOKEN',TOKEN)
    assert client.emit('0123456789abcdef',{'answer_mode':'evidence_guard','reply':'PRIVATE_REPLY_SENTINEL'}, {'guard_reasons':['unsupported_stock_claim']})
    client._QUEUE.join()
    cases=store.list_cases();assert len(cases)==1
    assert 'PRIVATE_REPLY_SENTINEL' not in store.path.read_bytes().decode('latin1')


def test_background_janitor_really_purges_expired_cases(tmp_path):
    import time
    from learning_server import maintenance
    from learning_store import TTL
    now=[1700000000.0];store=Store(tmp_path/'private',clock=lambda:now[0]);store.ingest(event())
    now[0]+=TTL;stop=threading.Event();thread=threading.Thread(target=maintenance,args=(store,stop,.01));thread.start()
    try:
        end=time.monotonic()+2
        while time.monotonic()<end:
            with store.db() as db:
                if db.execute('SELECT count(*) FROM cases').fetchone()[0]==0:break
            time.sleep(.01)
        else:raise AssertionError('janitor did not purge')
    finally:stop.set();thread.join(timeout=2)
