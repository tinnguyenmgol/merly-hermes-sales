"""Real internal HTTP probe, synthetic Haravan responses; no model calls."""
import io,json,threading,urllib.request,urllib.error
import pytest
import stock_probe,hermes_client as c,sales_gateway as gateway
from test_stock_options import source
from test_gateway import configured

@pytest.fixture
def http_probe(source,monkeypatch):
    monkeypatch.setenv('API_SERVER_KEY','K'*40)
    server=stock_probe.make_server(('127.0.0.1',0))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield 'http://127.0.0.1:'+str(server.server_port)+'/stock'
    server.shutdown();server.server_close()

def fetch(url,data,key='K'*40):
    req=urllib.request.Request(url,data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=5) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)

def test_http_probe_returns_actual_v2_reader_result(http_probe):
    code,r=fetch(http_probe,{'model_code':'1514','size':38})
    assert code==200 and r['stock_report']['schema']=='merly-stock-options-v2'
    assert len(r['stock_report']['variants'])==20

def test_auth_blocks_before_source(http_probe,source):
    assert fetch(http_probe,{'model_code':'1514','size':38},'wrong')[0]==401
    assert source['calls']==[]

@pytest.mark.parametrize('data',[{'model_code':'1514','size':'38'},{'model_code':'1514','size':True},{'model_code':'1514','size':38,'url':'https://evil.invalid'},{'tool':'create_order'}])
def test_scope_not_coerced_or_arbitrary_tool(http_probe,data,source):
    assert fetch(http_probe,data)[0]==400 and source['calls']==[]

def test_gateway_probe_cannot_invoke_model(configured,monkeypatch):
    monkeypatch.setattr(c,'chat',lambda *a:pytest.fail('model must not be invoked'))
    calls=[]
    def probe(scope):calls.append(scope);return {'reply':'synthetic stock','model_called':False}
    monkeypatch.setattr(c,'probe_stock',probe)
    raw=json.dumps({'model_code':'1514','size':38}).encode();out={}
    env={'REQUEST_METHOD':'POST','PATH_INFO':'/api/stock-check','CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'HTTP_AUTHORIZATION':'Bearer '+'P'*40,'wsgi.input':io.BytesIO(raw)}
    body=json.loads(b''.join(gateway.application(env,lambda status,headers:out.update(status=status))))
    assert out['status'].startswith('200') and body['model_called'] is False
    assert calls==[{'model_code':'1514','size':38}]

def test_actual_gateway_proxy_validates_real_internal_http_response(http_probe,configured,monkeypatch):
    monkeypatch.setenv('HERMES_SALES_API_KEY','K'*40)
    actual=urllib.request.build_opener(c.NoRedirect)
    class LocalProxy:
        def open(self,req,timeout):
            assert req.full_url=='http://hermes-sales:8644/stock'
            assert req.get_header('Authorization')=='Bearer '+'K'*40
            target=urllib.request.Request(http_probe,data=req.data,headers=dict(req.header_items()),method='POST')
            return actual.open(target,timeout=timeout)
    monkeypatch.setattr(c.urllib.request,'build_opener',lambda *a:LocalProxy())
    monkeypatch.setattr(c,'chat',lambda *a:pytest.fail('no model allowed'))
    r=c.probe_stock({'model_code':'1514','size':38})
    assert r['model_called'] is False and r['stock_options']['complete']
    assert len(r['stock_options']['variants'])==20

def test_catalog_search_real_http_requires_verified_specs(http_probe,source,monkeypatch):
    import merly_tools as tools
    url=http_probe.rsplit('/',1)[0]+'/catalog-search'
    scope={'heel_cm':5.0,'size':38,'limit':4}
    monkeypatch.setattr(tools,'enrichment',lambda:{})
    code,data=fetch(url,scope)
    assert code==200 and data['status']=='partial_metadata' and not data['products']
    monkeypatch.setattr(tools,'enrichment',lambda:{'100':{'heel_cm':5}})
    code,data=fetch(url,scope)
    assert code==200 and data['products'][0]['verified_specs']['heel_cm']==5
    assert data['stock_checked'] is False and source['calls']==[]
    assert fetch(url,dict(scope,url='https://evil.invalid'))[0]==400
    assert fetch(url,scope,key='wrong')[0]==401

def test_catalog_client_reads_real_http_without_inference(http_probe,configured,monkeypatch):
    import merly_tools as tools
    monkeypatch.setattr(tools,'enrichment',lambda:{})
    monkeypatch.setenv('HERMES_SALES_API_KEY','K'*40)
    actual=urllib.request.build_opener(c.NoRedirect)
    class Local:
        def open(self,req,timeout):
            assert req.full_url=='http://hermes-sales:8644/catalog-search'
            target=urllib.request.Request(http_probe.rsplit('/',1)[0]+'/catalog-search',data=req.data,headers=dict(req.header_items()),method='POST')
            return actual.open(target,timeout=timeout)
    monkeypatch.setattr(c.urllib.request,'build_opener',lambda *a:Local())
    r=c.search_catalog({'heel_cm':5.0,'size':38,'limit':4})
    assert r['model_called'] is False and r['stock_checked'] is False
    assert 'chưa đủ dữ liệu' in r['reply'] and 'không phải kết luận hết hàng' in r['reply']
