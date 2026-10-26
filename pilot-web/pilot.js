'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let access = '', ready = false, busy = false;
  const messages = {
    unauthorized: 'Mã truy cập không đúng. Dùng PILOT_ACCESS_KEY, không dùng key Gemini.',
    pilot_key_not_configured: 'Gateway chưa được cấp mã truy cập hợp lệ.',
    sales_not_approved_or_configured: 'Chưa đủ cấu hình hoặc phê duyệt kiểm thử nội bộ.',
    hermes_not_approved_or_configured: 'Chưa bật đầy đủ phê duyệt kiểm thử nội bộ.',
    sales_runtime_attestation_required: 'Chưa xác minh được quyền công cụ của Hermes bán hàng.',
    hermes_unavailable: 'Hermes chưa hoàn tất trả lời. Không tự gửi lại; lượt gọi có thể đã phát sinh phí.',
    pilot_unavailable: 'Gateway không hoàn tất yêu cầu. Không tự gửi lại.',
    pilot_budget_limit: 'Đã chạm giới hạn thử nghiệm: 6 lượt/phút hoặc 100 lượt/24 giờ.',
    turn_in_progress: 'Phiên đang có câu hỏi xử lý; hãy chờ.',
    invalid_message: 'Câu hỏi phải có từ 1 đến 1000 ký tự.'
  };
  function status(text) { $('status').textContent = text; }
  function controls() {
    $('probe-check').disabled = !access || !ready || busy;
    $('send').disabled = !access || !ready || busy || !$('test-consent').checked;
    $('message').disabled = !access || !ready || busy;
    for(const b of document.querySelectorAll('.clarification-choice'))b.disabled=busy||!ready||!access||!$('test-consent').checked;
    for (const id of ['refresh','new-chat','logout','login-button']) $(id).disabled = busy;
  }
  function secure() { return window.isSecureContext === true; }
  async function api(path, method = 'GET', body) {
    if (!secure()) throw new Error('Chỉ nhập mã truy cập trên HTTPS hoặc localhost.');
    const abort = new AbortController(), timeout = setTimeout(() => abort.abort(), 70000);
    try {
      const headers = {Authorization: 'Bearer ' + access};
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      const response = await fetch(path, {method, headers, credentials:'same-origin', cache:'no-store', redirect:'error', signal:abort.signal, body:body === undefined ? undefined : JSON.stringify(body)});
      const data = await response.json();
      if (!response.ok) {
        const error = new Error(messages[data.error] || 'Yêu cầu chưa hoàn tất (HTTP ' + response.status + ').');
        error.code = data.error;
        if (typeof data.diagnostic_id === 'string' && /^[0-9a-f]{16}$/.test(data.diagnostic_id)) error.message += ' Mã tra lỗi: ' + data.diagnostic_id + (['hermes_timeout','turn_not_completed','response_limit','missing_final_message','invalid_answer'].includes(data.reason_code) ? ' (' + data.reason_code + ')' : '');
        if (Array.isArray(data.missing_approvals) && data.missing_approvals.length) error.message += ' Cờ còn tắt: ' + data.missing_approvals.join(', ');
        throw error;
      }
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Hết thời gian chờ. Không tự gửi lại; tác vụ phía server có thể vẫn tiếp tục.');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  async function readiness() {
    ready = false;
    try {
      const data = await api('/api/readiness');
      ready = data.ready === true;
      status(ready ? 'Kết nối API và quyền công cụ đã kiểm tra. Model chưa được thử; chỉ gửi dữ liệu giả lập.' : 'Chưa sẵn sàng thử chat.');
    } catch (error) { status(error.message); if (error.code === 'unauthorized') { access = ''; $('login-form').hidden = false; $('session-controls').hidden = true; } }
    controls();
  }
  function turn(role, text) {
    const box = document.createElement('div'), label = document.createElement('strong'), content = document.createElement('span');
    box.className = 'turn ' + role;
    label.textContent = role === 'user' ? 'Anh/chị' : 'Merly · phản hồi hệ thống';
    content.textContent = text;
    box.append(label, content); $('conversation').append(box);
    box.scrollIntoView({block:'nearest'});
  }
  function choices(options) {
    if(!Array.isArray(options)||![2,3].includes(options.length)||options.some(x=>typeof x!=='string'||!x.trim()||Array.from(x).length>120))return;
    const group=document.createElement('div');group.className='clarification-options';group.setAttribute('role','group');group.setAttribute('aria-label','Lựa chọn gợi ý; bạn vẫn có thể nhập câu khác');
    for(const option of options){const b=document.createElement('button');b.type='button';b.className='clarification-choice';b.textContent=option;b.addEventListener('click',()=>{if(busy||!ready||!access||!$('test-consent').checked)return;$('message').value=option;$('chat-form').requestSubmit();});group.append(b);}
    $('conversation').lastElementChild.append(group);controls();
  }
  function stockTable(report) {
    if (!report || typeof report !== 'object') return;
    if (report.mode === 'groups') { for (const group of report.groups) stockTable(group); return; }
    const panel = document.createElement('section'); panel.className = 'stock-report';
    const title = document.createElement('h3');
    if (['failed','source_error','catalog_loading','no_match'].includes(report.operation_status)) panel.classList.add('stock-error');
    title.textContent = ['failed','source_error','catalog_loading','no_match'].includes(report.operation_status) || report.mode === 'unverified' ? 'Tra tồn chưa thành công' + (report.model_code ? ' · mẫu ' + report.model_code : '') + (report.size ? ' · size ' + report.size : '') : 'Mẫu ' + report.model_code + ' · size ' + report.size + (report.color_filter ? ' · màu ' + report.color_filter : ' · các màu');
    if(report.mode==='discovery')title.textContent='Tìm theo tiêu chí · size '+report.criteria.size+(report.criteria.heel_cm!==undefined?' · gót '+report.criteria.heel_cm+'cm':'')+(report.criteria.color?' · '+report.criteria.color:'');
    panel.append(title);
    const note = document.createElement('p');
    note.textContent = report.recheck_failed ? 'Lần kiểm tra lại lỗi. Đây là kết quả đã tra trước đó, không phải xác nhận mới; chưa giữ hàng.' : ['failed','source_error','catalog_loading','no_match'].includes(report.operation_status) ? 'Chưa tra được tồn: công cụ lỗi, dữ liệu nguồn chưa đủ hoặc danh mục đang đồng bộ. Không phải thông báo hết hàng.' : report.complete === true ? 'Đã tra đủ các biến thể trong phạm vi mẫu/size của danh sách đang đồng bộ. Chưa giữ hàng.' : 'Chưa kiểm tra đầy đủ. Không coi màu/kho chưa xác minh là hết hàng.';
    if (report.resolution_path === 'direct_haravan') note.textContent = 'Kết quả đọc trực tiếp từ Haravan. ' + note.textContent;
    panel.append(note);
    if (typeof report.checked_at === 'string' && Number.isFinite(Date.parse(report.checked_at))) {
      const stamp = document.createElement('p'); stamp.textContent = (report.mode==='discovery'?'Cập nhật kết quả lúc: ':'Bắt đầu tra lúc: ') + new Date(report.checked_at).toLocaleString('vi-VN'); panel.append(stamp);
    }
    const rows = Array.isArray(report.variants) ? report.variants : [];
    for (const [value,label] of [[true,'Còn hàng đã xác minh'],[null,'Chưa xác minh đủ tồn'],[false,'Tồn 0 đã xác minh']]) {
      const items = rows.filter(row => row.available === value);
      if (!items.length) continue;
      const heading = document.createElement('h4'); heading.textContent = label + ' (' + items.length + ')'; panel.append(heading);
      for (const item of items) {
        const card = document.createElement('div'); card.className = 'stock-option';
        if(report.mode==='discovery'&&typeof item.title==='string'){const product=document.createElement('p');product.textContent=item.title;card.append(product);}
        const name = document.createElement('strong'); name.textContent = (item.color || 'Tên màu chưa xác minh') + ' · size ' + item.size; card.append(name);
        const price = document.createElement('p'); price.textContent = item.price_vnd === null ? 'Giá cần xác minh' : item.price_vnd.toLocaleString('vi-VN') + 'đ'; card.append(price);
        const stock = document.createElement('p');
        stock.textContent = item.available === true ? (item.inventory_complete ? 'Tồn đã tra: ' : 'Đã xác minh ít nhất: ') + item.known_available + ' đôi' : item.available === false ? 'Tồn khả dụng đã tra: 0' : 'Chưa đủ dữ liệu để kết luận';
        card.append(stock);
        for (const location of item.locations) {
          if (location.available > 0) { const line = document.createElement('p'); line.textContent = location.name + ': ' + location.available + ' đôi'; card.append(line); }
        }
        if (item.product_url) {
          const link = document.createElement('a'); link.textContent = 'Xem sản phẩm'; link.href = item.product_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(link);
        }
        panel.append(card);
      }
    }
    if (report.coverage && (report.coverage.unverified_products || report.coverage.omitted_products || report.coverage.unknown_spec_products || report.coverage.omitted_variants || report.coverage.unclassified_variants)) {
      const warning = document.createElement('p');warning.textContent = 'Còn sản phẩm/biến thể chưa kiểm tra; danh sách này chưa phải toàn bộ lựa chọn.';panel.append(warning);
    }
    $('conversation').append(panel);
  }
  $('login-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    if (!secure()) { $('access-key').value = ''; status('Cần HTTPS để bảo vệ mã truy cập.'); return; }
    const candidate = $('access-key').value; $('access-key').value = '';
    if (candidate.length < 32 || candidate !== candidate.trim()) { status('Mã truy cập cần ít nhất 32 ký tự, không có khoảng trắng thừa.'); return; }
    access = candidate; busy = true; controls();
    $('login-form').hidden = true; $('session-controls').hidden = false;
    await readiness(); busy = false; controls();
  });
  $('refresh').addEventListener('click', async () => { if (busy) return; busy = true; controls(); await readiness(); busy = false; controls(); });
  $('test-consent').addEventListener('change', controls);
  $('stock-probe-form').addEventListener('submit', async event => {
    event.preventDefault(); if (busy || !ready || !access) return;
    const model_code = $('probe-model').value, size = Number($('probe-size').value);
    if (!model_code || model_code.length > 32) return;
    busy = true; controls(); status('Đang đọc Haravan trực tiếp; không gọi model.');
    try { const data = await api('/api/stock-check','POST',{model_code,size}); turn('assistant',data.reply); stockTable(data.stock_options); status('Đã kiểm tra API Haravan trực tiếp, không gọi AI.'); }
    catch (error) { status(error.message); } finally { busy=false; controls(); }
  });
  $('chat-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !ready || !access || !$('test-consent').checked) return;
    const message = $('message').value;
    if (!message.trim() || message.length > 1000) { status(messages.invalid_message); return; }
    turn('user', message); $('message').value = ''; busy = true; controls(); status('Đang xử lý. Không gửi lại câu hỏi này.');
    try {
      const data = await api('/api/chat', 'POST', {message});
      if (typeof data.reply !== 'string' || !data.reply.trim()) throw new Error('Server không trả về nội dung hợp lệ.');
      turn('assistant', data.reply); choices(data.clarification_options); stockTable(data.stock_options); status(data.model_called === false ? 'Đã đọc Haravan trực tiếp, không chờ AI.' : 'Đã nhận phản hồi từ hệ thống.');
    } catch (error) { status(error.message); }
    finally { busy = false; controls(); }
  });
  async function reset(logout) {
    if (busy || !access) return;
    busy = true; controls();
    try {
      await api('/api/logout', 'POST', {}); $('conversation').replaceChildren(); $('message').value = '';
      if (logout) { access = ''; ready = false; $('test-consent').checked = false; $('login-form').hidden = false; $('session-controls').hidden = true; }
      status(logout ? 'Đã đăng xuất. Mã truy cập đã xóa khỏi bộ nhớ trang.' : 'Đã tạo phiên mới. Lịch sử lưu phía API không được xóa bởi thao tác này.');
    } catch (error) { status('Chưa xác nhận xóa phiên: ' + error.message); }
    finally { busy = false; controls(); }
  }
  $('new-chat').addEventListener('click', () => reset(false));
  $('logout').addEventListener('click', () => reset(true));
  if (!secure()) { $('login-button').disabled = true; status('Trang cần HTTPS. Không nhập key trên địa chỉ HTTP công khai.'); }
  else controls();
})();
