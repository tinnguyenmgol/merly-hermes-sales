"""Legacy slot helper for old regression tests; not imported or shipped in the chat runtime."""
import re,unicodedata

def norm(text):
    text=text.casefold().replace('đ','d')
    text=''.join(c for c in unicodedata.normalize('NFD',text) if unicodedata.category(c)!='Mn')
    return ' '.join(re.sub(r'[?!.]+$','',text.strip()).split())
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
