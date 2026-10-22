"""Public-mode WSGI security; no real model/API calls."""
import io,json
import pytest
import sales_gateway as g,public_chat as p,hermes_client as c
from test_gateway import configured
ORIGIN='https://chat.merlyshoes.com'
@pytest.fixture
def public(configured,monkeypatch):
    monkeypatch.setenv('MERLY_PUBLIC_CHAT_ENABLED','1');monkeypatch.setenv('MERLY_PUBLIC_ORIGIN',ORIGIN)
    monkeypatch.setenv('MERLY_VISITOR_PER_MINUTE','4')
    p._RATE.clear()

def req(path,method='GET',cookie='',csrf='',origin=ORIGIN,data=None):
    raw=json.dumps(data).encode() if data is not None else b'';out={}
    env={'PATH_INFO':path,'REQUEST_METHOD':method,'HTTP_COOKIE':cookie,'HTTP_ORIGIN':origin,'HTTP_X_MERLY_CSRF':csrf,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
    def start(status,headers):out.update(status=status,headers=dict(headers))
    out['raw']=b''.join(g.application(env,start));return out

def session():
    r=req('/api/public/session');d=json.loads(r['raw']);return r['headers']['Set-Cookie'].split(';')[0],d['csrf']

def test_public_has_no_login_or_embedded_secret(public):
    r=req('/');assert r['status'].startswith('200') and b'access-key' not in r['raw']
    for path in ('/','/public.js','/public.css'):
        r=req(path);assert ('P'*40).encode() not in r['raw'] and ('S'*40).encode() not in r['raw']
        assert 'frame-ancestors https://merlyshoes.com' in r['headers']['Content-Security-Policy']

def test_public_stock_without_pilot_key(public,monkeypatch):
    monkeypatch.setattr(c,'chat',lambda *a:pytest.fail('must bypass model'))
    scopes=[]
    def probe(scope):scopes.append(scope);return {'reply':'synthetic source','stock_options':{},'model_called':False}
    monkeypatch.setattr(c,'probe_stock',probe)
    cookie,token=session();r=req('/api/public/chat','POST',cookie,token,data={'message':'mẫu 1514 38 còn màu gì'})
    assert r['status'].startswith('200') and scopes==[{'model_code':'1514','size':38}]
    assert 'merly_public_session=' in r['headers']['Set-Cookie']
    assert ('P'*40).encode() not in r['raw']

@pytest.mark.parametrize('origin',['https://evil.invalid','https://chat.merlyshoes.com.evil.invalid',''])
def test_cross_origin_rejected_before_calls(public,origin):
    cookie,token=session();r=req('/api/public/chat','POST',cookie,token,origin,{'message':'hello'})
    assert r['status'].startswith('403')

@pytest.mark.parametrize('payload',[{}, {'message':' '}, {'message':'x'*1001}, {'message':'hello','consent':False}, {'message':'hello','previous_response_id':'resp_other'}])
def test_message_and_scope_override_guard(public,payload):
    cookie,token=session();r=req('/api/public/chat','POST',cookie,token,data=payload)
    assert r['status'].startswith('400')

def test_csrf_bound_to_current_visitor(public):
    cookie1,csrf1=session();cookie2,csrf2=session();assert cookie1!=cookie2
    assert req('/api/public/chat','POST',cookie2,csrf1,data={'message':'hello'})['status'].startswith('403')
    assert req('/api/public/chat','POST',cookie1,'',data={'message':'hello'})['status'].startswith('403')

def test_private_tools_stay_private(public):
    assert req('/api/stock-check','POST',data={})['status'].startswith('401')
    assert req('/api/readiness')['status'].startswith('401')

def test_public_mode_opt_in(configured):
    assert req('/api/public/session')['status'].startswith('401')

def test_visitor_rate_and_private_error_sanitization(public,monkeypatch):
    def fail(*a):raise c.HermesError('private-error-fixture')
    monkeypatch.setattr(c,'chat',fail);cookie,token=session()
    for i in range(4):
        r=req('/api/public/chat','POST',cookie,token,data={'message':'hello'})
        assert r['status'].startswith('503') and b'private-error-fixture' not in r['raw']
    r=req('/api/public/chat','POST',cookie,token,data={'message':'hello'})
    assert r['status'].startswith('429')

def test_assets_cannot_accept_public_chat_posts(public):
    cookie,token=session()
    assert req('/public.js','POST',cookie,token,data={'message':'hello'})['status'].startswith('405')

def test_host_cookie_is_secure_http_only(public):
    r=req('/api/public/session');cookie=r['headers']['Set-Cookie']
    assert cookie.startswith('__Host-') and 'Domain=' not in cookie
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=Strict' in cookie

def test_legacy_embed_script_public_without_key(public):
    r=req('/embed.js')
    assert r['status'].startswith('200') and r['headers']['Content-Type']=='application/javascript; charset=utf-8'
    assert b'merly-chat-widget' in r['raw'] and ('P'*40).encode() not in r['raw']
    assert b'https://chat.merlyshoes.com/' in r['raw']
    assert b'innerHTML' not in r['raw']


def test_notice_instead_of_checkbox(public):
    html=req('/')['raw'].decode()
    assert 'type="checkbox"' not in html and 'Tôi đồng ý' not in html
    assert 'có thể lưu lịch sử' in html and 'dữ liệu nhạy cảm' in html
    assert html.index('id="privacy-notice"')>html.index('id="send"')
    js=req('/public.js')['raw'].decode()
    assert 'JSON.stringify({message})' in js and 'consent:true' not in js

def test_old_already_checked_tabs_still_work(public,monkeypatch):
    monkeypatch.setattr(c,'probe_stock',lambda scope:{'reply':'fixture','model_called':False})
    cookie,token=session()
    r=req('/api/public/chat','POST',cookie,token,data={'message':'mẫu 1514 38 còn màu gì','consent':True})
    assert r['status'].startswith('200')

def test_official_logo_and_explicit_product_cdn_csp(public):
    r=req('/merly-logo.png')
    assert r['status'].startswith('200') and r['headers']['Content-Type']=='image/png'
    assert r['raw'].startswith(b'\x89PNG\r\n\x1a\n')
    html=req('/')
    csp=html['headers']['Content-Security-Policy']
    assert "img-src 'self' https://product.hstatic.net https://file.hstatic.net https://cdn.hstatic.net https://theme.hstatic.net;" in csp
    assert '*' not in csp and 'data:' not in csp and "script-src 'self';" in csp
    assert b'/merly-logo.png' in html['raw']
    js=req('/embed.js')['raw']
    assert b'/merly-logo.png' in js and b'.tip{' not in js
