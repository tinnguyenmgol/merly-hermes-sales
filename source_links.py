"""Product links from actual read-only tool results, not model prose."""
import json
from stock_report import safe_url
TOOLS={'mcp__merly__search_products','mcp__merly__quote_variant'}
from tool_payload import unpack
def collect(items):
    calls={};duplicates=set();links=[]
    for item in items:
        if not isinstance(item,dict) or item.get('type')!='function_call':continue
        cid=item.get('call_id')
        if not isinstance(cid,str) or not cid:continue
        if cid in calls:duplicates.add(cid)
        calls[cid]=item.get('name')
    for item in items:
        if not isinstance(item,dict):continue
        cid=item.get('call_id')
        if not isinstance(cid,str) or not cid:continue
        if item.get('type')=='function_call_output' and calls.get(cid) in TOOLS and cid not in duplicates and item.get('status') in (None,'completed'):
            try:data=unpack(item.get('output'),calls.get(cid))
            except (TypeError,ValueError):continue
            if data.get('status') in ('invalid_arguments','source_unavailable','tool_unavailable'):continue
            report=data.get('stock_report',{})
            if not isinstance(report,dict):report={}
            rows=[data]
            for obj in (data,report):
                for key in ('products','variants'):
                    values=obj.get(key,[])
                    if isinstance(values,list):rows.extend(r for r in values if isinstance(r,dict))
            for row in rows:
                try:url=safe_url(row.get('product_url'))
                except (ValueError,TypeError):continue
                if url and url not in links:links.append(url)
                if len(links)>=32:return links
    return links
