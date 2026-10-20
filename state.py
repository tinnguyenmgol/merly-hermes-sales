"""Hermes-pilot-only persistent pseudonymous conversation mapping and request budget."""
import hashlib,hmac,os,secrets,sqlite3,time,math,threading
from functools import wraps
from http.cookies import SimpleCookie,CookieError
from pathlib import Path
from fast_limits import limit

_DB_LOCK=threading.RLock()
def serialized(fn):
    @wraps(fn)
    def run(*args,**kwargs):
        with _DB_LOCK:return fn(*args,**kwargs)
    return run

def database():
    p=Path(os.getenv('HERMES_PILOT_STATE_DB','/app/pilot-data/hermes-sessions.sqlite3'));p.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600);os.close(fd)
    db=sqlite3.connect(str(p),timeout=.3)
    db.execute('PRAGMA max_page_count=1024')
    db.executescript('CREATE TABLE IF NOT EXISTS sessions (sid TEXT PRIMARY KEY,cid TEXT,seen REAL);CREATE TABLE IF NOT EXISTS calls (ts REAL);CREATE TABLE IF NOT EXISTS rate_calls (bucket TEXT,ts REAL);CREATE INDEX IF NOT EXISTS rate_window ON rate_calls(bucket,ts);')
    return db

def identity(header):
    secret=os.getenv('PILOT_SESSION_SECRET','')
    if len(secret)<32:raise ValueError('session_secret_not_configured')
    c=SimpleCookie()
    try:c.load(header or '')
    except CookieError:pass
    raw=c.get('merly_hermes_pilot');token=raw.value if raw else ''
    if len(token)!=43 or any(ch not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for ch in token):token=secrets.token_urlsafe(32)
    sid=hmac.new(secret.encode(),token.encode(),hashlib.sha256).hexdigest()
    return token,sid

def _budget_block(db,now):
    count,oldest=db.execute('SELECT count(*),min(ts) FROM calls WHERE ts>=?',(now-86400,)).fetchone()
    if count>=limit('AI_PER_DAY'):return {'available':False,'reason':'daily_budget_limit','retry_after':max(1,math.ceil(oldest+86400-now))}
    count,oldest=db.execute('SELECT count(*),min(ts) FROM calls WHERE ts>?',(now-60,)).fetchone()
    if count>=limit('AI_PER_MINUTE'):return {'available':False,'reason':'ai_minute_limit','retry_after':max(1,math.ceil(oldest+60-now))}
    return {'available':True}

def availability():
    """Read-only public availability, no counters, identities or model calls."""
    path=Path(os.getenv('HERMES_PILOT_STATE_DB','/app/pilot-data/hermes-sessions.sqlite3'))
    if not path.exists():return {'available':True}
    try:
        db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.3)
        try:return _budget_block(db,time.time())
        finally:db.close()
    except sqlite3.Error:return {'available':None}

@serialized
def reserve_checked(sid):
    now=time.time();db=database()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM sessions WHERE seen<?',(now-1800,));db.execute('DELETE FROM calls WHERE ts<?',(now-86400,))
            status=_budget_block(db,now)
            if not status['available']:return status
            row=db.execute('SELECT cid FROM sessions WHERE sid=?',(sid,)).fetchone()
            db.execute('INSERT INTO sessions VALUES(?,?,?) ON CONFLICT(sid) DO UPDATE SET seen=excluded.seen',(sid,'',now))
            db.execute('INSERT INTO calls VALUES(?)',(now,))
            return {'available':True,'cid':row[0] if row else ''}
    finally:db.close()

def reserve(sid):
    status=reserve_checked(sid)
    return status['cid'] if status['available'] else None

@serialized
def save(sid,cid):
    db=database()
    try:
        with db:db.execute('UPDATE sessions SET cid=?,seen=? WHERE sid=?',(cid,time.time(),sid))
    finally:db.close()


@serialized
def clear(sid):
    db=database()
    try:
        with db:db.execute('DELETE FROM sessions WHERE sid=?',(sid,))
    finally:db.close()


@serialized
def touch(sid):
    db=database();now=time.time()
    try:
        with db:
            db.execute('DELETE FROM sessions WHERE seen<?',(now-1800,))
            row=db.execute('SELECT cid FROM sessions WHERE sid=?',(sid,)).fetchone()
            db.execute('INSERT INTO sessions VALUES(?,?,?) ON CONFLICT(sid) DO UPDATE SET seen=excluded.seen',(sid,'',now))
            return row[0] if row else ''
    finally:db.close()

@serialized
def resource(bucket):
    if bucket not in ('PUBLIC','STOCK'):raise ValueError('invalid_resource')
    db=database();now=time.time()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM rate_calls WHERE ts<=?',(now-60,))
            count,oldest=db.execute('SELECT count(*),min(ts) FROM rate_calls WHERE bucket=?',(bucket,)).fetchone()
            if count>=limit(bucket+'_PER_MINUTE'):return {'available':False,'retry_after':max(1,math.ceil(oldest+60-now))}
            db.execute('INSERT INTO rate_calls VALUES(?,?)',(bucket,now))
            return {'available':True}
    finally:db.close()
