"""Real gateway WSGI endpoints; model calls mocked and explicitly synthetic."""
import io,json
from test_gateway import configured
import sales_gateway as g,hermes_client as client,state

def req(path,method='GET',auth=False,cookie=''):
    out={};env={'PATH_INFO':path,'REQUEST_METHOD':method,'HTTP_COOKIE':cookie,'wsgi.input':io.BytesIO(b'{}'),'CONTENT_TYPE':'application/json','CONTENT_LENGTH':'2'}
    if auth:env['HTTP_AUTHORIZATION']='Bearer '+'P'*40
    def start(status,headers):out.update(status=status,headers=dict(headers))
    out['raw']=b''.join(g.application(env,start));return out

def test_public_login_assets_no_embedded_keys(configured):
    for path in ['/','/pilot.js','/pilot.css']:
        r=req(path);assert r['status'].startswith('200')
        assert ('P'*40).encode() not in r['raw']
        assert r['headers']['Cache-Control']=='no-store'
        assert "frame-ancestors 'none'" in r['headers']['Content-Security-Policy']
    assert req('/../.env')['status'].startswith('401')

def test_readiness_requires_auth(configured,monkeypatch):
    monkeypatch.setattr(client,'audit',lambda:(_ for _ in ()).throw(AssertionError('no anonymous probes')))
    assert req('/api/readiness')['status'].startswith('401')

def test_readiness_flags_fail_without_inference(configured,monkeypatch):
    monkeypatch.setenv('HERMES_MODEL_COST_APPROVED','0')
    monkeypatch.setattr(client,'audit',lambda:(_ for _ in ()).throw(AssertionError('must stop before audit')))
    r=req('/api/readiness',auth=True);body=json.loads(r['raw'])
    assert r['status'].startswith('503') and body['missing_approvals']==['HERMES_MODEL_COST_APPROVED']

def test_readiness_does_not_claim_model_acceptance(configured,monkeypatch):
    monkeypatch.setattr(client,'audit',lambda:True)
    monkeypatch.setattr(client,'chat',lambda *a:(_ for _ in ()).throw(AssertionError('no inference')))
    r=req('/api/readiness',auth=True);assert r['status'].startswith('200')
    assert json.loads(r['raw'])=={'ready':True,'model_inference_tested':False,'pilot_only':True}

def test_logout_clears_mapping_and_secure_cookie(configured):
    token,sid=state.identity('');state.reserve(sid);state.save(sid,'resp_previous')
    r=req('/api/logout',method='POST',auth=True,cookie='merly_hermes_pilot='+token)
    assert r['status'].startswith('200')
    cookie=r['headers']['Set-Cookie'];assert all(x in cookie for x in ['Max-Age=0','HttpOnly','Secure','SameSite=Strict'])
    assert state.reserve(sid)==''

def test_frontend_no_persistent_secret_or_html_rendering():
    js=(g.WEB/'pilot.js').read_text()
    for bad in ['localStorage','sessionStorage','innerHTML','document.cookie','URLSearchParams']:assert bad not in js
    assert 'content.textContent = text' in js
