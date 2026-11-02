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


# Typed tool token, NEVER a customer-message parser. One atomic decision avoids
# exact+missing-cm contradictions. Legacy numeric callers remain internal-compatible.
HEEL_SELECTION_PATTERN=r'^(?:unspecified|(?:[0-9]|1[0-4])(?:\.[0-9]+)?|15(?:\.0+)?)$'
def search_scope(data):
    out=dict(data)
    if 'heel_selection' not in out:return out
    value=out.pop('heel_selection')
    if 'heel_mode' in out or 'heel_cm' in out:raise ValueError('conflicting_heel_selection')
    if not isinstance(value,str) or len(value)>24 or not re.fullmatch(HEEL_SELECTION_PATTERN,value):raise ValueError('invalid_heel_selection')
    if value!='unspecified':
        number=float(value)
        out['heel_cm']=int(number) if number.is_integer() else number
    return out
