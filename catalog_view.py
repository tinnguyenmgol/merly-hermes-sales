"""Project actual catalog tool outputs to existing public cards, never model JSON."""
import json
from source_links import unpack
from stock_report import safe_url

def collect(calls,outputs,duplicates):
    rows=[];seen=set()
    for cid,call in calls.items():
        if cid in duplicates or cid not in outputs or call['name']!='mcp__merly__search_products':continue
        try:
            args=call.get('arguments',{})
            if isinstance(args,str):args=json.loads(args)
            if not isinstance(args,dict) or args.get('check_stock') is True:continue
            output=outputs[cid]
            if output.get('status') not in (None,'completed'):continue
            data=unpack(output.get('output'))
            if data.get('status') not in ('ok','partial_metadata'):continue
            products=data.get('products')
            if not isinstance(products,list):continue
            for p in products:
                if not isinstance(p,dict) or type(p.get('product_id')) is not int or not 0<p['product_id']<10**16 or p['product_id'] in seen:continue
                if not isinstance(p.get('title'),str) or len(p['title'])>500:continue
                url=safe_url(p.get('product_url'))
                variants=p.get('variants',[])
                if not isinstance(variants,list) or len(variants)>12:continue
                clean=[]
                for v in variants:
                    if not isinstance(v,dict) or type(v.get('variant_id')) is not int or not 0<v['variant_id']<10**16:continue
                    size=v.get('size');color=v.get('color')
                    if size is not None and (not isinstance(size,str) or len(size)>20):continue
                    if color is not None and (not isinstance(color,str) or len(color)>255):continue
                    clean.append({'variant_id':v['variant_id'],'size':size,'color':color})
                rows.append({'product_id':p['product_id'],'title':p['title'],'product_url':url,'variants':clean,'availability':'not_checked'})
                seen.add(p['product_id'])
                if len(rows)>=4:return rows
        except (ValueError,TypeError,KeyError):continue
    return rows
