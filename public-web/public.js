'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let csrf = '', busy = false;
  function controls() { $('send').disabled = busy || !csrf || !$('consent').checked; }
  function turn(kind,text) { const node=document.createElement('div');node.className='turn '+kind;node.textContent=text;$('conversation').append(node); }
  function stock(report) {
    if (!report || typeof report!=='object') return;
    if (report.mode==='groups') { for(const group of report.groups)stock(group);return; }
    if (!Array.isArray(report.variants) || !report.variants.length) return;
    const panel=document.createElement('section');panel.className='stock';
    const title=document.createElement('strong');title.textContent='Mẫu '+report.model_code+' · size '+report.size;panel.append(title);
    const notice=document.createElement('p');notice.textContent=report.complete ? 'Đã tra đủ trong phạm vi này; chưa giữ hàng.' : 'Dữ liệu chưa đầy đủ; chưa kiểm tra được không có nghĩa là hết hàng.';panel.append(notice);
    for (const row of report.variants) {
      const card=document.createElement('div');card.className='option';
      const name=document.createElement('strong');name.textContent=(row.color||'Màu cần xác minh')+' · size '+row.size;card.append(name);
      const info=document.createElement('p');info.textContent=(Number.isSafeInteger(row.price_vnd)?row.price_vnd.toLocaleString('vi-VN')+'đ':'Giá cần xác minh')+' · '+(row.available===true?'Còn hàng đã xác minh':row.available===false?'Tồn khả dụng đã tra: 0':'Chưa xác minh tồn');card.append(info);
      for(const loc of row.locations||[])if(loc.available>0){const p=document.createElement('p');p.textContent=loc.name+': '+loc.available+' đôi';card.append(p);}
      if(typeof row.product_url==='string' && /^https:\/\/merlyshoes\.com\/products\/[A-Za-z0-9_-]+$/.test(row.product_url)){const link=document.createElement('a');link.textContent='Xem sản phẩm';link.href=row.product_url;link.target='_blank';link.rel='noopener noreferrer';card.append(link);}
      panel.append(card);
    }
    $('conversation').append(panel);
  }
  async function session() {
    if (!window.isSecureContext) { $('status').textContent='Cần kết nối HTTPS để sử dụng chat.';return; }
    try { const r=await fetch('/api/public/session',{credentials:'same-origin',cache:'no-store'});const d=await r.json();if(!r.ok||typeof d.csrf!=='string')throw new Error();csrf=d.csrf;$('status').textContent='Merly sẵn sàng tư vấn.'; }
    catch { $('status').textContent='Chưa kết nối được. Vui lòng tải lại trang sau.'; }
    controls();
  }
  $('consent').addEventListener('change',controls);
  $('chat').addEventListener('submit',async e=>{
    e.preventDefault();if(busy||!csrf||!$('consent').checked)return;
    const message=$('message').value;if(!message.trim()||message.length>1000)return;
    turn('user',message);$('message').value='';busy=true;controls();$('status').textContent='Đang kiểm tra, vui lòng không gửi lại.';
    const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),70000);
    try {const r=await fetch('/api/public/chat',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Merly-CSRF':csrf},body:JSON.stringify({message,consent:true}),signal:abort.signal});const d=await r.json();if(!r.ok)throw new Error(d.error==='busy'?'Hệ thống đang bận. Vui lòng thử lại sau.':'Chưa xử lý được. Vui lòng không gửi lại liên tục.');if(typeof d.reply!=='string')throw new Error('Phản hồi chưa hợp lệ.');turn('assistant',d.reply);stock(d.stock_options);$('status').textContent='Đã nhận phản hồi từ Merly.';}
    catch(err){$('status').textContent=err.name==='AbortError'?'Hết thời gian chờ. Tác vụ có thể vẫn đang chạy; vui lòng không gửi lại liên tục.':err.message;}
    finally{clearTimeout(timer);busy=false;controls();}
  });
  session();
})();
