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
    $('send').disabled = !access || !ready || busy || !$('test-consent').checked;
    $('message').disabled = !access || !ready || busy;
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
  $('chat-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !ready || !access || !$('test-consent').checked) return;
    const message = $('message').value;
    if (!message.trim() || message.length > 1000) { status(messages.invalid_message); return; }
    turn('user', message); $('message').value = ''; busy = true; controls(); status('Đang xử lý. Không gửi lại câu hỏi này.');
    try {
      const data = await api('/api/chat', 'POST', {message});
      if (typeof data.reply !== 'string' || !data.reply.trim()) throw new Error('Server không trả về nội dung hợp lệ.');
      turn('assistant', data.reply); status('Đã nhận phản hồi từ hệ thống.');
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
