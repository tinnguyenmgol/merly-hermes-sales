'use strict';
(() => {
  const id='merly-chat-widget';
  if(document.getElementById(id))return;
  function mount(){
    if(document.getElementById(id))return;
    const host=document.createElement('div');host.id=id;
    const root=host.attachShadow({mode:'open'});
    const style=document.createElement('style');
    style.textContent=`
      :host{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom,0px));z-index:2147483000;font-family:system-ui,sans-serif}
      .launch{width:104px;margin-left:auto}
      button{box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;width:104px;height:64px;padding:6px 10px;border:1px solid #e6d9cf;border-radius:18px;background:#fffdfb;color:#57463b;cursor:pointer;box-shadow:0 4px 18px #4b30201c;-webkit-tap-highlight-color:transparent;transition:background .15s}
      button:focus-visible{outline:2px solid #9c8679;outline-offset:2px}
      button img{display:block;width:78px;height:31px;object-fit:contain;pointer-events:none}
      .caption{font:500 10px/1.3 system-ui,sans-serif;letter-spacing:.3px}
      @media(hover:hover){button:hover{background:#f7efe8}}
      @media(prefers-reduced-motion:reduce){button{transition:none}}
      section{box-sizing:border-box;width:min(380px,calc(100vw - 32px));height:min(640px,calc(100dvh - 120px - env(safe-area-inset-bottom,0px)));background:#fffdfb;border:1px solid #e6d9cf;border-radius:20px;box-shadow:0 8px 32px #4b302024;margin-bottom:12px;overflow:hidden}
      section[hidden]{display:none}iframe{display:block;width:100%;height:100%;border:0;background:#fffdfb}
    `;
    const panel=document.createElement('section');panel.id='panel';panel.hidden=true;
    const launch=document.createElement('div');launch.className='launch';
    const button=document.createElement('button');button.type='button';button.setAttribute('aria-label','Mở trợ lý Merly');button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls','panel');
    const logo=document.createElement('img');logo.src='https://chat.merlyshoes.com/merly-logo.png';logo.alt='';logo.width=78;logo.height=31;logo.referrerPolicy='no-referrer';
    const caption=document.createElement('span');caption.className='caption';caption.textContent='Trợ lý AI';
    button.append(logo,caption);launch.append(button);
    let frame=null;
    function toggle(open){
      if(open&&!frame){frame=document.createElement('iframe');frame.src='https://chat.merlyshoes.com/';frame.title='Tư vấn giày Merly';frame.referrerPolicy='no-referrer';frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox');panel.append(frame);}
      panel.hidden=!open;button.setAttribute('aria-label',open?'Đóng trợ lý Merly':'Mở trợ lý Merly');caption.textContent=open?'Đóng trò chuyện':'Trợ lý AI';button.setAttribute('aria-expanded',String(open));
    }
    button.addEventListener('click',()=>toggle(panel.hidden));
    root.addEventListener('keydown',event=>{if(event.key==='Escape'){toggle(false);button.focus();}});
    root.append(style,panel,launch);document.body.append(host);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
