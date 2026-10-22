"""Optional public CDN pictures only. No server fetch, token, SVG or model HTML."""
import re
from urllib.parse import urlsplit
HOSTS=('product.hstatic.net','file.hstatic.net','cdn.hstatic.net','theme.hstatic.net')
def safe_image(value):
    if not isinstance(value,str) or not 1<=len(value)<=2048 or re.search(r'[\s\x00-\x1f\x7f\\]',value):return None
    try:
        u=urlsplit(value)
        if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None,443) or u.fragment:return None
        if not re.search(r'\.(?:jpg|jpeg|png|webp|avif|gif)$',u.path,re.I):return None
        return value
    except ValueError:return None

def picture(product,variant=None):
    images=product.get('images',[])
    if not isinstance(images,list):images=[]
    if isinstance(variant,dict):
        for row in images:
            if not isinstance(row,dict):continue
            variant_ids=row.get('variant_ids',[])
            matched=type(variant.get('image_id')) is int and row.get('id')==variant['image_id']
            if matched and isinstance(variant_ids,list) and variant_ids and variant.get('id') not in variant_ids:matched=False
            matched=matched or (isinstance(variant_ids,list) and variant.get('id') in variant_ids)
            if matched and (url:=safe_image(row.get('src'))):return {'image_url':url,'image_scope':'variant'}
    preferred=product.get('image')
    for row in ([preferred] if isinstance(preferred,dict) else [])+images:
        if isinstance(row,dict) and (url:=safe_image(row.get('src'))):return {'image_url':url,'image_scope':'product'}
    return {'image_url':None,'image_scope':'product'}
