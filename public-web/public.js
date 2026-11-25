'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let csrf = '', busy = false, composing = false, cardsLeft = 4;
  const positive=row=>row&&Number.isSafeInteger(row.known_available)&&row.known_available>0;
  // Haravan titles are long SEO strings; the card shows the part before the first comma.
  const shortTitle=t=>{const s=t.split(',')[0].trim();return s.length>90?s.slice(0,88).trimEnd()+'…':s;};
  // Context from the widget on merlyshoes.com: model being viewed + how the chat was opened.
  const ctx=(()=>{const p=new URLSearchParams(location.hash.slice(1));const m=p.get('m')||'',s=p.get('s')||'';return {model:/^[0-9A-Za-z][0-9A-Za-z._-]{1,30}$/.test(m)?m:'',source:s==='button'||s==='teaser'?s:''};})();
  // The parent store page announces itself; only the shop's own origins may receive cart requests.
  const PARENTS=['https://merlyshoes.com','https://www.merlyshoes.com'].concat(location.hostname==='127.0.0.1'?['http://127.0.0.1:8766']:[]);
  let parentOrigin='';const pending=new Map();
  window.addEventListener('message',e=>{
    if(window.parent===window||e.source!==window.parent||!PARENTS.includes(e.origin))return;
    const d=e.data;if(!d||typeof d!=='object')return;
    if(d.type==='merly:hello'){parentOrigin=e.origin;for(const b of document.querySelectorAll('button.cart[hidden]'))b.hidden=false;}
    else if(d.type==='merly:cart-result'&&pending.has(d.rid)){pending.get(d.rid)(d);pending.delete(d.rid);}
  });
  function event(name){if(!csrf)return;fetch('/api/public/event',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Merly-CSRF':csrf},body:JSON.stringify({event:name})}).catch(()=>{});}
  function toParent(msg){if(parentOrigin)window.parent.postMessage(msg,parentOrigin);}
  function cartButton(card,row){
    if(row.available!==true||!Number.isSafeInteger(row.variant_id)||row.variant_id<=0)return;
    const b=document.createElement('button');b.type='button';b.className='cart';b.textContent='Thêm vào giỏ';b.hidden=!parentOrigin;
    b.addEventListener('click',()=>{
      if(!parentOrigin||b.disabled)return;
      b.disabled=true;b.textContent='Đang thêm…';
      const rid=Math.random().toString(36).slice(2);
      const done=result=>{
        clearTimeout(timer);
        if(result&&result.ok){
          event('add_to_cart');b.textContent='✓ Đã thêm vào giỏ';b.classList.add('added');
          const pay=document.createElement('button');pay.type='button';pay.className='checkout';pay.textContent='Thanh toán ngay';
          pay.addEventListener('click',()=>{event('checkout');toParent({type:'merly:go',to:'checkout'});});
          const view=document.createElement('button');view.type='button';view.className='view-cart';view.textContent='Xem giỏ hàng';
          view.addEventListener('click',()=>toParent({type:'merly:go',to:'cart'}));
          b.after(pay,view);
        }else{
          event('add_to_cart_failed');b.disabled=false;b.textContent='Thêm vào giỏ';
          const note=document.createElement('p');note.className='notice';note.textContent='Chưa thêm được vào giỏ, chị bấm "Xem và đặt hàng" giúp em nhé.';b.after(note);
        }
      };
      const timer=setTimeout(()=>{pending.delete(rid);done(null);},10000);
      pending.set(rid,done);toParent({type:'merly:add-to-cart',id:row.variant_id,quantity:1,rid});
    });
    card.append(b);
  }
  function sizeChips(){
    if(!ctx.model)return;
    const welcome=document.querySelector('.welcome p');if(welcome)welcome.textContent='Chị đang xem mẫu '+ctx.model+'. Chị mang size mấy ạ? Em kiểm tra còn hàng ngay.';
    const box=document.createElement('div');box.className='sizes';box.setAttribute('role','group');box.setAttribute('aria-label','Chọn size');
    for(let n=35;n<=43;n++){const b=document.createElement('button');b.type='button';b.textContent=String(n);
      b.addEventListener('click',()=>{if(busy||!csrf)return;event('size_chip');box.remove();$('message').value='mã '+ctx.model+' size '+n+' còn màu gì';controls();$('chat').requestSubmit();});box.append(b);}
    document.querySelector('.welcome').append(box);
  }
  function controls() { $('send').disabled = busy || !csrf || !$('message').value.trim(); }
  function turn(kind,text,links=[]) { const node=document.createElement('div');node.className='turn '+kind;if(kind==='assistant'&&window.MerlyLinks)window.MerlyLinks.append(node,text,links);else node.textContent=text;$('conversation').append(node); }
  function stock(report) {
    if (!report || typeof report!=='object') return;
    if (report.mode==='groups') { if(Array.isArray(report.groups))for(const group of report.groups)stock(group);return; }
    const discovery=report.mode==='discovery';
    if (!Array.isArray(report.variants)) return;
    const rows=report.variants.filter(positive).slice(0,cardsLeft);if(!rows.length)return;cardsLeft-=rows.length;
    const panel=document.createElement('section');panel.className='stock';
    const criteria=report.criteria||{};
    const title=document.createElement('strong');title.textContent=discovery?'Kết quả theo yêu cầu · size '+criteria.size+ (criteria.heel_cm!==undefined?' · gót '+criteria.heel_cm+'cm':'')+(criteria.color?' · '+criteria.color:''):(report.model_code?'Mẫu '+report.model_code:'Lượt tra sản phẩm')+(report.size?' · size '+report.size:'');panel.append(title);
    if(!report.complete){const notice=document.createElement('p');notice.className='notice';notice.textContent=report.mode==='unverified'?'Em chưa kiểm tra được tồn kho cho lựa chọn này.':'Em mới kiểm tra được một phần kho, có thể còn lựa chọn khác.';panel.append(notice);}
    for (const row of rows) {
      const card=document.createElement('div');card.className='option';
      if(window.MerlyMedia)window.MerlyMedia.append(card,row);
      if(typeof row.title==='string'){const product=document.createElement('p');product.textContent=shortTitle(row.title);product.title=row.title;card.append(product);}
      const name=document.createElement('strong');name.textContent=(row.color||'Màu đang cập nhật')+' · size '+row.size;card.append(name);
      const info=document.createElement('p');info.textContent=(Number.isSafeInteger(row.price_vnd)?row.price_vnd.toLocaleString('vi-VN')+'đ':'Giá đang cập nhật')+' · '+(row.available===true?'Còn hàng':row.available===false?'Hết hàng':'Chưa kiểm tra được tồn');card.append(info);
      for(const loc of row.locations||[])if(loc.available>0){const p=document.createElement('p');p.textContent=loc.name+': '+loc.available+' đôi';card.append(p);}
      cartButton(card,row);
      if(typeof row.product_url==='string' && /^https:\/\/merlyshoes\.com\/products\/[A-Za-z0-9_-]+$/.test(row.product_url)){const link=document.createElement('a');link.textContent='Xem và đặt hàng';link.href=row.product_url;link.target='_blank';link.rel='noopener noreferrer';card.append(link);}
      panel.append(card);
    }
    $('conversation').append(panel);
  }
  function failure(d,status) {
    d=d&&typeof d==='object'&&!Array.isArray(d)?d:{};
    const zalo=' Chị có thể nhắn Zalo Merly để nhân viên hỗ trợ: https://oa.zalo.me/2969822963244380594';
    const messages={daily_budget_limit:'Phần tư vấn đã hết lượt trong hôm nay ạ. Chị vẫn tra tồn nhanh được bằng cách gửi mã mẫu và size, ví dụ "mã 1676 size 38 còn màu gì".',ai_minute_limit:'Đang có nhiều khách hỏi cùng lúc nên em trả lời chậm một chút ạ. Chị đợi khoảng một phút rồi gửi lại giúp em nhé.',ai_capacity:'Đang có nhiều khách hỏi cùng lúc nên em trả lời chậm một chút ạ. Chị đợi khoảng một phút rồi gửi lại giúp em nhé.',turn_in_progress:'Em vẫn đang trả lời câu trước của chị, chị đợi em chút nhé.',stock_capacity:'Em đang tra tồn cho một lượt khác, chị đợi em vài giây rồi gửi lại nhé.',stock_rate_limit:'Đang có nhiều lượt tra tồn, chị đợi em khoảng một phút rồi gửi lại nhé.',visitor_rate_limit:'Chị gửi hơi nhanh, chị đợi em trả lời xong rồi nhắn tiếp nhé.',public_rate_limit:'Đang có nhiều khách hỏi cùng lúc, chị đợi em khoảng một phút rồi gửi lại nhé.'};
    const categories={timeout:'Em trả lời hơi lâu nên bị ngắt giữa chừng ạ. Chị đợi một chút rồi gửi lại giúp em nhé.'+zalo,response_incomplete:'Em đang gặp trục trặc nên chưa trả lời được câu này ạ. Chị thử lại sau ít phút nhé.'+zalo,configuration:'Trợ lý đang tạm bảo trì ạ.'+zalo,upstream_limit:'Đang có nhiều khách hỏi cùng lúc, chị đợi em khoảng một phút rồi gửi lại nhé.'};
    const local={session:'Phiên chat đã hết hạn, chị tải lại trang giúp em nhé.',origin:'Chị mở khung chat chính thức trên merlyshoes.com giúp em nhé.',invalid_message:'Tin nhắn cần có từ 1 đến 1000 ký tự ạ.'};
    let text=[messages[d.error],local[d.error],categories[d.error_category]].find(value=>typeof value==='string')||'Em đang gặp trục trặc nên chưa trả lời được ạ. Chị thử lại sau ít phút nhé.'+zalo;
    if(typeof d.diagnostic_id==='string'&&/^[0-9a-f]{16}$/.test(d.diagnostic_id))text+=' (Mã hỗ trợ: '+d.diagnostic_id+')';
    return text;
  }
  function publicError(text){const error=new Error(text);error.safeForPublic=true;return error;}
  function products(rows) { /* Catalog-only candidates are never customer listings. */ }
  function quotes(rows) {
    if(!Array.isArray(rows))return;
    for(const row of rows.filter(positive).slice(0,cardsLeft)){
      cardsLeft--;
      const card=document.createElement('section');card.className='stock quote';
      if(window.MerlyMedia)window.MerlyMedia.append(card,row);
      const title=document.createElement('strong');title.textContent=typeof row.title==='string'?shortTitle(row.title):'Mẫu em vừa tra';card.append(title);
      const p=document.createElement('p');p.textContent=(row.color||'Màu đang cập nhật')+' · size '+(row.size||'?')+' · '+(Number.isSafeInteger(row.price_vnd)?row.price_vnd.toLocaleString('vi-VN')+'đ':'Giá đang cập nhật');card.append(p);
      const status=document.createElement('p');status.textContent=row.available===true?'Còn hàng':row.available===false?'Không đủ số lượng chị cần':'Chưa kiểm tra được tồn';card.append(status);
      cartButton(card,row);
      if(typeof row.product_url==='string'&&/^https:\/\/merlyshoes\.com\/products\/[A-Za-z0-9_-]+$/.test(row.product_url)){const a=document.createElement('a');a.href=row.product_url;a.textContent='Xem và đặt hàng';a.target='_blank';a.rel='noopener noreferrer';card.append(a);}
      $('conversation').append(card);
    }
  }
  async function session() {
    if (!window.isSecureContext) { $('status').textContent='Cần kết nối HTTPS để sử dụng chat.';return; }
    try { const r=await fetch('/api/public/session',{credentials:'same-origin',cache:'no-store'});const d=await r.json();if(!r.ok||typeof d.csrf!=='string')throw new Error();csrf=d.csrf;if(ctx.source)event('open_'+ctx.source);sizeChips();$('status').textContent=d.ai_availability?.available===false?'Hiện em chỉ tra tồn nhanh được theo mã mẫu và size; phần tư vấn đang tạm giới hạn lượt.':'Merly sẵn sàng tư vấn ạ.'; }
    catch { $('status').textContent='Chưa kết nối được, chị tải lại trang giúp em nhé.'; }
    controls();
  }
  $('message').addEventListener('input',controls);
  $('message').addEventListener('compositionstart',()=>{composing=true;});
  $('message').addEventListener('compositionend',()=>{composing=false;controls();});
  $('message').addEventListener('keydown',event=>{
    if(event.key!=='Enter'||event.shiftKey||event.ctrlKey||event.altKey||event.metaKey||event.isComposing||composing||event.keyCode===229)return;
    event.preventDefault();
    if(!event.repeat&&!busy&&csrf&&$('message').value.trim())$('chat').requestSubmit();
  });
  $('chat').addEventListener('submit',async e=>{
    e.preventDefault();if(busy||composing||!csrf||!$('message').value.trim())return;
    const message=$('message').value;if(!message.trim()||message.length>1000)return;
    turn('user',message);$('message').value='';busy=true;controls();$('status').textContent='Merly đang trả lời, chị đợi em chút nhé…';
    const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),70000);
    try {const r=await fetch('/api/public/chat',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Merly-CSRF':csrf},body:JSON.stringify({message}),signal:abort.signal});let d;try{d=await r.json();}catch(_){throw publicError('Em đang gặp trục trặc nên chưa trả lời được ạ. Chị thử lại sau ít phút nhé.');}if(!r.ok)throw publicError(failure(d,r.status));if(!d||typeof d.reply!=='string'||!d.reply.trim())throw publicError('Em đang gặp trục trặc nên chưa trả lời được ạ. Chị thử lại sau ít phút nhé.');turn('assistant',d.reply,window.MerlyLinks?window.MerlyLinks.sources(d):[]);if(!d.needs_clarification&&(d.lookup_incomplete||d.answer_mode==='protocol_guard')&&typeof d.diagnostic_id==='string'&&/^[a-f0-9]{16}$/.test(d.diagnostic_id)){const note=document.createElement('small');note.className='diagnostic';note.textContent='Mã hỗ trợ: '+d.diagnostic_id;$('conversation').lastElementChild.append(document.createElement('br'),note);}cardsLeft=4;if(window.MerlyMedia)window.MerlyMedia.reset();stock(d.stock_options);products(d.products);quotes(d.quotes);if(d.listing?.has_more){const more=document.createElement('small');more.textContent='Em đang gửi '+d.listing.shown+' trong '+d.listing.verified_positive_skus+' lựa chọn còn hàng. Chị muốn xem thêm thì nhắn em nhé.';$('conversation').append(more);}$('status').textContent=d.needs_clarification?'Merly đang chờ chị trả lời.':d.lookup_incomplete?'Lượt tra chưa xong; chị không cần nhập lại yêu cầu.':'';}
    catch(err){$('status').textContent=err.name==='AbortError'?'Em trả lời hơi lâu nên bị ngắt giữa chừng ạ. Chị đợi một chút rồi gửi lại giúp em nhé.':err.safeForPublic?err.message:'Chưa gửi được tin nhắn, chị kiểm tra kết nối mạng rồi thử lại giúp em nhé.';}
    finally{clearTimeout(timer);busy=false;controls();}
  });
  session();
})();
