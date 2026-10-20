"""Runtime-configurable rates; paid AI budget unchanged by default."""
import os,threading
from contextlib import contextmanager
DEFAULTS={'AI_PER_MINUTE':6,'AI_PER_DAY':100,'PUBLIC_PER_MINUTE':120,'VISITOR_PER_MINUTE':12,'STOCK_PER_MINUTE':30,'AI_CONCURRENT':2,'STOCK_CONCURRENT':1}
def limit(name):
    raw=os.getenv('MERLY_'+name,str(DEFAULTS[name]))
    if not raw.isascii() or not raw.isdecimal() or not 1<=int(raw)<=10000:raise ValueError('invalid_rate_configuration')
    value=int(raw)
    if name.endswith('_CONCURRENT') and value>2:raise ValueError('concurrency_requires_capacity_review')
    return value
_GUARD=threading.Lock();_ACTIVE={};_SESSIONS={}
@contextmanager
def slot(kind):
    maximum=limit(kind+'_CONCURRENT')
    if limit('AI_CONCURRENT')+limit('STOCK_CONCURRENT')>3:raise ValueError('fast_worker_reservation_required')
    with _GUARD:
        ok=_ACTIVE.get(kind,0)<maximum
        if ok:_ACTIVE[kind]=_ACTIVE.get(kind,0)+1
    try:yield ok
    finally:
        if ok:
            with _GUARD:_ACTIVE[kind]-=1
@contextmanager
def session(sid):
    with _GUARD:
        ok=sid not in _SESSIONS
        if ok:_SESSIONS[sid]=True
    try:yield ok
    finally:
        if ok:
            with _GUARD:_SESSIONS.pop(sid,None)
