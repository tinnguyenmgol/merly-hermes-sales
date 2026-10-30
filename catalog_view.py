"""Project actual catalog tool outputs to existing public cards, never model JSON."""
import json
from source_links import unpack
from stock_report import safe_url
from media_urls import safe_image

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
            data=unpack(output.get('output'),call['name'])
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
                rows.append({'product_id':p['product_id'],'title':p['title'],'product_url':url,'image_url':safe_image(p.get('image_url')),'image_scope':'product','product_type':p.get('product_type') if isinstance(p.get('product_type'),str) and len(p['product_type'])<=255 else None,'variants':clean,'availability':'not_checked'})
                seen.add(p['product_id'])
                if len(rows)>=4:return rows
        except (ValueError,TypeError,KeyError):continue
    return rows

def quotes(calls,outputs,duplicates,started):
    """Quote thumbnails come from correlated tool outputs, not assistant prose."""
    from tool_evidence import usable
    rows=[]
    for cid,call in calls.items():
        if call['name']!='mcp__merly__quote_variant' or cid in duplicates or cid not in outputs or not usable(call,outputs[cid],started):continue
        try:
            data=unpack(outputs[cid].get('output'),call['name'])
            if data.get('status') not in ('ok','partial_inventory'):continue
            if not isinstance(data.get('title'),str) or len(data['title'])>500:continue
            row={k:data.get(k) for k in ('product_id','variant_id','title','size','color','price_vnd','quantity','subtotal_vnd','available','known_available','inventory_complete','locations','checked_at')}
            row.update(product_url=safe_url(data.get('product_url')),image_url=safe_image(data.get('image_url')),image_scope='variant' if data.get('image_scope')=='variant' else 'product')
            from math import isfinite
            spec=data.get('verified_specs',{})
            heel=spec.get('heel_cm') if isinstance(spec,dict) else None
            if type(heel) in (int,float) and isfinite(heel) and 0<=heel<=15:row['verified_specs']={'heel_cm':heel}
            rows.append(row)
            if len(rows)>=4:return rows
        except (TypeError,ValueError):continue
    return rows
