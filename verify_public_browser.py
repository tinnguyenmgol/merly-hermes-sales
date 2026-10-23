"""Real Chromium+WSGI public UI/iframe; scripted native replies and synthetic sources; no paid inference."""
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
        rows=[{'color':color,'size':str(scope['size']),'price_vnd':310000,'available':True,'locations':[{'name':'Kho fixture','available':1}],'product_url':'https://merlyshoes.com/products/fixture-only'} for color in ([scope['color']] if scope.get('color') else ('Trắng Kem','chì bạc'))]
        return {'reply':'SYNTHETIC source <img src=x onerror=alert(1)>','stock_options':{'mode':'all_options','model_code':'1514','size':scope['size'],'complete':True,'variants':rows},'model_called':False}
    c.probe_stock=probe
    searches=[]
    def search(scope):
        searches.append(scope)
        return {'reply':'SYNTHETIC discovery','stock_options':{'mode':'discovery','criteria':scope,'complete':True,'products':[],'variants':[{'product_id':100,'title':'Fixture <img src=x onerror=alert(1)>','color':'Đen','size':str(scope['size']),'available':True,'price_vnd':310000,'locations':[{'name':'Kho fixture','available':1}],'product_url':'https://merlyshoes.com/products/fixture-only'}]},'model_called':False}
    c.discover_products=search
    # Scripted model decisions test UI transport only, not language understanding.
    import dialogue
    scripted=iter([lambda:{'reply':'SCRIPTED warranty 365 ngày','engine':'hermes'},lambda:search({'heel_cm':5.0,'size':41,'limit':4}),lambda:probe({'model_code':'1514','size':38,'color':'đen'}),lambda:probe({'model_code':'1514','size':42,'color':'đen'}),lambda:probe({'model_code':'1514','size':42})])
    native_histories=[]
    def native(message,user,cid):
        native_histories.append(dialogue.history(dialogue.sid(user)))
        return {**next(scripted)(),'conversation_id':'resp_scripted_browser','model_called':True}
    c.chat=native
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
            expect(page.locator('.stock').last).to_contain_text('Fixture <img')
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
                assert b and b['width']==116 and b['height']==72 and b['x']>=0 and b['y']>=0
                assert b['x']+b['width']<=width and b['y']+b['height']<=height
                assert button.evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(66, 46, 36)'
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
            chat.locator('#message').fill('màu đen thì sao');chat.locator('#send').click()
            expect(chat.locator('.stock strong').last).to_contain_text('đen')
            chat.locator('#message').fill('còn 42');chat.locator('#send').click()
            expect(chat.locator('.stock > strong').last).to_contain_text('size 42')
            assert calls[-1]=={'model_code':'1514','size':42,'color':'đen'}
            chat.locator('#message').fill('còn màu nào');chat.locator('#send').click()
            expect(chat.locator('.option')).to_have_count(6)
            assert calls[-1]=={'model_code':'1514','size':42}
            button.click();expect(button).to_have_attribute('aria-expanded','false')
            button.click();expect(framed.locator('#merly-chat-widget iframe')).to_have_count(1)
            button.focus();button.press('Escape');expect(button).to_have_attribute('aria-expanded','false')
            assert public_payloads and all(set(p)=={'message'} for p in public_payloads)
            assert len(native_histories)==5 and '365' in native_histories[1][-1]['content']
            assert 'LỊCH SỬ' in native_histories[2][-1]['content']
            assert not errors,errors
            touch=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
            touch.route('https://chat.merlyshoes.com/**',proxy)
            touch.route('https://merlyshoes.com/**',lambda route:route.fulfill(status=200,body='<meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://chat.merlyshoes.com/embed.js" defer></script>',content_type='text/html'))
            mobile=touch.new_page();mobile.goto('https://merlyshoes.com/')
            mb=mobile.locator('#merly-chat-widget button');expect(mb).to_have_attribute('aria-label','Mở trợ lý Merly')
            assert mb.bounding_box()['width']==116
            assert mobile.locator('#merly-chat-widget .tip').count()==0
            mb.tap();expect(mb).to_have_attribute('aria-expanded','true')
            expect(mobile.frame_locator('#merly-chat-widget iframe').locator('h1')).to_contain_text('Merly')
            mb.tap();expect(mb).to_have_attribute('aria-expanded','false')
            touch.close()
            browser.close()
        print('PASS_PUBLIC_CHROMIUM no_login_key=true csrf_cookie=true source_query=true paid_inference_calls=0 native_scripted_turns=5 xss_literal=true Haravan_main_iframe=true legacy_embed_tag=true singleton_lazy_widget=true official_merly_logo=true prominent_116x72_mobile_desktop=true no_floating_tooltip=true no_consent_checkbox=true no_fabricated_consent_field=true native_policy_catalog=true contextual_followups=true synthetic_only=true')
    finally:server.shutdown();server.server_close()
