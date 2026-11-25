'use strict';
// Merly chat widget for merlyshoes.com (Haravan). Loaded from chat.merlyshoes.com.
// - Launcher states the benefit ("Hỏi size · còn hàng"), contrasts with dark banners.
// - Teaser bubble once per browser session, product-aware.
// - On product pages the chat opens on the model being viewed (size chips).
// - The chat iframe may ask THIS page to add a verified in-stock variant to the
//   visitor's own Haravan cart (/cart/add.js) or to go to cart/checkout. Messages
//   are accepted only from the chat origin and the widget's own iframe.
(() => {
  const id='merly-chat-widget';
  if(document.getElementById(id))return;
  const CHAT=(()=>{try{return new URL(document.currentScript.src).origin;}catch{return new URL('https://chat.merlyshoes.com/').origin;}})();
  const TEASER_KEY='merly-chat-teaser-seen',TEASER_DELAY=8000;
  function productModel(){
    if(!/^\/products\//.test(location.pathname))return '';
    const h1=document.querySelector('h1');const text=h1?h1.textContent:document.title;
    const m=/\bMerly\s+([0-9][0-9A-Za-z-]{1,19})/i.exec(text||'');
    return m?m[1].replace(/-+$/,''):'';
  }
  function mount(){
    if(document.getElementById(id))return;
    const host=document.createElement('div');host.id=id;
    const root=host.attachShadow({mode:'open'});
    const style=document.createElement('style');
    style.textContent=`
      :host{position:fixed;right:14px;bottom:calc(var(--merly-bottom,16px) + env(safe-area-inset-bottom,0px));z-index:2147483000;font-family:system-ui,-apple-system,sans-serif}
      .launch{display:flex;justify-content:flex-end}
      button.open{position:relative;display:flex;align-items:center;gap:9px;height:52px;padding:0 18px 0 8px;border:2px solid #8a5a3c;border-radius:999px;background:#fffaf4;color:#4a2e20;cursor:pointer;box-shadow:0 8px 26px rgba(40,22,14,.35);font:700 15px/1.1 system-ui,-apple-system,sans-serif;-webkit-tap-highlight-color:transparent;transition:transform .15s,box-shadow .15s}
      button.open:focus-visible{outline:3px solid #c98b5e;outline-offset:3px}
      .icon{position:relative;display:grid;place-items:center;width:38px;height:38px;border-radius:50%;background:#8a5a3c;flex:none}
      .icon svg{width:20px;height:20px}
      .dot{position:absolute;right:-1px;top:-1px;width:11px;height:11px;border-radius:50%;background:#2fb36b;border:2px solid #fffaf4}
      .label small{display:block;font:500 11.5px/1.2 system-ui,-apple-system,sans-serif;color:#8a6a55;margin-top:2px}
      .pulse{animation:pulse 1.6s ease-out 3}
      @keyframes pulse{0%{box-shadow:0 8px 26px rgba(40,22,14,.35),0 0 0 0 rgba(201,139,94,.65)}100%{box-shadow:0 8px 26px rgba(40,22,14,.35),0 0 0 16px rgba(201,139,94,0)}}
      @media(hover:hover){button.open:hover{transform:translateY(-2px);box-shadow:0 12px 30px rgba(40,22,14,.4)}}
      .teaser{position:relative;max-width:min(290px,calc(100vw - 40px));margin:0 0 10px auto;padding:13px 34px 13px 14px;background:#fff;color:#3b2a20;border:1px solid #e4d3c4;border-radius:16px 16px 4px 16px;box-shadow:0 10px 30px rgba(40,22,14,.25);font:500 14.5px/1.4 system-ui,-apple-system,sans-serif;cursor:pointer;animation:rise .35s ease-out}
      .teaser b{color:#8a5a3c}.teaser .logo{display:block;height:22px;width:auto;margin-bottom:6px}
      .teaser .x{position:absolute;right:6px;top:6px;width:26px;height:26px;border:0;border-radius:50%;background:transparent;color:#8a6a55;font:600 18px/1 system-ui;cursor:pointer}
      .teaser .cta{display:inline-block;margin-top:8px;padding:6px 12px;border-radius:999px;background:#8a5a3c;color:#fff;font-weight:700;font-size:13.5px}
      @keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
      @media(prefers-reduced-motion:reduce){.pulse,.teaser{animation:none}button.open{transition:none}}
      section{box-sizing:border-box;width:min(390px,calc(100vw - 28px));height:min(660px,calc(100dvh - var(--merly-bottom,16px) - 92px - env(safe-area-inset-bottom,0px)));background:#fffdfb;border:1px solid #e6d9cf;border-radius:20px;box-shadow:0 10px 36px rgba(75,48,32,.28);margin-bottom:12px;overflow:hidden}
      section[hidden],.teaser[hidden]{display:none}iframe{display:block;width:100%;height:100%;border:0;background:#fffdfb}
    `;
    const model=productModel();
    const panel=document.createElement('section');panel.id='panel';panel.hidden=true;
    const launch=document.createElement('div');launch.className='launch';
    const button=document.createElement('button');button.type='button';button.className='open pulse';
    button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls','panel');
    const icon=document.createElement('span');icon.className='icon';
    const NS='http://www.w3.org/2000/svg',svg=document.createElementNS(NS,'svg');
    for(const [k,v] of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'#fff','stroke-width':'2','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true'}))svg.setAttribute(k,v);
    for(const [d,w] of [['M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z','2'],['M8.5 11.5h.01M12 11.5h.01M15.5 11.5h.01','3']]){const p=document.createElementNS(NS,'path');p.setAttribute('d',d);p.setAttribute('stroke-width',w);svg.append(p);}
    const dot=document.createElement('span');dot.className='dot';icon.append(svg,dot);
    const label=document.createElement('span');label.className='label';
    function setLabel(open){
      label.replaceChildren(document.createTextNode(open?'Đóng trò chuyện':'Hỏi size · còn hàng'));
      if(!open){const s=document.createElement('small');s.textContent='Trợ lý Merly · trả lời ngay';label.append(s);}
      button.setAttribute('aria-label',open?'Đóng trợ lý Merly':'Mở trợ lý Merly: hỏi size và còn hàng');
    }
    setLabel(false);button.append(icon,label);
    const teaser=document.createElement('div');teaser.className='teaser';teaser.hidden=true;teaser.setAttribute('role','button');teaser.tabIndex=0;
    const logo=document.createElement('img');logo.className='logo';logo.src=CHAT+'/merly-logo.png';logo.alt='Merly';logo.width=58;logo.height=24;logo.referrerPolicy='no-referrer';
    const tText=document.createElement('div');
    if(model){tText.append('Chị mang size mấy ạ? Em kiểm tra ',Object.assign(document.createElement('b'),{textContent:'mẫu '+model}),' còn size của chị ngay.');}
    else{tText.append('Chị tìm giày ',Object.assign(document.createElement('b'),{textContent:'size 35–43'}),'? Em tư vấn size và báo còn hàng ngay ạ.');}
    const cta=document.createElement('span');cta.className='cta';cta.textContent=model?'Kiểm tra size của em':'Hỏi ngay';
    const close=document.createElement('button');close.type='button';close.className='x';close.setAttribute('aria-label','Ẩn lời chào');close.textContent='×';
    teaser.append(logo,tText,cta,close);
    launch.append(button);
    let frame=null;
    function seenTeaser(){try{sessionStorage.setItem(TEASER_KEY,'1');}catch{/* storage blocked */}}
    function toggle(open,source){
      if(open){teaser.hidden=true;seenTeaser();}
      if(open&&!frame){
        const params=new URLSearchParams();if(model)params.set('m',model);params.set('s',source||'button');
        frame=document.createElement('iframe');frame.src=CHAT+'/#'+params.toString();frame.title='Tư vấn giày Merly';frame.referrerPolicy='no-referrer';
        frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox');
        frame.addEventListener('load',()=>frame.contentWindow.postMessage({type:'merly:hello'},CHAT));
        panel.append(frame);
      }
      panel.hidden=!open;setLabel(open);button.setAttribute('aria-expanded',String(open));button.classList.remove('pulse');
    }
    button.addEventListener('click',()=>toggle(panel.hidden,'button'));
    teaser.addEventListener('click',e=>{if(e.target===close)return;toggle(true,'teaser');});
    teaser.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();toggle(true,'teaser');}});
    close.addEventListener('click',e=>{e.stopPropagation();teaser.hidden=true;seenTeaser();});
    root.addEventListener('keydown',event=>{if(event.key==='Escape'){teaser.hidden=true;toggle(false);button.focus();}});
    root.append(style,panel,teaser,launch);document.body.append(host);
    let shown=false;try{shown=sessionStorage.getItem(TEASER_KEY)==='1';}catch{shown=true;}
    if(!shown)setTimeout(()=>{if(panel.hidden)teaser.hidden=false;},TEASER_DELAY);

    // Requests from the chat iframe. Only our own frame and origin; fixed actions only.
    function reply(msg){if(frame)frame.contentWindow.postMessage(msg,CHAT);}
    function refreshCartCount(count){
      for(const n of document.querySelectorAll('a[href="/cart"] span, .count-holder, .cart-count, [data-cart-count]')){if(/^\s*\d+\s*$/.test(n.textContent))n.textContent=String(count);}
    }
    window.addEventListener('message',async event=>{
      if(event.origin!==CHAT||!frame||event.source!==frame.contentWindow)return;
      const d=event.data;if(!d||typeof d!=='object')return;
      if(d.type==='merly:add-to-cart'){
        const rid=typeof d.rid==='string'?d.rid.slice(0,40):'';
        if(!Number.isSafeInteger(d.id)||d.id<=0||!Number.isSafeInteger(d.quantity)||d.quantity<1||d.quantity>5){reply({type:'merly:cart-result',rid,ok:false});return;}
        try{
          const r=await fetch('/cart/add.js',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest'},body:'id='+d.id+'&quantity='+d.quantity});
          if(!r.ok)throw new Error('add');
          let count=null;try{const c=await (await fetch('/cart.js',{credentials:'same-origin',cache:'no-store'})).json();if(Number.isSafeInteger(c.item_count)){count=c.item_count;refreshCartCount(count);}}catch{/* count is optional */}
          reply({type:'merly:cart-result',rid,ok:true,item_count:count});
        }catch{reply({type:'merly:cart-result',rid,ok:false});}
      } else if(d.type==='merly:go'&&(d.to==='cart'||d.to==='checkout')){
        location.href=d.to==='cart'?'/cart':'/checkout';
      }
    });

    let layoutFrame=0;
    function layout(){
      layoutFrame=0;let bottom=16;const h=window.innerHeight,w=window.innerWidth;
      for(const other of document.querySelectorAll('.back-to-top,#back-to-top,#backToTop')){
        const css=getComputedStyle(other),r=other.getBoundingClientRect();
        if(css.display==='none'||css.visibility==='hidden'||Number(css.opacity)===0||r.width===0||r.height===0)continue;
        if(r.left<w-4&&r.right>w-220&&r.top<h-bottom+12&&r.bottom>h-bottom-64)bottom=Math.max(bottom,h-r.top+12);
      }
      host.style.setProperty('--merly-bottom',Math.min(bottom,Math.max(16,h-160))+'px');
    }
    function schedule(){if(!layoutFrame)layoutFrame=requestAnimationFrame(layout);}
    window.addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule,{passive:true});window.addEventListener('load',schedule,{once:true});
    document.addEventListener('transitionend',event=>{if(event.target.matches?.('.back-to-top,#back-to-top,#backToTop'))schedule();});schedule();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
