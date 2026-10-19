"""Real Chromium + actual WSGI gateway + explicitly synthetic model fixture."""
import os,tempfile,threading
from wsgiref.simple_server import make_server,WSGIRequestHandler
from playwright.sync_api import sync_playwright,expect
import sales_gateway as gateway,hermes_client
class Quiet(WSGIRequestHandler):
    def log_message(self,*a):pass
with tempfile.TemporaryDirectory(prefix='pilot-browser-') as temp:
    os.environ.update({'PILOT_ACCESS_KEY':'P'*40,'PILOT_SESSION_SECRET':'S'*40,'HERMES_PILOT_STATE_DB':temp+'/state.db','HERMES_SALES_API_BASE':'https://offline.invalid/v1','HERMES_SALES_API_KEY':'T'*40,'HERMES_SALES_ISOLATION_APPROVED':'1','HERMES_CUSTOMER_DATA_APPROVED':'1','HERMES_MODEL_COST_APPROVED':'1'})
    calls=[]
    hermes_client.audit=lambda:True
    def synthetic(message,user,previous):
        calls.append((message,user,previous))
        return {'reply':'OFFLINE FIXTURE — NOT GEMINI <img src=x onerror=alert(1)>','conversation_id':'resp_fixture_'+str(len(calls))}
    hermes_client.chat=synthetic
    server=make_server('127.0.0.1',0,gateway.application,handler_class=Quiet)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://localhost:'+str(server.server_port)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-gpu','--no-zygote','--renderer-process-limit=1'])
            errors=[]
            context=browser.new_context(viewport={'width':390,'height':844})
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            def login(page,key='P'*40):
                page.goto(url);page.locator('#access-key').fill(key);page.locator('#login-button').click()
            login(page,'wrong-key-'+'x'*32)
            expect(page.locator('#status')).to_contain_text('không đúng')
            page.locator('#access-key').fill('P'*40);page.locator('#login-button').click()
            expect(page.locator('#status')).to_contain_text('Model chưa được thử')
            assert page.locator('#access-key').input_value()==''
            assert page.locator('#send').is_disabled()
            page.locator('#test-consent').check()
            def send(page,text,count):
                page.locator('#message').fill(text);page.locator('#send').click()
                expect(page.locator('.turn.assistant')).to_have_count(count)
            send(page,'Câu hỏi giả lập thứ nhất',1)
            send(page,'Câu hỏi giả lập tiếp theo',2)
            assert page.locator('.turn.assistant img').count()==0
            assert '<img src=x' in page.locator('.turn.assistant').first.inner_text()
            assert calls[0][1]==calls[1][1] and calls[1][2]=='resp_fixture_1'
            assert page.evaluate('localStorage.length === 0 && sessionStorage.length === 0')
            page2=browser.new_page();page2.on('pageerror',lambda e:errors.append(str(e)))
            login(page2);expect(page2.locator('#status')).to_contain_text('Model chưa được thử')
            page2.locator('#test-consent').check();send(page2,'Phiên giả lập khác',1)
            assert calls[2][1]!=calls[0][1] and calls[2][2]==''
            page.locator('#new-chat').click();expect(page.locator('.turn')).to_have_count(0)
            send(page,'Câu đầu phiên mới',1);assert calls[3][2]==''
            page.locator('#logout').click();expect(page.locator('#status')).to_contain_text('Đã đăng xuất')
            assert page.locator('#login-form').is_visible()
            assert not any(c['name']=='merly_hermes_pilot' for c in context.cookies())
            failure_calls=[]
            def failed_model(*args):
                failure_calls.append(1)
                raise hermes_client.HermesError('synthetic-no-real-model')
            hermes_client.chat=failed_model
            page2.locator('#message').fill('Lượt lỗi giả lập');page2.locator('#send').click()
            expect(page2.locator('#status')).to_contain_text('Không tự gửi lại')
            page2.wait_for_timeout(1000);assert len(failure_calls)==1
            page2.close();context.close()
            os.environ['HERMES_MODEL_COST_APPROVED']='0'
            blocked=browser.new_page();login(blocked)
            expect(blocked.locator('#status')).to_contain_text('HERMES_MODEL_COST_APPROVED')
            blocked.locator('#test-consent').check();assert blocked.locator('#send').is_disabled()
            blocked.close()
            unsafe=browser.new_context();unsafe_page=unsafe.new_page()
            def assets_only(route):
                from urllib.parse import urlsplit
                asset=gateway.ASSETS.get(urlsplit(route.request.url).path)
                if asset:route.fulfill(status=200,body=(gateway.WEB/asset[0]).read_bytes(),headers={'Content-Type':asset[1],**dict(gateway.SECURITY)})
                else:route.abort()
            unsafe.route('**/*',assets_only)
            unsafe_page.goto('http://pilot-insecure.test/')
            expect(unsafe_page.locator('#status')).to_contain_text('HTTPS')
            assert unsafe_page.locator('#login-button').is_disabled()
            unsafe.close()
            assert errors==[],errors
            browser.close()
        print('PASS_REAL_CHROMIUM mobile_layout=true login_401_then_200=true consent_gate=true two_contexts_isolated=true context_continuity=true xss_literal=true secret_not_persisted=true reset_and_logout=true no_auto_retry=true approval_gate=true insecure_http_blocked=true synthetic_model_only=true live_Gemini_calls=0')
    finally:
        server.shutdown();server.server_close()
