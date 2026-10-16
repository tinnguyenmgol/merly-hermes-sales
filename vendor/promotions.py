"""GET-only approved summaries, not a checkout eligibility engine."""
import argparse,json,re,threading,time
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
import catalog,haravan_client as h
LOCK=threading.Lock();CACHE={};TTL=60
CONFIG=Path(__file__).resolve().parent/'promotions-public.json'

def interested(message,state=None):
    if state and state.get('_dialog',{}).get('topic')=='promotions' and any(w in catalog.norm(message) for w in ('cong don','ap dung','het han','dieu kien','ma nao','ma nay','toi thieu')):return True
    return bool(re.search(r'\b(?:khuyen mai|uu dai|giam gia|ma giam|voucher|coupon|sale)\b',catalog.norm(message)))

def config():
    try:
        c=json.loads(CONFIG.read_text())
        if not isinstance(c,dict) or c.get('approved') is not True:return []
        pairs=[]
        for resource in ('promotions','discounts'):
            values=c.get(resource,[])
            if not isinstance(values,list):raise ValueError()
            for value in values:
                if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=9999999999999999:raise ValueError()
                if (resource,value) not in pairs:pairs.append((resource,value))
        if len(pairs)>3:raise ValueError()
        return pairs
    except (ValueError,OSError,TypeError):return []

def number(v):
    if isinstance(v,bool):raise ValueError()
    try:d=Decimal(str(v))
    except InvalidOperation:raise ValueError() from None
    if not d.is_finite() or d<0 or d>10**12:raise ValueError()
    return d

