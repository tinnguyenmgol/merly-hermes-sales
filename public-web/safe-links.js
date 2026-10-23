'use strict';
(() => {
  const staticLinks=new Set(['https://merlyshoes.com/','https://www.merlyshoes.com/','https://care.merlyshoes.com/','https://oa.zalo.me/2969822963244380594']);
  const reviewedProfiles=new Set(["https://www.facebook.com/merlyshoes", "https://www.facebook.com/giaysizelon", "https://www.tiktok.com/@merlyshoes", "https://shopee.vn/merlyofficial", "https://www.lazada.vn/shop/merly"]);
  function checked(raw,known){
    if(typeof raw!=='string'||/[\u0000-\u0020\u007f]/.test(raw)||raw.length>2000)return null;
    try{
      const u=new URL(raw);
      if(u.protocol!=='https:'||u.username||u.password||(u.port&&u.port!=='443'))return null;
      if(staticLinks.has(u.href))return raw;
      if(reviewedProfiles.has(u.href))return known.has(raw)?raw:null;
      const pathOK=/^\/(?:products|pages)\/[A-Za-z0-9_-]+$/.test(u.pathname)||/^\/blogs\/[a-z0-9_-]+\/[a-z0-9_-]+$/.test(u.pathname)||/^\/account\/(?:register|login)$/.test(u.pathname);
      if(u.hostname!=='merlyshoes.com'||u.search||u.hash||!pathOK)return null;
      return known.has(raw)?raw:null;
    }catch{return null;}
  }
  function append(root,text,urls=[]){
    const known=new Set(urls.filter(u=>typeof u==='string'));
    const tokens=/\[([^\]\n]{1,160})\]\(([^\s<>]{1,2000}?)\)|https?:\/\/[^\s<>"'\u0000-\u001f]{1,2000}/g;
    let start=0,m;
    while((m=tokens.exec(text))!==null){
      root.append(document.createTextNode(text.slice(start,m.index)));
      const markdown=m[1]!==undefined;
      let url=markdown?m[2]:m[0],tail='';
      if(!markdown){
        while(/[.,!?;:]$/.test(url)){tail=url.slice(-1)+tail;url=url.slice(0,-1);}
        while(url.endsWith(')')&&(url.match(/\)/g)||[]).length>(url.match(/\(/g)||[]).length){tail=')'+tail;url=url.slice(0,-1);}
      }
      const href=checked(url,known);
      if(href){const a=document.createElement('a');a.href=href;a.textContent=markdown?m[1]:url;a.target='_blank';a.rel='noopener noreferrer';root.append(a);if(tail)root.append(document.createTextNode(tail));}
      else root.append(document.createTextNode(m[0]));
      start=tokens.lastIndex;
    }
    root.append(document.createTextNode(text.slice(start)));
  }
  function sources(data){
    const urls=[];
    function report(r){if(!r||typeof r!=='object')return;if(r.mode==='groups'){for(const g of Array.isArray(r.groups)?r.groups:[])report(g);return;}for(const row of [...(Array.isArray(r.variants)?r.variants:[]),...(Array.isArray(r.products)?r.products:[])])if(typeof row.product_url==='string')urls.push(row.product_url);}
    report(data.stock_options);
    for(const row of Array.isArray(data.products)?data.products:[])if(typeof row.product_url==='string')urls.push(row.product_url);
    for(const u of Array.isArray(data.source_links)?data.source_links:[])if(typeof u==='string')urls.push(u);
    return [...new Set(urls)].slice(0,64);
  }
  window.MerlyLinks=Object.freeze({append,sources});
})();
