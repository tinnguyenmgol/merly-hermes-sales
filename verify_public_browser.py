"""Real Chromium+WSGI public UI/iframe; synthetic source data, no model calls."""
import os,threading,tempfile,urllib.request,urllib.error
from wsgiref.simple_server import make_server,WSGIRequestHandler
from playwright.sync_api import sync_playwright,expect
import sales_gateway as g,hermes_client as c
class Quiet(WSGIRequestHandler):
    def log_message(self,*a):pass
with tempfile.TemporaryDirectory(prefix='public-browser-') as tmp:
    os.environ.update({'MERLY_PUBLIC_CHAT_ENABLED':'1','MERLY_PUBLIC_ORIGIN':'https://chat.merlyshoes.com','PILOT_ACCESS_KEY':'P'*40,'PILOT_SESSION_SECRET':'S'*40,'HERMES_PILOT_STATE_DB':tmp+'/state.db','HERMES_SALES_API_BASE':'https://offline.invalid/v1','HERMES_SALES_API_KEY':'T'*40,'HERMES_SALES_ISOLATION_APPROVED':'1','HERMES_CUSTOMER_DATA_APPROVED':'1','HERMES_MODEL_COST_APPROVED':'1'})
    calls=[]
    def probe(scope):
        calls.append(scope)
        rows=[{'color':color,'size':'38','price_vnd':310000,'available':True,'locations':[{'name':'Kho fixture','available':1}],'product_url':'https://merlyshoes.com/products/fixture-only'} for color in ('Trắng Kem','chì bạc')]
        return {'reply':'SYNTHETIC source <img src=x onerror=alert(1)>','stock_options':{'mode':'all_options','model_code':'1514','size':38,'complete':True,'variants':rows},'model_called':False}
    c.probe_stock=probe
    c.chat=lambda *a:(_ for _ in ()).throw(AssertionError('must not call model'))
    server=make_server('127.0.0.1',0,g.application,handler_class=Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    local='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-gpu','--no-zygote','--renderer-process-limit=1'])
            context=browser.new_context(viewport={'width':390,'height':844});errors=[]
            def proxy(route):
                request=route.request;path=request.url.split('chat.merlyshoes.com',1)[1]
                headers={k:v for k,v in request.all_headers().items() if k not in ('host','content-length')}
                req=urllib.request.Request(local+path,data=request.post_data_buffer,headers=headers,method=request.method)
                try:r=urllib.request.urlopen(req,timeout=10)
                except urllib.error.HTTPError as e:r=e
                route.fulfill(status=r.status,body=r.read(),headers=dict(r.headers));r.close()
            context.route('https://chat.merlyshoes.com/**',proxy)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto('https://chat.merlyshoes.com/')
            expect(page.locator('#status')).to_contain_text('sẵn sàng')
            assert page.locator('input[type=password]').count()==0
            assert page.locator('#send').is_disabled();page.locator('#consent').check()
            page.locator('#message').fill('mẫu 1514 38 còn màu gì');page.locator('#send').click()
            expect(page.locator('.option')).to_have_count(2)
            assert page.locator('.turn img').count()==0 and '<img src=x' in page.locator('.turn').last.inner_text()
            assert page.evaluate('localStorage.length===0 && sessionStorage.length===0')
            assert calls==[{'model_code':'1514','size':38}]
            context.route('https://merlyshoes.com/**',lambda route:route.fulfill(status=200,body='<iframe src="https://chat.merlyshoes.com/"></iframe>',content_type='text/html'))
            framed=context.new_page();framed.goto('https://merlyshoes.com/')
            expect(framed.frame_locator('iframe').locator('h1')).to_contain_text('Merly')
            assert not errors,errors
            browser.close()
        print('PASS_PUBLIC_CHROMIUM no_login_key=true csrf_cookie=true source_query=true model_calls0=true xss_literal=true Haravan_main_iframe=true synthetic_only=true')
    finally:server.shutdown();server.server_close()
