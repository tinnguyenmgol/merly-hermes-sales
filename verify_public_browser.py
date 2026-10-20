"""Real Chromium+WSGI public UI/iframe; synthetic source data, no model calls."""
import os,threading,tempfile,urllib.request,urllib.error
from pathlib import Path
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
    searches=[]
    def search(scope):
        searches.append(scope)
        return {'reply':'SYNTHETIC catalog; inventory not checked','products':[{'title':'Fixture <img src=x onerror=alert(1)>','product_url':'https://merlyshoes.com/products/fixture-only'}],'model_called':False}
    c.search_catalog=search
    c.chat=lambda *a:(_ for _ in ()).throw(AssertionError('must not call model'))
    server=make_server('127.0.0.1',0,g.application,handler_class=Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    local='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-gpu','--no-zygote','--renderer-process-limit=1'])
            context=browser.new_context(viewport={'width':390,'height':844});errors=[]
            public_payloads=[]
            def proxy(route):
                request=route.request;path=request.url.split('chat.merlyshoes.com',1)[1]
                if path=='/api/public/chat':
                    import json
                    public_payloads.append(json.loads(request.post_data_buffer))
                headers={k:v for k,v in request.all_headers().items() if k not in ('host','content-length')}
                req=urllib.request.Request(local+path,data=request.post_data_buffer,headers=headers,method=request.method)
                try:r=urllib.request.urlopen(req,timeout=10)
                except urllib.error.HTTPError as e:r=e
                route.fulfill(status=r.status,body=r.read(),headers=dict(r.headers));r.close()
            context.route('https://chat.merlyshoes.com/**',proxy)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto('https://chat.merlyshoes.com/')
            expect(page.locator('#status')).to_contain_text('sẵn sàng')
            preview=os.getenv('MERLY_DESIGN_PREVIEW_DIR')
            if preview:
                Path(preview).mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(Path(preview)/'merly-assistant-mobile.png'),full_page=True)
            assert page.locator('input[type=password]').count()==0
            expect(page.locator('header img')).to_have_attribute('src','/merly-logo.png')
            assert page.locator('header img').evaluate('(i)=>i.complete && i.naturalWidth===626')
            assert page.locator('#send').is_disabled();assert page.locator('input[type=checkbox]').count()==0
            page.locator('#message').fill('mẫu 1514 38 còn màu gì');page.locator('#send').click()
            expect(page.locator('.option')).to_have_count(2)
            assert page.locator('.turn img').count()==0 and '<img src=x' in page.locator('.turn').last.inner_text()
            assert page.evaluate('localStorage.length===0 && sessionStorage.length===0')
            assert calls==[{'model_code':'1514','size':38}]
            page.locator('#message').fill('bảo hành bao lâu?');page.locator('#send').click()
            expect(page.locator('.assistant').last).to_contain_text('365')
            page.locator('#message').fill('cần mẫu 5cm size 41');page.locator('#send').click()
            expect(page.locator('.stock strong').last).to_contain_text('Fixture <img')
            assert page.locator('.stock img').count()==0
            assert searches==[{'heel_cm':5.0,'size':41,'limit':4}]
            context.route('https://merlyshoes.com/**',lambda route:route.fulfill(status=200,body='<script src="https://chat.merlyshoes.com/embed.js" defer></script><script src="https://chat.merlyshoes.com/embed.js" defer></script>',content_type='text/html'))
            framed=context.new_page();framed.goto('https://merlyshoes.com/')
            expect(framed.locator('#merly-chat-widget')).to_have_count(1)
            expect(framed.locator('#merly-chat-widget iframe')).to_have_count(0)
            button=framed.locator('#merly-chat-widget button')
            expect(button).to_have_attribute('aria-label','Mở trợ lý Merly')
            for width,height in [(320,568),(390,844),(1440,900)]:
                framed.set_viewport_size({'width':width,'height':height})
                b=button.bounding_box()
                assert b and b['width']==104 and b['height']==64 and b['x']>=0 and b['y']>=0
                assert b['x']+b['width']<=width and b['y']+b['height']<=height
                assert button.evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 253, 251)'
                assert button.locator('svg').count()==0 and button.locator('img').count()==1
                expect(button.locator('.caption')).to_have_text('Trợ lý AI')
                assert button.locator('img').evaluate('(i)=>i.complete && i.naturalWidth===626')
            framed.set_viewport_size({'width':390,'height':844})
            button.click()
            expect(button).to_have_attribute('aria-label','Đóng trợ lý Merly')
            panel=framed.locator('#merly-chat-widget section').bounding_box()
            assert panel and panel['x']>=0 and panel['y']>=0 and panel['x']+panel['width']<=390

            chat=framed.frame_locator('#merly-chat-widget iframe')
            expect(chat.locator('h1')).to_contain_text('Merly')
            expect(chat.locator('#status')).to_contain_text('sẵn sàng')
            if preview:framed.locator('#merly-chat-widget').screenshot(path=str(Path(preview)/'merly-assistant-widget.png'))
            assert chat.locator('input[type=checkbox]').count()==0;chat.locator('#message').fill('mẫu 1514 38 còn màu gì');chat.locator('#send').click()
            expect(chat.locator('.option')).to_have_count(2)
            assert len(calls)==2
            button.click();expect(button).to_have_attribute('aria-expanded','false')
            button.click();expect(framed.locator('#merly-chat-widget iframe')).to_have_count(1)
            button.focus();button.press('Escape');expect(button).to_have_attribute('aria-expanded','false')
            assert public_payloads and all(set(p)=={'message'} for p in public_payloads)
            assert not errors,errors
            touch=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            touch.route('https://chat.merlyshoes.com/**',proxy)
            touch.route('https://merlyshoes.com/**',lambda route:route.fulfill(status=200,body='<meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://chat.merlyshoes.com/embed.js" defer></script>',content_type='text/html'))
            mobile=touch.new_page();mobile.goto('https://merlyshoes.com/')
            mb=mobile.locator('#merly-chat-widget button');expect(mb).to_have_attribute('aria-label','Mở trợ lý Merly')
            assert mb.bounding_box()['width']==104
            assert mobile.locator('#merly-chat-widget .tip').count()==0
            mb.tap();expect(mb).to_have_attribute('aria-expanded','true')
            expect(mobile.frame_locator('#merly-chat-widget iframe').locator('h1')).to_contain_text('Merly')
            mb.tap();expect(mb).to_have_attribute('aria-expanded','false')
            touch.close()
            browser.close()
        print('PASS_PUBLIC_CHROMIUM no_login_key=true csrf_cookie=true source_query=true model_calls0=true xss_literal=true Haravan_main_iframe=true legacy_embed_tag=true singleton_lazy_widget=true official_merly_logo=true branded_104x64_mobile_desktop=true no_floating_tooltip=true no_consent_checkbox=true no_fabricated_consent_field=true fast_policy_catalog=true synthetic_only=true')
    finally:server.shutdown();server.server_close()
