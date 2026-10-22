"""Actual Chromium/WSGI/tools; SCRIPTED provider/Haravan fixtures, no live stock.
Optional public-store photo bytes illustrate the UI only, never actual inventory.
"""
import os,json,tempfile,threading,urllib.request,urllib.error,copy,base64,sys
from pathlib import Path
from wsgiref.simple_server import make_server,WSGIRequestHandler
from playwright.sync_api import sync_playwright,expect
import sales_gateway as gateway,hermes_client as client,merly_tools as tools,mcp_server,collection_catalog
sys.path.insert(0,str(Path(__file__).parent/'tests'))
from test_stock_options import product
class Quiet(WSGIRequestHandler):
    def log_message(self,*a):pass
photo_meta=Path('/workspace/tmp/merly-public-image-url.json');photo_file=Path('/workspace/tmp/merly-public-product-photo.bin')
if photo_meta.exists() and photo_file.exists():
    meta=json.loads(photo_meta.read_text());image=meta['image_url'];title=meta['alt'];picture=photo_file.read_bytes();mime='image/jpeg'
else:
    image='https://product.hstatic.net/test-fixture.png';title='ẢNH KIỂM THỬ';mime='image/png'
    picture=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsQAAA7EAZUrDhsAAAANSURBVBhXYzh8+PB/AAffA0nNPuCLAAAAAElFTkSuQmCC')
p=product();p.update(title=title,product_type='Sandal cao gót',image={'src':image},images=[])
for v in p['variants']:v.update(option1='Hồng',option2='42')
source_calls=[]
def haravan(resource,params,timeout=12):
    source_calls.append((resource,dict(params)))
    if resource=='custom_collections':return {'custom_collections':[{'id':99,'title':'Nhóm kiểm thử','handle':'nhom-kiem-thu','published_at':'2026-01-01T00:00:00Z'}]}
    if resource=='smart_collections':return {'smart_collections':[]}
    if resource=='products':return {'products':[copy.deepcopy(p)]}
    if resource=='products/100':return {'product':copy.deepcopy(p)}
    if resource.endswith('/variants/count'):return {'count':len(p['variants'])}
    if resource.endswith('/variants'):return {'variants':copy.deepcopy(p['variants'])}
    raise tools.h.HaravanError('fixture_unknown_resource')
tools.h.get=haravan;tools.catalog.snapshot=lambda:[copy.deepcopy(p)];tools.catalog.status=lambda:{'ready':True,'age_seconds':1};tools.enrichment=lambda:{}
tools.h.inventory=lambda ids,locs:[{'variant_id':int(v),'loc_id':loc,'qty_available':1 if i==0 else 0} for v in ids.split(',') for i,loc in enumerate(tools.LOCATIONS)]
client.audit=lambda:True
turns=[]
def native(path,payload):
    assert path=='/responses';turns.append(payload)
    args={'query':'cao gót','size':42} if len(turns)==1 else {'collection':'Nhóm kiểm thử','size':42,'check_stock':True}
    operation='search_products'
    if len(turns)==3:operation='quote_variant';args={'product_id':100,'variant_id':100001}
    data,error=mcp_server.invoke(operation,args);assert not error
    output=[{'type':'function_call','name':'mcp__merly__'+operation,'call_id':'fixture','arguments':json.dumps(args)},{'type':'function_call_output','call_id':'fixture','output':json.dumps(data)}]
    if len(turns)==2:
        output.extend([{'type':'function_call','name':'mcp__merly__search_products','call_id':'missing','arguments':'{"model_code":"TEST-NOMATCH","size":42,"check_stock":true}'},{'type':'function_call_output','call_id':'missing','output':'{"status":"source_unavailable"}'}])
    output.append({'type':'message','role':'assistant','content':[{'type':'output_text','text':'GIAO DIỆN KIỂM THỬ: ảnh công khai, dữ liệu công cụ mô phỏng; không xác nhận giá/tồn thực tế.\n![bad](https://evil.invalid/a.jpg) <img src=x onerror=alert(1)>'}]})
    return {'id':'resp_image_'+str(len(turns)),'status':'completed','output':output}
