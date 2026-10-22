'use strict';
(() => {
  const hosts=new Set(['product.hstatic.net','file.hstatic.net','cdn.hstatic.net','theme.hstatic.net']);
  let shown=new Set();
  function safe(value) {
    if(typeof value!=='string'||value.length>2048||/[\s\x00-\x1f\x7f\\]/u.test(value))return null;
    try {const u=new URL(value);return u.protocol==='https:'&&hosts.has(u.hostname)&&!u.username&&!u.password&&(!u.port||u.port==='443')&&!u.hash&&/\.(?:jpe?g|png|webp|avif|gif)$/i.test(u.pathname)?value:null;}catch{return null;}
  }
  function append(parent,row) {
    const src=safe(row.image_url);if(!src)return;
    const key=row.product_id||row.product_url||src;
    if(shown.has(key)||shown.size>=4)return;shown.add(key);
    const figure=document.createElement('figure');figure.className='product-visual';
    const img=document.createElement('img');img.className='product-thumbnail';img.width=72;img.height=72;img.loading='lazy';img.decoding='async';img.referrerPolicy='no-referrer';
    img.alt=typeof row.title==='string'?row.title.slice(0,160):'Ảnh mẫu sản phẩm Merly';
    const caption=document.createElement('figcaption');caption.textContent=row.image_scope==='variant'?'Ảnh biến thể từ Haravan.':'Ảnh mẫu; chưa xác minh đúng màu đang chọn.';
    img.addEventListener('error',()=>{figure.replaceChildren(document.createTextNode('Chưa tải được ảnh mẫu.'));},{once:true});
    if(typeof row.product_url==='string'&&/^https:\/\/merlyshoes\.com\/products\/[A-Za-z0-9_-]+$/.test(row.product_url)){
      const link=document.createElement('a');link.href=row.product_url;link.target='_blank';link.rel='noopener noreferrer';link.append(img);figure.append(link);
    }else figure.append(img);
    figure.append(caption);parent.append(figure);img.src=src;
  }
  window.MerlyMedia=Object.freeze({append,reset:()=>{shown=new Set();},safe});
})();
