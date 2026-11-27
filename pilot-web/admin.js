'use strict';
// Owner dashboard. All visitor text is rendered with textContent only.
(() => {
  const $ = id => document.getElementById(id);
  const STORE = 'merly-admin-key';
  let key = '', days = 7;
  try { key = localStorage.getItem(STORE) || ''; } catch { key = ''; }

  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
  const status = t => { $('status').textContent = t; };

  function bars(id, rows, opts = {}) {
    const box = $(id); box.replaceChildren();
    if (!rows || !rows.length) { box.append(el('p', 'empty', 'Chưa có dữ liệu')); return; }
    const max = Math.max(...rows.map(r => r[1]));
    for (const [label, count] of rows) {
      const row = el('div', 'bar' + (opts.warn ? ' warn' : ''));
      const track = el('div', 'track'); const fill = el('div', 'fill'); fill.style.width = (max ? Math.max(4, 100 * count / max) : 0) + '%'; track.append(fill);
      row.append(el('span', '', String(label)), track, el('b', '', String(count)));
      box.append(row);
    }
  }

  function kpis(d) {
    const pct = (a, b) => b ? Math.round(100 * a / b) + '%' : '—';
    const items = [
      [d.turns, 'lượt khách nhắn'], [d.visitors, 'khách (phiên chat)'],
      [pct(d.answered, d.turns), 'trả lời được'], [d.failed + d.limited, 'lượt không trả lời được'],
      [d.product_search_turns, 'lượt tìm/tra hàng'], [d.median_seconds == null ? '—' : d.median_seconds + 's', 'thời gian trả lời (trung vị)']
    ];
    $('kpis').replaceChildren(...items.map(([v, l]) => { const k = el('div', 'kpi'); k.append(el('b', '', String(v)), el('span', '', l)); return k; }));
  }

  function describe(c) {
    const parts = [];
    if (c.category) parts.push(c.category);
    if (c.model_code) parts.push('mã ' + c.model_code);
    if (c.size) parts.push('size ' + c.size);
    if (c.color) parts.push('màu ' + c.color);
    if (c.heel_cm != null) parts.push('gót ' + c.heel_cm + 'cm');
    if (c.occasion) parts.push(c.occasion);
    if (c.query) parts.push('"' + c.query + '"');
    return parts.join(' · ');
  }

  function unmet(rows) {
    const box = $('unmet'); box.replaceChildren();
    if (!rows.length) { box.append(el('p', 'empty', 'Chưa có — khách tìm gì cũng đã có hàng để giới thiệu.')); return; }
    const table = el('table'); const head = el('tr');
    for (const h of ['Khách tìm', 'Lượt', 'Kết quả']) head.append(el('th', '', h));
    table.append(head);
    for (const r of rows) {
      const tr = el('tr');
      tr.append(el('td', '', describe(r.criteria)), el('td', 'n', String(r.count)), el('td', '', Object.entries(r.outcomes).map(([k, v]) => k + ' ' + v).join(', ')));
      table.append(tr);
    }
    box.append(table);
  }

  function chats(id, sessions, conversations, reasons) {
    const box = $(id); box.replaceChildren();
    const list = (sessions || []).filter(s => conversations[s] && conversations[s].length);
    if (!list.length) { box.append(el('p', 'empty', 'Chưa có')); return; }
    for (const s of list) {
      const turns = conversations[s];
      const d = el('details'); const sum = el('summary');
      sum.append(document.createTextNode((turns[0].message || '').slice(0, 80) + ' '), el('small', '', '· ' + turns[0].day + ' · ' + turns.length + ' lượt · ' + s));
      d.append(sum);
      for (const t of turns) {
        const u = el('div', 'msg user'); u.append(el('i', '', 'Khách'), document.createTextNode(t.message || '')); d.append(u);
        if (t.status !== 'ok') { const e = el('div', 'msg err'); e.append(el('i', '', 'Không trả lời được'), document.createTextNode(reasons[t.reason] || t.reason || '')); d.append(e); }
        else { const b = el('div', 'msg bot'); b.append(el('i', '', 'Bot' + (t.shown ? ' · ' + t.shown + ' thẻ sản phẩm' : '')), document.createTextNode(t.reply || '')); d.append(b); }
      }
      box.append(d);
    }
  }

  async function load() {
    status('Đang tải…');
    let r;
    try { r = await fetch('/api/admin/insights?days=' + days + '&chats=10', { headers: { Authorization: 'Bearer ' + key }, cache: 'no-store' }); }
    catch { status('Không kết nối được, thử lại sau.'); return; }
    if (r.status === 401) { logout('Mã truy cập không đúng.'); return; }
    if (!r.ok) { status('Chưa tải được thống kê (mã ' + r.status + ').'); return; }
    const d = await r.json();
    $('login').hidden = true; $('dashboard').hidden = false;
    kpis(d);
    bars('per-day', d.per_day);
    bars('funnel', (d.funnel || []).filter(f => f.name !== 'add_to_cart_failed' || f.count).map(f => [f.label, f.visitors]));
    unmet(d.unmet_demand || []);
    bars('sizes', d.sizes); bars('colors', d.colors); bars('categories', d.categories); bars('heels', d.heels);
    bars('models', d.models); bars('outcomes', d.outcomes); bars('topics', d.policy_topics); bars('failures', d.failure_reasons, { warn: true }); bars('incomplete', d.incomplete_reasons, { warn: true });
    chats('review', d.review_sessions, d.conversations || {}, d.reasons || {});
    chats('recent', d.recent_sessions, d.conversations || {}, d.reasons || {});
    $('footer').textContent = (d.no_data ? 'Chưa có lượt chat nào được ghi. ' : '') + 'Số điện thoại, email và dãy số dài đã được che. Dữ liệu tự xoá sau ' + (d.retention_days || 30) + ' ngày.';
    status('Cập nhật lúc ' + new Date().toLocaleTimeString('vi-VN'));
  }

  function logout(message) {
    key = ''; try { localStorage.removeItem(STORE); } catch { /* storage unavailable */ }
    $('dashboard').hidden = true; $('login').hidden = false; $('key').value = '';
    status(''); if (message) alert(message);
  }

  $('login').addEventListener('submit', e => {
    e.preventDefault(); key = $('key').value.trim();
    if ($('remember').checked) { try { localStorage.setItem(STORE, key); } catch { /* storage unavailable */ } }
    load();
  });
  for (const b of document.querySelectorAll('[data-days]')) b.addEventListener('click', () => {
    days = Number(b.dataset.days); for (const o of document.querySelectorAll('[data-days]')) o.classList.toggle('on', o === b); load();
  });
  $('reload').addEventListener('click', load);
  $('logout').addEventListener('click', () => logout());
  if (key) load();
})();