def date(v):
    if v is None:return None
    if not isinstance(v,str) or not v:raise ValueError()
    d=datetime.fromisoformat(v.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError()
    return d.astimezone(timezone.utc)

def summary(row,resource,identity,now):
    if not isinstance(row,dict) or type(row.get('id')) is not int or row['id']!=identity:raise ValueError()
    if row.get('status')!='enabled':return None
    start=date(row.get('starts_at'));end=date(row.get('ends_at'))
    if (start and now<start) or (end and now>=end):return None
    if row.get('set_time_active') is True and not start:raise ValueError()
    channels=row.get('entitled_channels')
    if row.get('channels_selection') not in (None,'all') and (not isinstance(channels,list) or 'web' not in channels):return None
    if row.get('channel') not in (None,'web'):return None
    if isinstance(channels,list) and channels and 'web' not in channels:return None
    if resource=='discounts' and row.get('usage_limit') is not None:
        cap=number(row['usage_limit']);used=number(row.get('times_used'))
        if cap>0 and used>=cap:return None
    kind=row.get('discount_type');value=number(row.get('value',0))
    if kind=='percentage':
        if not 0<value<=100:raise ValueError()
        benefit=f'Giảm {value.normalize():f}%'
    elif kind in ('fixed_amount','same_price'):
        if value!=value.to_integral_value():raise ValueError()
        benefit=('Giảm ' if kind=='fixed_amount' else 'Đồng giá ')+f'{int(value):,}'.replace(',','.')+'đ'
    elif kind=='shipping':benefit='Ưu đãi phí vận chuyển'
    else:raise ValueError()
    label=row.get('code' if resource=='discounts' else 'name')
    if not isinstance(label,str) or not label.strip() or len(label)>160 or re.search(r'[<>\x00-\x1f]',label):raise ValueError()
    notes=[]
    for field in ('minimum_order_amount','order_over'):
        if row.get(field) is not None and number(row[field]):
            amount=number(row[field]);notes.append('Ngưỡng giá trị đơn ghi nhận: '+f'{amount:,.0f}'.replace(',','.')+'đ; cần đối chiếu cách tính và điều kiện cụ thể')
    if row.get('applies_to_resource') or row.get('products_selection') not in (None,'all') or any(row.get(k) for k in ('entitled_product_ids','entitled_variant_ids','entitled_collection_ids','variants')):notes.append('Giới hạn sản phẩm/nhóm sản phẩm')
    if row.get('customers_selection') not in (None,'all') or any(row.get(k) for k in ('applies_customer_group_id','entitled_customer_ids','entitled_customer_segment_ids')):notes.append('Có điều kiện khách hàng')
    if row.get('provinces_selection') not in (None,'all') or row.get('entitled_province_ids'):notes.append('Có điều kiện khu vực')
    if row.get('locations_selection') not in (None,'all') or row.get('entitled_location_ids') or row.get('location_ids'):notes.append('Có điều kiện chi nhánh')
    if row.get('rule_customs') or row.get('applies_to_quantity') or row.get('promotion_apply_type'):notes.append('Có điều kiện bổ sung cần kiểm tra')
    if row.get('usage_limit'):notes.append('Có giới hạn lượt dùng; chưa cam kết còn lượt tại thanh toán')
    if end:notes.append('Mốc kết thúc theo Haravan: '+end.isoformat())
    return {'label':label.strip(),'benefit':benefit,'notes':notes}

def load(pairs):
    key=tuple(pairs);now=time.monotonic()
    # Non-blocking single flight: do not queue customer requests behind Haravan.
    if not LOCK.acquire(blocking=False):raise h.HaravanError('promotion_busy')
    try:
        if CACHE.get('key')==key and now-CACHE.get('ts',0)<TTL:
            if CACHE.get('error'):raise h.HaravanError('promotion_unavailable')
            return CACHE['rows']
        CACHE.clear();CACHE.update(key=key,ts=now,error=True)
        rows=[]
        for resource,identity in pairs:
            result=h.get(resource+'/'+str(identity),{})
            row=result.get('promotion' if resource=='promotions' else 'discount')
            if not isinstance(row,dict) or row.get('id')!=identity:raise h.HaravanError('invalid_promotion')
            rows.append((resource,identity,row))
        CACHE.update(ts=now,error=False,rows=rows)
        return rows
    finally:LOCK.release()

def respond(message,state):
    if not interested(message,state):return None
    state['_dialog']={'topic':'promotions'};state.pop('_pending_ai',None)
    pairs=config()
    if not pairs:return 'Em chưa có danh sách ưu đãi được duyệt công khai cho chat. Anh/chị nhắn Zalo OA để nhân viên kiểm tra chương trình phù hợp nhé; em chưa xác nhận shop không có khuyến mãi.'
    try:
        rows=load(pairs);now=datetime.now(timezone.utc);items=[]
        for resource,identity,row in rows:
            item=summary(row,resource,identity,now)
            if item:items.append(item)
    except (h.HaravanError,ValueError,TypeError,KeyError):
        return 'Em tạm chưa xác minh được ưu đãi từ Haravan. Anh/chị nhắn Zalo OA để kiểm tra nhé; em chưa xác nhận chương trình hay mã giảm giá áp dụng được.'
    if not items:return 'Trong danh sách đã được duyệt cho chat, em chưa xác minh được ưu đãi đang hiệu lực và có kênh website. Điều này không có nghĩa shop không có chương trình khác; anh/chị nhắn Zalo OA nhé.'
    lines=['Các ưu đãi đã duyệt công khai, để anh/chị tham khảo (dữ liệu cache tối đa 60 giây):']
    for item in items:
        line=item['label']+': '+item['benefit']+'.'
        if item['notes']:line+=' '+'; '.join(item['notes'])+'.'
        lines.append(line)
    lines.append('Em chưa xác nhận áp dụng cho mẫu/đơn của anh/chị, lượt dùng còn lại, cộng dồn hoặc giá sau ưu đãi. Cần đối chiếu sản phẩm, giỏ hàng và điều kiện tại thanh toán/nhân viên; không tự cộng các ưu đãi trên.')
    return '\n'.join(lines)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Operator-only GET permission probe; no coupon/name/customer fields are printed.')
    parser.add_argument('--probe',action='store_true');args=parser.parse_args()
    if not args.probe:parser.error('Use --probe in the app terminal; public IDs require separate approval.')
    failed=False
    for resource in ('promotions','discounts'):
        try:
            data=h.get(resource,{'limit':5,'page':1}).get(resource)
            if not isinstance(data,list):raise h.HaravanError('invalid_response')
            print(json.dumps({'resource':resource,'permission_probe':'ok','sampled_rows':len(data),'sample_ids':[r.get('id') for r in data if isinstance(r,dict)],'not_a_total':True}))
        except h.HaravanError as e:
            failed=True;print(json.dumps({'resource':resource,'permission_probe':'failed','error':str(e)}))
    raise SystemExit(1 if failed else 0)
