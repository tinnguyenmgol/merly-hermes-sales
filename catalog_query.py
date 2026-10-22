"""Lexical catalog retrieval, not customer intent routing. All filters are ANDed."""
import re,unicodedata

def norm(value):
    text=str(value).casefold().replace('đ','d')
    return ' '.join(''.join(c for c in unicodedata.normalize('NFD',text) if unicodedata.category(c)!='Mn').split())
def words(value):return re.findall(r'[a-z0-9]+',norm(value)) if isinstance(value,str) else []
def phrase(source,query):
    a=words(source);b=words(query)
    for i in range(len(a)-len(b)+1):
        if b and a[i:i+len(b)]==b and not (i and a[i-1]=='khong') and not (i>1 and a[i-2:i]==['khong','phai']):return True
    return False

def name_matches(product,query):
    # Every requested name token must occur in source title/type, not in SKU.
    available=set(words(product.get('title',''))+words(product.get('product_type','')))
    return bool(words(query)) and set(words(query))<=available

def category_evidence(product,value,approved):
    for field in ('product_type','title'):
        if phrase(product.get(field,''),value):return {'field':field,'value':product.get(field,'')}
    if isinstance(approved.get('category'),str) and norm(approved['category'])==norm(value):return {'field':'approved_metadata','value':approved['category']}
    return None

def specs(product,approved,data,base):
    result=base(product,approved)
    if 'category' in data:
        evidence=category_evidence(product,data['category'],approved)
        if evidence:result['category']=data['category']
        else:result.pop('category',None)
    elif isinstance(product.get('product_type'),str) and 1<=len(product['product_type'].strip())<=60:
        result.setdefault('category',product['product_type'])
    return result
