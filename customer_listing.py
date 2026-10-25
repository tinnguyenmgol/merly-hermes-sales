"""Customer display projection, after evidence validation. No inventory lookup/NLU."""
import copy
from catalog_query import norm
MAX_CARDS=4

def positive(row):
    return isinstance(row,dict) and all(type(row.get(k)) is int and 0<row[k]<10**16 for k in ('product_id','variant_id')) and type(row.get('known_available')) is int and row['known_available']>0

def positive_rows(report):
    if not isinstance(report,dict):return []
    if report.get('mode')=='groups':return [r for g in report.get('groups',[]) for r in positive_rows(g)]
    if report.get('mode') not in ('all_options','discovery'):return []
    expected=scopes(report)
    return [r for r in report.get('variants',[]) if positive(r) and (not expected or any(matches(r,s) for s in expected))]

def scopes(report):
    if not isinstance(report,dict):return []
    if report.get('mode')=='groups':return [s for g in report.get('groups',[]) for s in scopes(g)]
    data=dict(report.get('criteria',report))
    if 'color' not in data and data.get('color_filter'):data['color']=data['color_filter']
    return [{k:data[k] for k in ('size','color') if k in data}] if any(k in data for k in ('size','color')) else []

def matches(row,scope):
    return ('size' not in scope or str(scope['size'])==row.get('size')) and ('color' not in scope or norm(scope['color'])==norm(row.get('color')))

def project(answer):
    """Never mutate the complete report used by the evidence gate."""
    out=copy.deepcopy(answer);out.pop('products',None)
    expected=scopes(answer.get('stock_options'))
    eligible=positive_rows(answer.get('stock_options'))+[r for r in answer.get('quotes',[]) if positive(r) and (not expected or any(matches(r,s) for s in expected))]
    total=len({r.get('variant_id') for r in eligible});seen=set();shown=[]
    def take(rows):
        selected=[]
        for row in rows:
            vid=row.get('variant_id')
            if type(vid) is not int or vid in seen or len(shown)>=MAX_CARDS:continue
            seen.add(vid);shown.append(row);selected.append(row)
        return selected
    def report_view(report):
        if report.get('mode')=='groups':
            groups=[v for g in report.get('groups',[]) if (v:=report_view(g))]
            return {**report,'groups':groups,'view_mode':'verified_positive_subset'} if groups else None
        rows=take(positive_rows(report))
        if not rows:return None
        ids={r.get('product_id') for r in rows}
        return {**report,'variants':rows,'products':[p for p in report.get('products',[]) if p.get('product_id') in ids],'view_mode':'verified_positive_subset'}
    quotes=take([r for r in out.get('quotes',[]) if positive(r) and (not expected or any(matches(r,s) for s in expected))])
    if quotes:out['quotes']=quotes
    else:out.pop('quotes',None)
    report=report_view(out['stock_options']) if isinstance(out.get('stock_options'),dict) else None
    if report:out['stock_options']=report
    else:out.pop('stock_options',None)
    allowed={r.get('product_url') for r in shown}
    out['source_links']=[u for u in out.get('source_links',[]) if isinstance(u,str) and ('/products/' not in u or u in allowed)]
    if any(k in answer for k in ('stock_options','quotes','products')) and (answer.get('answer_mode')=='evidence_guard' or answer.get('engine')=='haravan-readonly'):
        out['reply']='Các lựa chọn bên dưới đã xác minh có tồn; chưa giữ hàng.' if shown else 'Chưa xác minh được mẫu có tồn đúng yêu cầu trong lượt này.'
    out['listing']={'mode':'verified_positive_only','shown':len(shown),'verified_positive_skus':total,'has_more':total>len(shown),'limit':MAX_CARDS}
    return out
