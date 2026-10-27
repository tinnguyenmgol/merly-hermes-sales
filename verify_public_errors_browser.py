"""Real Chromium/WSGI error path; injected failures, NO live model calls."""
import os,json,tempfile,threading,urllib.request,urllib.error
from wsgiref.simple_server import make_server,WSGIRequestHandler
from playwright.sync_api import sync_playwright,expect
import sales_gateway as gateway,hermes_client as client
class Quiet(WSGIRequestHandler):
    def log_message(self,*a):pass
calls=[]
def fake(message,*args):
    calls.append(message)
    if message=='tôi cần mua giày nữ':return {'reply':'Bạn đang tìm kiểu giày nào?','conversation_id':'resp_fixture'}
    raise client.HermesError({'43 đen':'turn_not_completed','TIMEOUT':'hermes_timeout','CONFIG':'hermes_http_401','LIMIT':'hermes_http_429'}.get(message,'PRIVATE_REASON_SENTINEL'))
client.chat=fake
with tempfile.TemporaryDirectory(prefix='public-errors-',dir='/workspace/tmp') as tmp:
    os.environ.update(MERLY_PUBLIC_CHAT_ENABLED='1',MERLY_PUBLIC_ORIGIN='https://chat.merlyshoes.com',PILOT_ACCESS_KEY='P'*40,PILOT_SESSION_SECRET='S'*40,HERMES_PILOT_STATE_DB=tmp+'/state.db',HERMES_SALES_API_BASE='https://offline.invalid/v1',HERMES_SALES_API_KEY='T'*40,HERMES_SALES_ISOLATION_APPROVED='1',HERMES_CUSTOMER_DATA_APPROVED='1',HERMES_MODEL_COST_APPROVED='1',MERLY_VISITOR_PER_MINUTE='100',MERLY_AI_PER_MINUTE='100',MERLY_AI_PER_DAY='1000')
    server=make_server('127.0.0.1',0,gateway.application,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-gpu','--no-zygote','--renderer-process-limit=1'])
            ctx=browser.new_context(viewport={'width':390,'height':844});errors=[]
            def proxy(route):
                req=route.request;path=req.url.split('chat.merlyshoes.com',1)[1]
                if path=='/api/public/chat':
                    message=json.loads(req.post_data)['message']
                    if message=='NON_JSON':route.fulfill(status=502,body='<html>PRIVATE_HTML_SENTINEL</html>',content_type='text/html');return
                    if message=='BAD_TRACE':route.fulfill(status=503,body=json.dumps({'error':'constructor','diagnostic_id':'<img src=x onerror=alert(1)>'}),content_type='application/json');return
                    if message=='NETWORK':route.abort();return
                headers={k:v for k,v in req.all_headers().items() if k not in ('host','content-length')}
                request=urllib.request.Request(base+path,data=req.post_data_buffer,headers=headers,method=req.method)
                try:r=urllib.request.urlopen(request,timeout=10)
                except urllib.error.HTTPError as e:r=e
                with r:route.fulfill(status=r.status,body=r.read(),headers=dict(r.headers))
            ctx.route('https://chat.merlyshoes.com/**',proxy)
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('https://chat.merlyshoes.com/');expect(page.locator('#status')).to_contain_text('sẵn sàng')
            def send(message):page.locator('#message').fill(message);page.locator('#message').press('Enter')
            send('tôi cần mua giày nữ');expect(page.locator('.assistant').last).to_have_text('Bạn đang tìm kiểu giày nào?')
            for message,expected in [('43 đen','không phải do bạn diễn đạt sai'),('TIMEOUT','hết thời gian chờ'),('CONFIG','lỗi cấu hình hoặc quyền kết nối'),('LIMIT','giới hạn lượt xử lý'),('UNKNOWN','Hệ thống chưa hoàn tất')]:
                with page.expect_response(lambda r:r.url.endswith('/api/public/chat')) as result:send(message)
                response=result.value;data=response.json()
                expect(page.locator('#status')).to_contain_text(expected)
                expect(page.locator('#status')).to_contain_text('HTTP 503')
                expect(page.locator('#status')).to_contain_text(data['diagnostic_id'])
                expect(page.locator('#message')).to_be_editable()
                before=len(calls);page.wait_for_timeout(150);assert len(calls)==before
                assert page.locator('.assistant').count()==1 # system errors are not AI dialogue
            assert calls==['tôi cần mua giày nữ','43 đen','TIMEOUT','CONFIG','LIMIT','UNKNOWN']
            send('NON_JSON');expect(page.locator('#status')).to_contain_text('phản hồi không hợp lệ (HTTP 502)')
            send('BAD_TRACE');expect(page.locator('#status')).to_contain_text('HTTP 503')
            assert 'Mã hỗ trợ:' not in page.locator('#status').inner_text()
            assert 'function ' not in page.locator('#status').inner_text()
            send('NETWORK');expect(page.locator('#status')).to_contain_text('Không nhận được phản hồi hoàn chỉnh')
            assert len(calls)==6 and page.locator('.assistant').count()==1
            assert page.locator('.turn img,.turn script').count()==0
            text=page.locator('body').inner_text()
            assert all(x not in text for x in ('PRIVATE_REASON_SENTINEL','PRIVATE_HTML_SENTINEL','P'*40,'T'*40))
            assert not errors,errors
            browser.close()
        print('PASS_PUBLIC_ERRORS actual_gateway=true screenshot_flow=true error_category=true matching_support_id=true http_status=true non_json_safe=true malformed_trace_hidden=true network_failure_safe=true no_auto_retry=true no_fake_ai_reply=true no_secrets=true provider_scripted=true live_model=false')
    finally:server.shutdown();server.server_close()
