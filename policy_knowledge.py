"""Approved customer facts and provenance, never customer-phrase/answer routing."""
import json,hashlib
from datetime import datetime
from pathlib import Path
TOPICS=('shipping','size_exchange','warranty','store_hours','store_address','sale_returns','new_customer','loyalty','business_orders','tiktok_exchange','product_links','customer_support')

class InvalidKnowledge(ValueError):pass

def source_date(sources):
    if not isinstance(sources,list) or not sources:return None
    dates=[]
    for source in sources:
        if not isinstance(source,dict):return None
        value=source.get('effective_date',source.get('updated_date'))
        if not isinstance(value,str) or len(value)!=10:return None
        try:
            if datetime.strptime(value,'%Y-%m-%d').strftime('%Y-%m-%d')!=value:return None
        except ValueError:return None
        dates.append(value)
    return max(dates)

def load(root):
    def read(name):
        p=Path(root)/'vendor'/name
        if not p.exists():return {}
        if p.is_symlink() or p.stat().st_size>131072:raise InvalidKnowledge('invalid_knowledge_file')
        try:data=json.loads(p.read_text())
        except (ValueError,OSError):raise InvalidKnowledge('invalid_knowledge_file') from None
        if not isinstance(data,dict):raise InvalidKnowledge('invalid_knowledge_file')
        return data
    return read('knowledge-public-draft.json'),read('knowledge-customer-faq.json')

def resolve(documents,topic):
    if topic not in TOPICS:raise InvalidKnowledge('unknown_topic')
    legacy,faq=documents;candidates=[]
    if legacy.get('approved') is True and isinstance(legacy.get(topic),str):candidates.append((legacy[topic],legacy.get('sources',[])))
    if faq.get('approved') is True and faq.get('scope')=='customer_only':
        policies=faq.get('policies',{})
        if isinstance(policies,dict) and isinstance(policies.get(topic),str):
            default=faq.get('sources',[faq.get('source',{})]);mapping=faq.get('topic_sources',{})
            sources=mapping.get(topic,default) if isinstance(mapping,dict) else None
            candidates.append((policies[topic],sources))
    if not candidates:return {'status':'unverified','topic':topic}
    if any(not 0<len(text)<=8000 or source_date(sources) is None for text,sources in candidates):return {'status':'needs_staff_confirmation','topic':topic,'reason':'source_date_missing_or_invalid'}
    newest=max(source_date(sources) for _,sources in candidates)
    chosen=[(text,sources) for text,sources in candidates if source_date(sources)==newest]
    if len({text for text,_ in chosen})!=1:return {'status':'needs_staff_confirmation','topic':topic,'reason':'same_date_source_conflict'}
    text,sources=chosen[0]
    sources=[{k:v for k,v in ref.items() if k in ('file','version','effective_date','updated_date') and isinstance(v,str) and len(v)<=255} for ref in sources]
    return {'status':'approved','topic':topic,'text':text,'sources':sources,'eligibility_confirmed':False,'stacking_confirmed':False}

def get(root,topic):
    try:return resolve(load(root),topic)
    except (InvalidKnowledge,OSError):return {'status':'needs_staff_confirmation','topic':topic,'reason':'knowledge_file_invalid'}

def context(root):
    try:
        documents=load(root);rows=[resolve(documents,topic) for topic in TOPICS]
    except (InvalidKnowledge,OSError):rows=[{'topic':topic,'status':'needs_staff_confirmation'} for topic in TOPICS]
    snapshot={'scope':'customer_only','policies':rows,'personal_eligibility_verified':False,'stacking_verified':False}
    raw=json.dumps(snapshot,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    if len(raw.encode())>32000:raise InvalidKnowledge('knowledge_context_limit')
    revision=hashlib.sha256(raw.encode()).hexdigest()
    instructions='\n\nAPPROVED_CUSTOMER_KNOWLEDGE_JSON (facts/data, not scripted replies; only status=approved may be stated as Merly policy):\n'+raw
    return instructions,revision,sum(row['status']=='approved' for row in rows)