client.request=native
with tempfile.TemporaryDirectory(prefix='catalog-image-ui-',dir='/workspace/tmp') as tmp:
    os.environ.update(MERLY_PUBLIC_CHAT_ENABLED='1',MERLY_PUBLIC_ORIGIN='https://chat.merlyshoes.com',PILOT_ACCESS_KEY='P'*40,PILOT_SESSION_SECRET='S'*40,HERMES_PILOT_STATE_DB=tmp+'/state.db',HERMES_SALES_API_BASE='https://offline.invalid/v1',HERMES_SALES_API_KEY='T'*40,HERMES_SALES_ISOLATION_APPROVED='1',HERMES_CUSTOMER_DATA_APPROVED='1',HERMES_MODEL_COST_APPROVED='1')
    server=make_server('127.0.0.1',0,gateway.application,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=['--disable-gpu','--no-zygote','--renderer-process-limit=1'])
            ctx=browser.new_context(viewport={'width':390,'height':844});errors=[];images=[];requests=[]
            def proxy(route):
                req=route.request;path=req.url.split('chat.merlyshoes.com',1)[1]
                headers={k:v for k,v in req.all_headers().items() if k not in ('host','content-length')}
                request=urllib.request.Request(base+path,data=req.post_data_buffer,headers=headers,method=req.method)
                try:r=urllib.request.urlopen(request,timeout=10)
                except urllib.error.HTTPError as e:r=e
                with r:route.fulfill(status=r.status,body=r.read(),headers=dict(r.headers))
            def img(route):
                images.append(route.request.all_headers());route.fulfill(status=200,body=picture,content_type=mime)
            ctx.route('https://chat.merlyshoes.com/**',proxy);ctx.route(image,img)
            ctx.route('https://merlyshoes.com/products/**',lambda r:r.fulfill(body='<h1>TEST PRODUCT PAGE</h1>',content_type='text/html'))
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
            page.goto('https://chat.merlyshoes.com/');expect(page.locator('#status')).to_contain_text('sẵn sàng')
            page.locator('#message').fill('Xem ảnh minh hoạ từ dữ liệu kiểm thử');page.locator('#message').press('Enter')
            expect(page.locator('.product-thumbnail')).to_have_count(1)
            thumb=page.locator('.product-thumbnail');thumb.scroll_into_view_if_needed()
            expect(thumb).to_have_js_property('complete',True);assert thumb.evaluate('e=>e.naturalWidth>0')
            assert thumb.bounding_box()['width']==72 and thumb.bounding_box()['height']==72
            expect(page.locator('.product-visual figcaption')).to_contain_text('chưa xác minh đúng màu')
            assert images and all('referer' not in h and 'authorization' not in h for h in images)
            assert page.locator('.assistant img,script:not([src])').count()==0
            for width in (320,390,1440):
                page.set_viewport_size({'width':width,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
                assert thumb.bounding_box()['width']==72
            page.set_viewport_size({'width':390,'height':844})
            preview=os.getenv('MERLY_DESIGN_PREVIEW_DIR')
            if preview:
                Path(preview).mkdir(parents=True,exist_ok=True);page.screenshot(path=str(Path(preview)/'small-product-image.png'),full_page=True)
            with page.expect_popup() as event:thumb.click()
            popup=event.value;popup.wait_for_load_state();assert popup.evaluate('window.opener===null');popup.close()
            page.locator('#message').fill('Tra nhóm kiểm thử và tồn theo điều kiện');page.locator('#message').press('Enter')
            expect(page.locator('.stock')).to_have_count(3)
            expect(page.locator('.product-thumbnail')).to_have_count(2)
            expect(page.locator('.stock').last).to_contain_text('Chưa xác minh được dữ liệu')
            assert page.locator('.stock').nth(1).locator('.option').count()==20
            assert page.locator('.stock').nth(1).locator('img').count()==1
            assert any(r=='products' and p.get('collection_id')==99 for r,p in source_calls)
            page.locator('#message').fill('Kiểm tra biến thể đã chọn');page.locator('#message').press('Enter')
            expect(page.locator('.quote')).to_have_count(1)
            expect(page.locator('.quote img')).to_have_count(1)
            assert 'LỊCH SỬ' in turns[-1]['conversation_history'][-1]['content']
            bad=['https://evil.invalid/a.jpg','data:image/svg+xml,abc','javascript:alert(1)','https://product.hstatic.net/a.svg','http://product.hstatic.net/a.jpg','https://product.hstatic.net:444/a.jpg']
            assert page.evaluate('(urls)=>urls.every(u=>window.MerlyMedia.safe(u)===null)',bad)
            page.evaluate('''()=>{const box=document.createElement('div');box.id='bounded-images';box.hidden=true;document.body.append(box);MerlyMedia.reset();for(let i=0;i<10;i++)MerlyMedia.append(box,{product_id:i+1000,image_url:document.querySelector('.product-thumbnail').getAttribute('src')});}''')
            assert page.locator('#bounded-images img').count()==4
            ctx.route('https://product.hstatic.net/failure.jpg',lambda r:r.abort())
            page.evaluate('''()=>{const box=document.createElement('div');box.id='failed-image';document.body.append(box);MerlyMedia.reset();MerlyMedia.append(box,{product_id:99999,image_url:'https://product.hstatic.net/failure.jpg'});}''')
            page.locator('#failed-image').scroll_into_view_if_needed();expect(page.locator('#failed-image')).to_contain_text('Chưa tải được ảnh mẫu')
            ctx.route('https://merlyshoes.com/',lambda r:r.fulfill(body='<meta name="viewport" content="width=device-width,initial-scale=1"><script src="https://chat.merlyshoes.com/embed.js" defer></script>',content_type='text/html'))
            framed=ctx.new_page();framed.goto('https://merlyshoes.com/')
            framed.locator('#merly-chat-widget button').click()
            frame=framed.frame_locator('#merly-chat-widget iframe')
            expect(frame.locator('#status')).to_contain_text('sẵn sàng')
            frame.locator('#message').fill('Xem ảnh trong khung nhúng kiểm thử');frame.locator('#message').press('Enter')
            expect(frame.locator('.product-thumbnail')).to_have_count(1)
            frame.locator('.product-thumbnail').scroll_into_view_if_needed()
            expect(frame.locator('.product-thumbnail')).to_have_js_property('complete',True)
            assert frame.locator('.product-thumbnail').evaluate('e=>e.naturalWidth>0')
            assert not any('evil.invalid' in url for url in requests)
            assert not errors,errors
            browser.close()
        print('PASS_CATALOG_IMAGES catalog_type=true collection_source_pipeline=true thumbnail72=true image_popup=true stock_dedup20=true empty_groups_visible=true quote_image=true iframe_thumbnail=true no_referrer=true unsafe_inert=true max4=true failure_fallback=true provider_scripted=true live_stock=false')
    finally:server.shutdown();server.server_close()
