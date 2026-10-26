"""Chromium + real gateway/decoder/history, SCRIPTED model, no live inference."""
import os,json,tempfile,threading,urllib.request,urllib.error
from wsgiref.simple_server import make_server,WSGIRequestHandler
from playwright.sync_api import sync_playwright,expect
import sales_gateway as gateway,hermes_client as client
class Quiet(WSGIRequestHandler):
    def log_message(self,*a):pass
seen=[]
client.audit=lambda:True

def model(path,payload):
    assert path=='/responses';seen.append(json.loads(json.dumps(payload)))
    message=payload['input'];status='partial';reply='Mình giữ các điều kiện bạn đã gửi.';question='Bạn muốn gợi ý nào?';options=['Gót 3cm','Gót 5cm'];tools=[]
    if message=='Gót 5cm':status='understood';reply='BROWSER_ACK';question='';options=[]
    elif message=='Không chọn hai gợi ý, tôi muốn cách khác':status='unclear';reply='Mình chưa hiểu rõ nhu cầu của bạn.';question='Bạn mô tả rõ hơn điều bạn cần được không?';options=[]
    elif message=='BROWSER_XSS':options=['<img src=x onerror="window.__choice_xss=1">','javascript:window.__choice_xss=1']
    else:
        tools=[{'type':'function_call','call_id':'fixture','name':'mcp__merly__get_policy','arguments':'{"topic":"store_hours"}'},{'type':'function_call_output','call_id':'fixture','output':'{"status":"source_unavailable"}'}]
    text=json.dumps(dict(understanding=status,reply=reply,question=question,options=options),ensure_ascii=False)
    return {'id':'resp_browser_'+str(len(seen)),'status':'completed','output':tools+[{'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}]}
client.request=model
with tempfile.TemporaryDirectory(prefix='dialogue-browser-',dir='/workspace/tmp') as tmp:
    os.environ.update(MERLY_PUBLIC_CHAT_ENABLED='1',MERLY_PUBLIC_ORIGIN='https://chat.merlyshoes.com',PILOT_ACCESS_KEY='P'*40,PILOT_SESSION_SECRET='S'*40,HERMES_PILOT_STATE_DB=tmp+'/state.db',HERMES_SALES_API_BASE='https://offline.invalid/v1',HERMES_SALES_API_KEY='T'*40,HERMES_SALES_ISOLATION_APPROVED='1',HERMES_CUSTOMER_DATA_APPROVED='1',HERMES_MODEL_COST_APPROVED='1',MERLY_DIALOGUE_CONTRACT_ENABLED='1')
    server=make_server('127.0.0.1',0,gateway.application,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-gpu','--no-zygote','--renderer-process-limit=1'])
            ctx=browser.new_context(viewport={'width':390,'height':844});errors=[];external=[]
            def proxy(route):
                req=route.request
                if not req.url.startswith('https://chat.merlyshoes.com/'):
                    external.append(req.url);route.abort();return
                path=req.url.split('chat.merlyshoes.com',1)[1]
                headers={k:v for k,v in req.all_headers().items() if k not in ('host','content-length')}
                request=urllib.request.Request(base+path,data=req.post_data_buffer,headers=headers,method=req.method)
                try:r=urllib.request.urlopen(request,timeout=15)
                except urllib.error.HTTPError as e:r=e
                with r:route.fulfill(status=r.status,body=r.read(),headers=dict(r.headers))
            ctx.route('**/*',proxy)
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('https://chat.merlyshoes.com/');expect(page.locator('#status')).to_contain_text('sẵn sàng')
            page.locator('#message').fill('BROWSER_FIRST_INPUT');page.locator('#message').press('Enter')
            expect(page.locator('.clarification-choice')).to_have_count(2)
            expect(page.locator('#status')).to_contain_text('chờ bạn xác nhận hoặc bổ sung')
            expect(page.locator('.assistant').last).to_contain_text('Bạn muốn gợi ý nào?')
            assert not page.locator('.stock,.quote,.product-card').count() and len(seen)==1
            expect(page.locator('#message')).to_be_editable()
            page.get_by_role('button',name='Gót 5cm',exact=True).click()
            expect(page.locator('.assistant').last).to_have_text('BROWSER_ACK')
            assert len(seen)==2 and seen[1]['input']=='Gót 5cm'
            assert 'choices_shown' in seen[1]['conversation_history'][-1]['content']
            assert [x['content'] for x in seen[1]['conversation_history'] if x['role']=='user']==['BROWSER_FIRST_INPUT']
            page.locator('#message').fill('Không chọn hai gợi ý, tôi muốn cách khác');page.locator('#message').press('Enter')
            expect(page.locator('.assistant').last).to_contain_text('Mình chưa hiểu rõ nhu cầu')
            expect(page.locator('.assistant').last).to_contain_text('Bạn mô tả rõ hơn')
            assert page.locator('.assistant').last.locator('button').count()==0
            assert len(seen)==3 and seen[2]['input']=='Không chọn hai gợi ý, tôi muốn cách khác'
            assert [x['content'] for x in seen[2]['conversation_history'] if x['role']=='user']==['BROWSER_FIRST_INPUT','Gót 5cm']
            page.locator('#message').fill('BROWSER_XSS');page.locator('#message').press('Enter')
            expect(page.locator('.assistant').last.locator('button')).to_have_count(2)
            assert page.locator('.assistant').last.locator('img,script,a').count()==0
            assert not page.evaluate('Boolean(window.__choice_xss)')
            assert len(seen)==4
            for width in (320,390,1440):
                page.set_viewport_size({'width':width,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            operator=ctx.new_page();operator.on('pageerror',lambda e:errors.append(str(e)))
            operator.goto('https://chat.merlyshoes.com/operator')
            operator.locator('#access-key').fill('P'*40);operator.locator('#login-button').click()
            expect(operator.locator('#status')).to_contain_text('Model chưa được thử')
            operator.locator('#test-consent').check()
            operator.locator('#message').fill('BROWSER_OPERATOR_INPUT');operator.locator('#send').click()
            expect(operator.locator('.clarification-choice')).to_have_count(2)
            assert len(seen)==5
            operator.locator('#test-consent').uncheck()
            expect(operator.locator('.clarification-choice').first).to_be_disabled()
            operator.locator('#test-consent').check()
            operator.get_by_role('button',name='Gót 5cm',exact=True).click()
            expect(operator.locator('.assistant').last).to_contain_text('BROWSER_ACK')
            assert len(seen)==6 and seen[-1]['input']=='Gót 5cm'
            assert seen[-1]['conversation_history'][0]['content']=='BROWSER_OPERATOR_INPUT'
            assert not external and not errors,(external,errors)
            browser.close()
        print('PASS_DIALOGUE_BROWSER actual_gateway=true operator_choices=true consent_gate=true operator_history_isolated=true final_json_decoded=true source_error_question_preserved=true choices2=true no_auto_selection=true click_posts_user_text=true free_text_allowed=true history_preserved=true unclear_asks_again=true no_listing_while_clarifying=true xss_inert=true responsive320_390_1440=true provider_scripted=true live_model=false')
    finally:server.shutdown();server.server_close()
