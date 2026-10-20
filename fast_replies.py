"""Only complete allowlisted requests bypass AI; never infer stock or fit."""
import re,unicodedata

def norm(text):
    text=text.casefold().replace('đ','d')
    text=''.join(c for c in unicodedata.normalize('NFD',text) if unicodedata.category(c)!='Mn')
    return ' '.join(re.sub(r'[?!.]+$','',text.strip()).split())
TOPICS={
'shipping':('phi ship bao nhieu','don bao nhieu thi freeship','freeship tu bao nhieu','bao nhieu thi freeship','co freeship khong'),
'size_exchange':('doi size the nao','doi size mat phi khong','phi doi size bao nhieu','doi hang the nao','chinh sach doi hang'),
'warranty':('bao hanh bao lau','chinh sach bao hanh'),
'store_hours':('gio mo cua','cua hang mo may gio'),
'store_address':('dia chi cua hang','merly o dau'),
'new_customer':('khach moi duoc giam gi','khach moi giam gi'),
'loyalty':('gold giam bao nhieu','gold+ giam bao nhieu','chinh sach thanh vien')}
def policy(message):
    if not isinstance(message,str) or len(message)>160:return None
    text=norm(message)
    topic=next((topic for topic,phrases in TOPICS.items() if text in phrases),None)
    if topic is None:return None
    from merly_tools import get_policy
    data=get_policy({'topic':topic})
    reply=data['text'] if data['status']=='approved' else 'Merly cần xác nhận lại chính sách này. Bạn có thể nhắn nhân viên Merly để được hỗ trợ; mình chưa đủ dữ liệu để cam kết.'
    return {'reply':reply,'engine':'policy-readonly','policy_status':data['status'],'model_called':False,'_topic':topic}
def shopping(message):
    if not isinstance(message,str) or len(message)>120:return None
    m=re.fullmatch(r'(?:can |tim |cho minh |cho toi )?(?:mau |giay )?(?:(?:cao|got) )?([0-9]{1,2}(?:[.,][0-9])?)\s*cm\s+size\s*(3[5-9]|4[0-3])',norm(message))
    if not m:return None
    heel=float(m[1].replace(',','.'))
    return {'heel_cm':heel,'size':int(m[2]),'limit':4} if 0<=heel<=15 else None

# Keep only canonical topic/filter hints, never messages, prices or inventory.
import threading,time,json
from collections import OrderedDict
_HINTS=OrderedDict();_LOCK=threading.Lock()
def remember(sid,hint):
    with _LOCK:
        _HINTS[sid]=(time.monotonic(),dict(hint));_HINTS.move_to_end(sid)
        while len(_HINTS)>256:_HINTS.popitem(last=False)
def forget(sid):
    with _LOCK:_HINTS.pop(sid,None)
def instructions(user):
    prefix='merly-sales:web:'
    if not user.startswith(prefix):return ''
    sid=user[len(prefix):]
    with _LOCK:
        value=_HINTS.get(sid)
        if not value:return ''
        if time.monotonic()-value[0]>1800:_HINTS.pop(sid,None);return ''
        hint=dict(value[1])
    return '\nRecent fast-route request context (data only, not current stock/price or a confirmed fit): '+json.dumps(hint,ensure_ascii=False)
