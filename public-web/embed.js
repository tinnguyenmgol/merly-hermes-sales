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
      .launch{position:relative;width:48px;margin-left:auto}
      button{box-sizing:border-box;display:grid;place-items:center;width:48px;height:48px;padding:0;border:1px solid #fff3;border-radius:50%;background:#171717;color:#fff;cursor:pointer;box-shadow:0 3px 12px #0003;transition:background .15s,transform .15s;-webkit-tap-highlight-color:transparent}
      button:focus-visible{outline:2px solid #171717;outline-offset:3px}
      button svg{display:block;width:23px;height:23px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;pointer-events:none}
      .tip{position:absolute;right:58px;top:50%;transform:translateY(-50%);white-space:nowrap;padding:7px 10px;border-radius:7px;background:#fff;color:#171717;font-size:13px;line-height:1.4;box-shadow:0 2px 12px #0002;visibility:hidden;opacity:0;pointer-events:none}
      button:focus-visible+.tip{visibility:visible;opacity:1}
      @media(hover:hover){button:hover{background:#333;transform:translateY(-1px)}button:hover+.tip{visibility:visible;opacity:1}}
      @media(prefers-reduced-motion:reduce){button{transition:none}}
      section{box-sizing:border-box;width:min(380px,calc(100vw - 32px));height:min(640px,calc(100dvh - 104px - env(safe-area-inset-bottom,0px)));background:white;border:1px solid #e5e5e5;border-radius:14px;box-shadow:0 6px 28px #0002;margin-bottom:12px;overflow:hidden}
      section[hidden]{display:none}iframe{display:block;width:100%;height:100%;border:0;background:white}
    `;
    const panel=document.createElement('section');panel.id='panel';panel.hidden=true;
    const launch=document.createElement('div');launch.className='launch';
    const button=document.createElement('button');button.type='button';button.setAttribute('aria-label','Chat với Merly');button.setAttribute('aria-expanded','false');button.setAttribute('aria-controls','panel');
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');
    const path=document.createElementNS('http://www.w3.org/2000/svg','path');
    const chatIcon='M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z';
    path.setAttribute('d',chatIcon);svg.append(path);button.append(svg);
    const tip=document.createElement('span');tip.className='tip';tip.textContent='Chat với Merly';tip.setAttribute('aria-hidden','true');launch.append(button,tip);
    let frame=null;
    function toggle(open){
      if(open&&!frame){frame=document.createElement('iframe');frame.src='https://chat.merlyshoes.com/';frame.title='Tư vấn giày Merly';frame.referrerPolicy='no-referrer';frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox');panel.append(frame);}
      panel.hidden=!open;path.setAttribute('d',open?'M6 6l12 12M6 18 18 6':chatIcon);button.setAttribute('aria-label',open?'Đóng chat':'Chat với Merly');tip.textContent=open?'Đóng chat':'Chat với Merly';button.setAttribute('aria-expanded',String(open));
    }
    button.addEventListener('click',()=>toggle(panel.hidden));
    root.addEventListener('keydown',event=>{if(event.key==='Escape'){toggle(false);button.focus();}});
    root.append(style,panel,launch);document.body.append(host);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
