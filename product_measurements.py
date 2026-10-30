"""Parse source measurements; never route or infer customer intent."""
import re
from catalog_query import norm

def measurement_specs(product,approved):
    """Extract explicit heel measurement; caller supplies authority.
    Assistant prose can supply a CLAIM only, never source evidence."""
    meta=dict(approved)
    title=norm(product.get('title',''))
    values={float(m.replace(',','.')) for m in re.findall(r'(?<![a-z])(?:chieu cao got|cao got|got)(?:\s+(?:cao|vuong|nhon|tru))?\s*[:(]?\s*([0-9]{1,2}(?:[.,][0-9])?)\s*cm(?![a-z0-9_])',title)}
    # Source-title measurement, including names with words between heel and cm.
    # Never interpret SKU/foot dimensions or approximate bounds as exact heels.
    context=title+' '+norm(product.get('product_type',''))
    if re.search(r'\b(?:cao got|got nhon|got vuong|got tru)\b',context):
        measures=list(re.finditer(r'(?<![a-z0-9_.-])([0-9]{1,2}(?:[.,][0-9])?)\s*cm(?![a-z0-9_])',title))
        safe=[]
        for match in measures:
            before=title[max(0,match.start()-25):match.start()]
            if re.search(r'(?:chan|chieu dai|vong|ngang|sku|ma|khoang|tam|tu|den)\s*[:#]?\s*$|[<>~]\s*$',before):continue
            safe.append(float(match.group(1).replace(',','.')))
        if len(measures)==len(safe):values.update(safe)
    if any(not 0<=v<=15 for v in values):
        meta.pop('heel_cm',None);return meta
    if len(values)==1 and not re.search(r'\bkhong(?: (?:phai|co))? (?:cao )?got\b',title):
        value=next(iter(values))
        if 'heel_cm' not in meta:meta['heel_cm']=value
        elif meta['heel_cm']!=value:meta.pop('heel_cm',None)
    elif len(values)>1:meta.pop('heel_cm',None)
    return meta

