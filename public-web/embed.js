'use strict';
(() => {
  const id='merly-chat-widget';
  if(document.getElementById(id))return;
  function mount(){
    if(document.getElementById(id))return;
    const host=document.createElement('div');host.id=id;
    const root=host.attachShadow({mode:'open'});
    const style=document.createElement('style');
    style.textContent=':host{position:fixed;right:16px;bottom:16px;z-index:2147483000;font-family:system-ui,sans-serif}button{font:inherit;cursor:pointer;border:0;background:#764765;color:white;padding:12px 18px;border-radius:24px;box-shadow:0 3px 16px #0003}section{width:min(380px,calc(100vw - 32px));height:min(640px,calc(100dvh - 104px));background:white;border:1px solid #e7dce3;border-radius:12px;box-shadow:0 4px 22px #0003;margin-bottom:10px;overflow:hidden}section[hidden]{display:none}iframe{width:100%;height:100%;border:0;background:white}';
    const panel=document.createElement('section');panel.id='panel';panel.hidden=true;
    const button=document.createElement('button');button.type='button';button.textContent='Chat với Merly';button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls','panel');
    let frame=null;
    function toggle(open){
      if(open&&!frame){frame=document.createElement('iframe');frame.src='https://chat.merlyshoes.com/';frame.title='Tư vấn giày Merly';frame.referrerPolicy='no-referrer';frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox');panel.append(frame);}
      panel.hidden=!open;button.textContent=open?'Đóng chat':'Chat với Merly';button.setAttribute('aria-expanded',String(open));
    }
    button.addEventListener('click',()=>toggle(panel.hidden));
    root.addEventListener('keydown',event=>{if(event.key==='Escape'){toggle(false);button.focus();}});
    root.append(style,panel,button);document.body.append(host);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
