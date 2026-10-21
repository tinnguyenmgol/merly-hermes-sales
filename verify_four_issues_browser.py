"""Real Chromium + local WSGI. All model/network business data synthetic."""
import os,tempfile,threading,urllib.request,urllib.error,json,re
from pathlib import Path
from wsgiref.simple_server import make_server,WSGIRequestHandler
from playwright.sync_api import sync_playwright,expect
import sales_gateway as gateway,hermes_client as client
URL='https://merlyshoes.com/products/fixture-verified'
class Quiet(WSGIRequestHandler):
    def log_message(self,*a):pass
with tempfile.TemporaryDirectory(prefix='four-ui-',dir='/workspace/tmp') as tmp:
    os.environ.update(MERLY_PUBLIC_CHAT_ENABLED='1',MERLY_PUBLIC_ORIGIN='https://chat.merlyshoes.com',PILOT_ACCESS_KEY='P'*40,PILOT_SESSION_SECRET='S'*40,HERMES_PILOT_STATE_DB=tmp+'/state.db',HERMES_SALES_API_BASE='https://offline.invalid/v1',HERMES_SALES_API_KEY='T'*40,HERMES_SALES_ISOLATION_APPROVED='1',HERMES_CUSTOMER_DATA_APPROVED='1',HERMES_MODEL_COST_APPROVED='1')
    received=[]
    reply='[Mẫu từ nguồn]('+URL+')\n'+URL+'.\n[Chăm sóc](https://care.merlyshoes.com/)\n[x](javascript:alert(1)) https://evil.invalid/ https://merlyshoes.com/products/not-returned <img src=x onerror=alert(1)>'
    def chat(message,user,cid):
        received.append(message);return {'reply':reply,'conversation_id':'resp_fixture','source_links':[URL]}
    client.chat=chat
    server=make_server('127.0.0.1',0,gateway.application,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-gpu','--no-zygote','--renderer-process-limit=1'])
            context=browser.new_context(viewport={'width':390,'height':844});errors=[]
            def proxy(route):
                req=route.request;path=req.url.split('chat.merlyshoes.com',1)[1]
                headers={k:v for k,v in req.all_headers().items() if k not in ('host','content-length')}
                request=urllib.request.Request(base+path,data=req.post_data_buffer,headers=headers,method=req.method)
                try:r=urllib.request.urlopen(request,timeout=10)
                except urllib.error.HTTPError as e:r=e
                with r:route.fulfill(status=r.status,body=r.read(),headers=dict(r.headers))
            context.route('https://chat.merlyshoes.com/**',proxy)
            context.route('https://merlyshoes.com/products/**',lambda r:r.fulfill(status=200,body='<h1>SYNTHETIC PRODUCT PAGE</h1>',content_type='text/html'))
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto('https://chat.merlyshoes.com/')
            expect(page.locator('#status')).to_contain_text('sẵn sàng')
            field=page.locator('#message');field.fill('test links');field.press('Enter')
            expect(page.locator('.assistant')).to_have_count(1);assert received==['test links']
            bubble=page.locator('.assistant').last
            expect(bubble.locator('a')).to_have_count(3)
            assert bubble.locator('img,script').count()==0
            assert bubble.locator('a[href^="javascript:"],a[href*="evil.invalid"],a[href*="not-returned"]').count()==0
            link=bubble.get_by_role('link',name='Mẫu từ nguồn');expect(link).to_have_attribute('href',URL)
            with page.expect_popup() as event:link.click()
            popup=event.value;popup.wait_for_load_state();assert popup.url==URL and popup.evaluate('window.opener===null');popup.close()
            field.fill('modifier fixture');field.press('Control+Enter');assert len(received)==1
            field.fill('line one');field.press('Shift+Enter');field.press('End');field.type('line two')
            assert '\n' in field.input_value() and len(received)==1
            field.press('Enter');expect(page.locator('.assistant')).to_have_count(2)
            assert received[-1]=='line one\nline two'
            field.fill('composition fixture')
            field.dispatch_event('compositionstart');field.dispatch_event('keydown',{'key':'Enter','isComposing':True})
            page.wait_for_timeout(80);assert len(received)==2
            field.dispatch_event('compositionend');field.dispatch_event('keydown',{'key':'Enter','keyCode':229,'which':229})
            page.wait_for_timeout(80);assert len(received)==2
            field.press('Enter');expect(page.locator('.assistant')).to_have_count(3)
            page.evaluate("""()=>{window.__normalFetch=window.fetch;window.__testPosts=0;window.fetch=(url,opts)=>{if(url==='/api/public/chat'){window.__testPosts++;return new Promise(resolve=>{window.__release=()=>resolve({ok:true,json:async()=>({reply:'SYNTHETIC delayed response'})});});}return window.__normalFetch(url,opts);};}""")
            field.fill('busy fixture');field.press('Enter');expect(page.locator('#send')).to_be_disabled()
            field.fill('draft while pending');field.press('Enter');field.dispatch_event('keydown',{'key':'Enter','repeat':True})
            assert page.evaluate('window.__testPosts')==1
            page.evaluate('window.__release()');expect(page.locator('#send')).to_be_enabled()
            page.evaluate('window.fetch=window.__normalFetch')
            field.fill('');field.press('Enter');assert len(received)==3
            fixture='<meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:linear-gradient(120deg,#faf5ee,#d9c3a7);height:1000px}.back-to-top{position:fixed;right:16px;bottom:16px;width:40px;height:40px;background:white}</style><p>TRANG KIỂM THỬ GIAO DIỆN — KHÔNG PHẢI WEBSITE THẬT</p><button class="back-to-top">↑</button><script src="https://chat.merlyshoes.com/embed.js" defer></script>'
            context.route('https://merlyshoes.com/',lambda r:r.fulfill(status=200,body=fixture,content_type='text/html; charset=utf-8'))
            framed=context.new_page();framed.on('pageerror',lambda e:errors.append(str(e)));framed.goto('https://merlyshoes.com/')
            launcher=framed.locator('#merly-chat-widget button');expect(launcher).to_be_visible();framed.wait_for_timeout(100)
            for w,h in ((320,568),(390,844),(1440,900)):
                framed.set_viewport_size({'width':w,'height':h});framed.wait_for_timeout(80)
                a=launcher.bounding_box();b=framed.locator('.back-to-top').bounding_box()
                assert a['width']==116 and a['height']==72 and a['y']>=0 and a['x']>=0
                assert a['y']+a['height']<=b['y']-10
                assert launcher.evaluate('e=>getComputedStyle(e).backgroundColor')=='rgb(66, 46, 36)'
                def light(css):
                    values=[int(v)/255 for v in re.findall(r'\d+',css)[:3]]
                    return sum(weight*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for weight,v in zip((.2126,.7152,.0722),values))
                bg=light(launcher.evaluate('e=>getComputedStyle(e).backgroundColor'));fg=light(launcher.locator('.caption').evaluate('e=>getComputedStyle(e).color'))
                contrast=(max(bg,fg)+.05)/(min(bg,fg)+.05);assert contrast>=4.5
            framed.set_viewport_size({'width':390,'height':844});framed.wait_for_timeout(80)
            preview=os.getenv('MERLY_DESIGN_PREVIEW_DIR')
            if preview:
                Path(preview).mkdir(parents=True,exist_ok=True)
                framed.screenshot(path=str(Path(preview)/'prominent-merly-launcher.png'))
            launcher.click()
            iframe=framed.frame_locator('#merly-chat-widget iframe');expect(iframe.locator('#status')).to_contain_text('sẵn sàng')
            bounds=framed.locator('#merly-chat-widget section').bounding_box();assert bounds['y']>=0
            iframe.locator('#message').fill('iframe links');iframe.locator('#message').press('Enter')
            expect(iframe.locator('.assistant a')).to_have_count(3)
            with framed.expect_popup() as event:iframe.get_by_role('link',name='Mẫu từ nguồn').click()
            child=event.value;child.wait_for_load_state();assert child.url==URL and child.evaluate('window.opener===null');child.close()
            if preview:
                reply='Merly chào bạn! Bạn muốn tìm mẫu, size hay màu nào? [Xem website Merly](https://merlyshoes.com/) · [Chăm sóc khách hàng](https://care.merlyshoes.com/)'
                childframe=next(f for f in framed.frames if f.url.startswith('https://chat.merlyshoes.com/'))
                childframe.goto('https://chat.merlyshoes.com/')
                expect(iframe.locator('#status')).to_contain_text('sẵn sàng')
                iframe.locator('#message').fill('Xin chào Merly');iframe.locator('#message').press('Enter')
                expect(iframe.locator('.assistant')).to_have_count(1)
                framed.locator('#merly-chat-widget').screenshot(path=str(Path(preview)/'chat-clickable-links.png'))
            assert not errors,errors
            browser.close()
        print('PASS_FOUR_UI enter=true shift_enter_newline=true ime_guard=true no_duplicate_busy=true safe_source_links=true sandbox_popup=true brand_contrast=true collision_avoided=true synthetic_only=true caption_contrast='+str(round(contrast,2)))
    finally:server.shutdown();server.server_close()
