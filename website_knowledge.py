"""Curated website facts only; no runtime crawl, policy override, or phrase router."""
import json,re
from datetime import datetime
from pathlib import Path
TOPICS={'about_merly','measurement_help','membership_help','address_details','official_channels','shoe_care','payment_help','order_help','privacy_help','uniform_orders'}
PROFILE_LINKS={'https://www.facebook.com/merlyshoes','https://www.facebook.com/giaysizelon','https://www.tiktok.com/@merlyshoes','https://shopee.vn/merlyofficial','https://www.lazada.vn/shop/merly'}
ACCOUNT_LINKS={'https://merlyshoes.com/account/login','https://merlyshoes.com/account/register'}
class InvalidWebsiteKnowledge(ValueError):pass

def document_url(value):
    return isinstance(value,str) and bool(re.fullmatch(r'https://merlyshoes\.com/(?:pages/[a-z0-9_-]+|blogs/[a-z0-9_-]+/[a-z0-9_-]+)',value))

def timestamp(value):
    return isinstance(value,str) and datetime.fromisoformat(value).tzinfo is not None

def load(root):
    path=Path(root)/'vendor/knowledge-website-reference.json'
    if not path.exists():return None
    try:
        if path.is_symlink() or path.stat().st_size>65536:raise ValueError()
        d=json.loads(path.read_text())
        if not isinstance(d,dict) or d.get('approved') is not True or d.get('scope')!='customer_reference' or type(d.get('revision')) is not int or d['revision']<1 or not timestamp(d.get('retrieved_at')):raise ValueError()
        sources=d['sources'];items=d['items'];links=d['customer_links']
        if not isinstance(sources,dict) or not 1<=len(sources)<=20 or not isinstance(items,list) or not 1<=len(items)<=10 or not isinstance(links,list) or len(links)>32:raise ValueError()
        clean_sources={}
        for key,s in sources.items():
            if not isinstance(key,str) or not re.fullmatch(r'[a-z0-9_-]{1,180}',key) or not isinstance(s,dict) or not document_url(s.get('url')) or not timestamp(s.get('retrieved_at')) or not re.fullmatch(r'[a-f0-9]{64}',s.get('html_sha256','')):raise ValueError()
            excerpts=s.get('excerpts')
            if not isinstance(excerpts,list) or not 1<=len(excerpts)<=8 or any(not isinstance(x,str) or not 1<=len(x)<=400 for x in excerpts):raise ValueError()
            clean_sources[key]={k:s[k] for k in ('url','retrieved_at','html_sha256','excerpts')}
        seen=set();clean_items=[]
        for item in items:
            if not isinstance(item,dict) or item.get('topic') not in TOPICS or item['topic'] in seen or item.get('status')!='reference_only' or not isinstance(item.get('text'),str) or not 1<=len(item['text'])<=1200:raise ValueError()
            ids=item.get('source_ids')
            if not isinstance(ids,list) or not 1<=len(ids)<=3 or any(not isinstance(i,str) or i not in sources for i in ids):raise ValueError()
            seen.add(item['topic']);clean_items.append({k:item[k] for k in ('topic','status','text','source_ids')})
        allowed={s['url'] for s in clean_sources.values()}|PROFILE_LINKS|ACCOUNT_LINKS
        if any(not isinstance(u,str) or u not in allowed for u in links):raise ValueError()
        return {'status':'reference_only','scope':'customer_reference','revision':d['revision'],'retrieved_at':d['retrieved_at'],'sources':clean_sources,'items':clean_items,'customer_links':list(dict.fromkeys(links))}
    except (ValueError,TypeError,KeyError,OSError,AttributeError):raise InvalidWebsiteKnowledge('invalid_website_knowledge') from None
