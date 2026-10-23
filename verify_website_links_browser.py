"""Real Chromium DOM only; no network, no model, no production calls."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import website_knowledge
ROOT=Path(__file__).parent
known=website_knowledge.load(ROOT)['customer_links']
good=['https://merlyshoes.com/pages/huong-dan-do-size-giay','https://merlyshoes.com/account/register','https://merlyshoes.com/account/login','https://merlyshoes.com/blogs/news/cap-nhat-dia-chi-moi-cua-he-thong-cua-hang-giay-merly-tai-tp-hcm','https://www.facebook.com/merlyshoes','https://shopee.vn/merlyofficial']
bad=['javascript:alert(1)','https://evil.invalid/','https://merlyshoes.com.evil.invalid/pages/lien-he','https://u:pass@merlyshoes.com/pages/lien-he','https://merlyshoes.com/pages/not-reviewed','https://merlyshoes.com/pages/chinh-sach-thanh-toan','https://www.facebook.com/merlyshoes?next=https://evil.invalid','https://shopee.vn/not-reviewed']
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,args=['--disable-gpu','--no-zygote','--renderer-process-limit=1'])
 context=browser.new_context();context.route('**/*',lambda r:r.fulfill(status=200,body='<h1>OFFLINE LINK FIXTURE</h1>',content_type='text/html'));page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content('<div id="answer"></div>');page.add_script_tag(content=(ROOT/'public-web/safe-links.js').read_text())
 text='\n'.join('[ok'+str(i)+']('+u+')' for i,u in enumerate(good))+'\n'+'\n'.join('[blocked'+str(i)+']('+u+')' for i,u in enumerate(bad))+'\n<img src=x onerror=alert(1)><script>alert(1)</script>'
 page.evaluate('([text,known])=>MerlyLinks.append(document.querySelector("#answer"),text,known)',[text,known])
 assert page.locator('#answer a').count()==len(good)
 assert page.locator('#answer a').evaluate_all('(a)=>a.map(x=>x.href)')==good
 assert page.locator('#answer a').evaluate_all('(a)=>a.every(x=>x.target==="_blank"&&x.rel==="noopener noreferrer")')
 assert page.locator('#answer img,#answer script').count()==0 and not errors
 with page.expect_popup() as event:page.locator('#answer a').first.click()
 popup=event.value;popup.wait_for_load_state();assert popup.url==good[0] and popup.evaluate('window.opener===null');popup.close()
 print('PASS_WEBSITE_LINKS_CHROMIUM safe_links='+str(len(good))+' blocked_cases='+str(len(bad))+' xss_blocked=true popup_click=true external_network_calls=0 model_calls=0')
 browser.close()
