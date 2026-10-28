"""Generic execution lifecycle checks. Validation rejection is not a source read."""
import json,time
from datetime import datetime
from source_links import unpack
from stock_report import tool_error_code,clarification_request

STATUSES={
 'mcp__merly__search_products':{'ok','partial_metadata'},
 'mcp__merly__quote_variant':{'ok','partial_inventory'},
 'mcp__merly__get_policy':{'approved'},
 'mcp__merly__size_guide':{'reference_only','needs_staff_review'},
 'mcp__merly__get_promotions':{'reference_only'}}

def usable(call,output,started):
    try:
        if output.get('status') not in (None,'completed'):return False
        args=call.get('arguments',{})
        if isinstance(args,str):args=json.loads(args)
        if not isinstance(args,dict):return False
        data=unpack(output.get('output'),call['name'])
        if not data:return False
        if call['name']=='mcp__merly__search_products' and (data.get('status')=='needs_clarification' or 'missing_fields' in data):return clarification_request(data,args)
        if isinstance(data.get('stock_report'),dict):return call['name']=='mcp__merly__search_products' and args.get('check_stock',True) is True
        name=call['name'];status=data.get('status')
        if status not in STATUSES[name]:return False
        if name=='mcp__merly__search_products' and status in ('ok','partial_metadata'):
            return isinstance(data.get('products'),list)
        if name=='mcp__merly__quote_variant' and status in ('ok','partial_inventory'):
            args=call.get('arguments',{})
            if isinstance(args,str):args=json.loads(args)
            for k in ('product_id','variant_id'):
                if type(args.get(k)) is not int or type(data.get(k)) is not int or data[k]!=args[k]:return False
            quantity=args.get('quantity',1)
            if type(quantity) is not int or not 1<=quantity<=20 or data.get('quantity')!=quantity:return False
            known=data.get('known_available');complete=data.get('inventory_complete')
            if type(known) is not int or known<0 or type(complete) is not bool:return False
            if data.get('available') is not (True if known>=quantity else False if complete else None):return False
            price=data.get('price_vnd');subtotal=data.get('subtotal_vnd')
            if price is not None and (type(price) is not int or not 0<=price<=9007199254740991):return False
            if subtotal!=(price*quantity if price is not None else None):return False
            locations=data.get('locations')
            if not isinstance(locations,list) or not 1<=len(locations)<=10:return False
            names=set();counts=[]
            for row in locations:
                if not isinstance(row,dict) or not isinstance(row.get('name'),str) or row['name'] in names:return False
                names.add(row['name']);q=row.get('available')
                if q is not None and (type(q) is not int or not 0<=q<=9007199254740991):return False
                counts.append(q)
            if sum(q for q in counts if q is not None)!=known or complete!=all(q is not None for q in counts):return False
            checked=datetime.fromisoformat(data['checked_at'].replace('Z','+00:00'))
            if checked.tzinfo is None or not started-3<=checked.timestamp()<=time.time()+3:return False
        if name=='mcp__merly__get_policy' and status=='approved':return isinstance(data.get('text'),str)
        if name=='mcp__merly__size_guide' and status=='reference_only':return isinstance(data.get('chart'),list)
        if name=='mcp__merly__get_promotions' and status=='reference_only':return isinstance(data.get('offers'),list)
        return True
    except (ValueError,TypeError,KeyError,AttributeError):return False

def repaired_rejections(calls,outputs,started):
    # Only skip pre-execution schema errors followed by a usable call of the
    # SAME fixed tool. Never hide source failures or coerce/repair identifiers.
    ids=list(calls);repaired=set()
    for i,cid in enumerate(ids):
        if tool_error_code(outputs.get(cid,{}).get('output'))!='tool_invalid_arguments':continue
        if any(calls[later]['name']==calls[cid]['name'] and usable(calls[later],outputs.get(later,{}),started) for later in ids[i+1:]):repaired.add(cid)
    return repaired
