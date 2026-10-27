'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let csrf = '', busy = false, composing = false, cardsLeft = 4;
  const positive=row=>row&&Number.isSafeInteger(row.known_available)&&row.known_available>0;
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
    const notice=document.createElement('p');notice.textContent=report.mode==='unverified'?'Chưa xác minh được dữ liệu cho phạm vi này; chưa thể kết luận còn hay hết hàng.':report.complete ? 'Đã tra đủ trong phạm vi này; chưa giữ hàng.' : 'Dữ liệu chưa đầy đủ; chưa kiểm tra được không có nghĩa là hết hàng.';panel.append(notice);
    for (const row of rows) {
      const card=document.createElement('div');card.className='option';
      if(window.MerlyMedia)window.MerlyMedia.append(card,row);
      if(typeof row.title==='string'){const product=document.createElement('p');product.textContent=row.title;card.append(product);}
      const name=document.createElement('strong');name.textContent=(row.color||'Màu cần xác minh')+' · size '+row.size;card.append(name);
      const info=document.createElement('p');info.textContent=(Number.isSafeInteger(row.price_vnd)?row.price_vnd.toLocaleString('vi-VN')+'đ':'Giá cần xác minh')+' · '+(row.available===true?'Còn hàng đã xác minh':row.available===false?'Tồn khả dụng đã tra: 0':'Chưa xác minh tồn');card.append(info);
      for(const loc of row.locations||[])if(loc.available>0){const p=document.createElement('p');p.textContent=loc.name+': '+loc.available+' đôi';card.append(p);}
      if(typeof row.product_url==='string' && /^https:\/\/merlyshoes\.com\/products\/[A-Za-z0-9_-]+$/.test(row.product_url)){const link=document.createElement('a');link.textContent='Xem sản phẩm';link.href=row.product_url;link.target='_blank';link.rel='noopener noreferrer';card.append(link);}
      panel.append(card);
    }
    $('conversation').append(panel);
  }
  function failure(d,status) {
    d=d&&typeof d==='object'&&!Array.isArray(d)?d:{};
    const messages={daily_budget_limit:'Phần tư vấn AI đã đạt hạn mức hiện tại. Bạn vẫn có thể tra tồn trực tiếp khi có mã mẫu và size.',ai_minute_limit:'Phần tư vấn AI đang giới hạn lượt. Bạn vẫn có thể tra tồn trực tiếp khi có mã mẫu và size.',ai_capacity:'Các lượt tư vấn AI đang được xử lý. Bạn vẫn có thể tra tồn trực tiếp khi có mã mẫu và size.',turn_in_progress:'Câu hỏi trước vẫn đang xử lý. Vui lòng chờ, không gửi lại.',stock_capacity:'Đang có lượt tra cứu hàng. Vui lòng chờ một chút rồi thử lại.',stock_rate_limit:'Tra cứu hàng đang tạm giới hạn lượt. Vui lòng thử lại sau.',visitor_rate_limit:'Bạn gửi tin nhắn hơi nhanh. Vui lòng chờ trước khi gửi tiếp.',public_rate_limit:'Có nhiều lượt gửi cùng lúc. Vui lòng thử lại sau.'};
    const categories={timeout:'Dịch vụ trợ lý đã hết thời gian chờ. Tác vụ có thể vẫn đang chạy; vui lòng không gửi lại liên tục.',response_incomplete:'Dịch vụ trợ lý chưa trả về câu trả lời hoàn chỉnh. Đây là lỗi xử lý, không phải do bạn diễn đạt sai.',configuration:'Dịch vụ trợ lý chưa sẵn sàng do lỗi cấu hình hoặc quyền kết nối. Merly cần kiểm tra hệ thống.',upstream_limit:'Dịch vụ trợ lý đang giới hạn lượt xử lý. Vui lòng không gửi lại liên tục.'};
    const local={session:'Phiên chat đã hết hạn hoặc không hợp lệ. Vui lòng tải lại khung chat.',origin:'Yêu cầu từ trang này chưa được chấp nhận. Vui lòng mở khung chat chính thức của Merly.',invalid_message:'Tin nhắn cần có từ 1 đến 1000 ký tự.'};
    let text=[messages[d.error],local[d.error],categories[d.error_category]].find(value=>typeof value==='string')||'Hệ thống chưa hoàn tất yêu cầu. Merly cần kiểm tra lỗi; vui lòng không gửi lại liên tục.';
    if(Number.isInteger(status)&&status>=400&&status<=599)text+=' (HTTP '+status+')';
    if(typeof d.diagnostic_id==='string'&&/^[0-9a-f]{16}$/.test(d.diagnostic_id))text+=' Mã hỗ trợ: '+d.diagnostic_id+'.';
    if(Number.isInteger(d.retry_after)&&d.retry_after>1&&d.retry_after<=60)text+=' Có thể thử sau khoảng '+d.retry_after+' giây.';
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
      const title=document.createElement('strong');title.textContent=row.title||'Mẫu đã tra';card.append(title);
      const p=document.createElement('p');p.textContent=(row.color||'Màu cần xác minh')+' · size '+(row.size||'cần xác minh')+' · '+(Number.isSafeInteger(row.price_vnd)?row.price_vnd.toLocaleString('vi-VN')+'đ':'Giá cần xác minh');card.append(p);
      const status=document.createElement('p');status.textContent=row.available===true?'Đã xác minh đủ số lượng yêu cầu; chưa giữ hàng.':row.available===false?'Chưa đủ số lượng yêu cầu theo tồn đã kiểm tra.':'Chưa xác minh đủ tồn.';card.append(status);
      if(typeof row.product_url==='string'&&/^https:\/\/merlyshoes\.com\/products\/[A-Za-z0-9_-]+$/.test(row.product_url)){const a=document.createElement('a');a.href=row.product_url;a.textContent='Xem sản phẩm';a.target='_blank';a.rel='noopener noreferrer';card.append(a);}
      $('conversation').append(card);
    }
  }
  async function session() {
    if (!window.isSecureContext) { $('status').textContent='Cần kết nối HTTPS để sử dụng chat.';return; }
    try { const r=await fetch('/api/public/session',{credentials:'same-origin',cache:'no-store'});const d=await r.json();if(!r.ok||typeof d.csrf!=='string')throw new Error();csrf=d.csrf;$('status').textContent=d.ai_availability?.available===false?'Merly sẵn sàng tra cứu nhanh; phần tư vấn AI đang tạm giới hạn lượt.':'Merly sẵn sàng tư vấn.'; }
    catch { $('status').textContent='Chưa kết nối được. Vui lòng tải lại trang sau.'; }
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
    turn('user',message);$('message').value='';busy=true;controls();$('status').textContent='Đang kiểm tra, vui lòng không gửi lại.';
    const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),70000);
    try {const r=await fetch('/api/public/chat',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Merly-CSRF':csrf},body:JSON.stringify({message}),signal:abort.signal});let d;try{d=await r.json();}catch(_){throw publicError('Máy chủ trả về phản hồi không hợp lệ (HTTP '+r.status+'). Vui lòng không gửi lại liên tục.');}if(!r.ok)throw publicError(failure(d,r.status));if(!d||typeof d.reply!=='string'||!d.reply.trim())throw publicError('Máy chủ chưa trả về nội dung hợp lệ (HTTP '+r.status+').');turn('assistant',d.reply,window.MerlyLinks?window.MerlyLinks.sources(d):[]);if((d.lookup_incomplete||d.answer_mode==='protocol_guard')&&typeof d.diagnostic_id==='string'&&/^[a-f0-9]{16}$/.test(d.diagnostic_id)){const note=document.createElement('small');note.className='diagnostic';note.textContent='Mã hỗ trợ: '+d.diagnostic_id;$('conversation').lastElementChild.append(document.createElement('br'),note);}cardsLeft=4;if(window.MerlyMedia)window.MerlyMedia.reset();stock(d.stock_options);products(d.products);quotes(d.quotes);if(d.listing?.has_more){const more=document.createElement('small');more.textContent='Đang hiển thị '+d.listing.shown+' / '+d.listing.verified_positive_skus+' SKU đã xác minh có tồn.';$('conversation').append(more);}$('status').textContent=d.needs_clarification?'Merly đang chờ bạn xác nhận hoặc bổ sung thông tin.':d.lookup_incomplete?'Lượt tra chưa hoàn tất; bạn không cần nhập lại yêu cầu.':'Đã nhận phản hồi từ Merly.';}
    catch(err){$('status').textContent=err.name==='AbortError'?'Hết thời gian chờ. Tác vụ có thể vẫn đang chạy; vui lòng không gửi lại liên tục.':err.safeForPublic?err.message:'Không nhận được phản hồi hoàn chỉnh từ hệ thống. Vui lòng kiểm tra kết nối; không gửi lại liên tục.';}
    finally{clearTimeout(timer);busy=false;controls();}
  });
  session();
})();
