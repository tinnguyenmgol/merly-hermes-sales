"""Hermes-pilot-only persistent pseudonymous conversation mapping and request budget."""
import hashlib,hmac,os,secrets,sqlite3,time
from http.cookies import SimpleCookie,CookieError
from pathlib import Path

def database():
    p=Path(os.getenv('HERMES_PILOT_STATE_DB','/app/pilot-data/hermes-sessions.sqlite3'));p.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600);os.close(fd)
    db=sqlite3.connect(str(p),timeout=.3)
    db.execute('PRAGMA max_page_count=1024')
    db.executescript('CREATE TABLE IF NOT EXISTS sessions (sid TEXT PRIMARY KEY,cid TEXT,seen REAL);CREATE TABLE IF NOT EXISTS calls (ts REAL);')
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

def reserve(sid):
    now=time.time();db=database()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM sessions WHERE seen<?',(now-1800,));db.execute('DELETE FROM calls WHERE ts<?',(now-86400,))
            if db.execute('SELECT count(*) FROM calls WHERE ts>?',(now-60,)).fetchone()[0]>=6 or db.execute('SELECT count(*) FROM calls').fetchone()[0]>=100:return None
            row=db.execute('SELECT cid FROM sessions WHERE sid=?',(sid,)).fetchone()
            db.execute('INSERT INTO sessions VALUES(?,?,?) ON CONFLICT(sid) DO UPDATE SET seen=excluded.seen',(sid,'',now))
            db.execute('INSERT INTO calls VALUES(?)',(now,))
            return row[0] if row else ''
    finally:db.close()

def save(sid,cid):
    db=database()
    try:
        with db:db.execute('UPDATE sessions SET cid=?,seen=? WHERE sid=?',(cid,time.time(),sid))
    finally:db.close()
