"""Customer insights store: what visitors ask, what they search for, what is missing.

Owner-approved (2026-11-25): keep chat logs for analysis. Stored per turn:
- the visitor message and the reply that was actually shown, with phone numbers,
  e-mail addresses and long digit runs (card/account/ID numbers) masked;
- search criteria values (size, colour, style, heel, model code) and the
  inventory outcome, so unmet demand can be counted;
- which tools/policy topics were used and why a turn failed.
Sessions are a one-way hash of the pseudonymous gateway session, never a cookie,
IP, name or contact. Rows older than MERLY_INSIGHTS_RETENTION_DAYS are deleted.
Recording is best effort: it never changes or blocks the customer reply.
"""
import hashlib,json,logging,os,re,sqlite3,threading,time
from datetime import datetime,timedelta,timezone
from pathlib import Path

LOG=logging.getLogger('merly.insights')
VN=timezone(timedelta(hours=7))
CRITERIA=('model_code','size','color','category','heel_cm','occasion','query','collection')
_LOCK=threading.Lock()
_LAST_PURGE=[0.0]
_SCHEMA='''
CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY, ts REAL NOT NULL, day TEXT NOT NULL, session TEXT NOT NULL, turn INTEGER NOT NULL,
  channel TEXT NOT NULL, status TEXT NOT NULL, reason TEXT, engine TEXT, answer_mode TEXT, message TEXT, reply TEXT,
  tools TEXT, policy_topics TEXT, guard_reasons TEXT, needs_clarification INTEGER, lookup_incomplete INTEGER, shown INTEGER, elapsed_ms INTEGER);
CREATE INDEX IF NOT EXISTS turns_ts ON turns(ts);
CREATE INDEX IF NOT EXISTS turns_session ON turns(session,turn);
CREATE TABLE IF NOT EXISTS searches (turn_id INTEGER NOT NULL REFERENCES turns(id) ON DELETE CASCADE, ts REAL NOT NULL, day TEXT NOT NULL,
  model_code TEXT, size INTEGER, color TEXT, category TEXT, heel_cm REAL, occasion TEXT, query TEXT, collection TEXT,
  outcome TEXT, positive_skus INTEGER, positive_products INTEGER, complete INTEGER);
CREATE INDEX IF NOT EXISTS searches_ts ON searches(ts);
'''

def enabled():
    return os.getenv('MERLY_INSIGHTS_ENABLED','1')=='1'

def retention_days():
    raw=os.getenv('MERLY_INSIGHTS_RETENTION_DAYS','30')
    if not raw.isdecimal() or not 1<=int(raw)<=365:raise ValueError('invalid_insights_retention')
    return int(raw)

def path():
    explicit=os.getenv('MERLY_INSIGHTS_DB')
    if explicit:return Path(explicit)
    state=Path(os.getenv('HERMES_PILOT_STATE_DB','/app/pilot-data/hermes-sessions.sqlite3'))
    return state.with_name('insights.sqlite3')

def connect(readonly=False):
    p=path()
    if readonly:
        db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    else:
        p.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(str(p),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600);os.close(fd)
        db=sqlite3.connect(str(p),timeout=1)
        db.executescript(_SCHEMA)
    db.execute('PRAGMA foreign_keys=ON')
    return db

# Masking happens before anything is written. URLs are kept (product/Zalo links
# carry long IDs that are not personal); everything else that looks like a
# phone, e-mail or long number is replaced.
_URL=re.compile(r'https?://\S+')
_EMAIL=re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_PHONE=re.compile(r'(?<![\w/])(?:\+?84|0)(?:[\s.-]?\d){8,10}(?!\w)')
_LONG=re.compile(r'(?<![\w/])\d(?:[\s.-]?\d){8,}(?!\w)')

def redact(text):
    if not isinstance(text,str):return ''
    parts=[];last=0
    for m in _URL.finditer(text):
        parts.append(_mask(text[last:m.start()]));parts.append(m.group(0));last=m.end()
    parts.append(_mask(text[last:]))
    return ''.join(parts)[:4000]

def _mask(text):
    text=_EMAIL.sub('[email]',text)
    text=_PHONE.sub('[SĐT]',text)
    return _LONG.sub('[số]',text)

def _session(sid):
    return hashlib.sha256(('merly-insights:'+str(sid)).encode()).hexdigest()[:16]

def _clean(value,kind):
    if value is None:return None
    if kind is int:return value if type(value) is int and 0<value<100 else None
    if kind is float:return float(value) if type(value) in (int,float) and 0<=value<=30 else None
    return _mask(value.strip())[:80] if isinstance(value,str) and value.strip() else None

def searches(report):
    """Criteria values + outcome for each inventory lookup in a stock report."""
    if not isinstance(report,dict):return []
    if report.get('mode')=='groups':
        return [row for group in report.get('groups',[]) if isinstance(group,dict) for row in searches(group)][:8]
    mode=report.get('mode')
    if mode not in ('all_options','discovery','unverified'):return []
    criteria=report.get('criteria') if isinstance(report.get('criteria'),dict) else {}
    source={**criteria}
    for key in ('model_code','size'):
        if key in report and key not in source:source[key]=report[key]
    if report.get('color_filter') and 'color' not in source:source['color']=report['color_filter']
    rows=[r for r in report.get('variants',[]) if isinstance(r,dict)] if isinstance(report.get('variants'),list) else []
    positive=[r for r in rows if type(r.get('known_available')) is int and r['known_available']>0]
    outcome=report.get('operation_status') if isinstance(report.get('operation_status'),str) else mode
    if outcome=='complete':outcome='available' if positive else ('verified_zero' if rows else 'no_variant')
    # Verified in-stock rows shown with an incomplete check are a partial success,
    # not a lookup failure.
    elif positive and outcome in ('partial','source_error','unverified','catalog_loading'):outcome='partial_available'
    entry={k:_clean(source.get(k),int if k=='size' else float if k=='heel_cm' else str) for k in CRITERIA}
    entry.update(outcome=outcome[:40],positive_skus=len({r.get('variant_id') for r in positive}),positive_products=len({r.get('product_id') for r in positive}),complete=1 if report.get('complete') is True else 0)
    return [entry]

def _write(sid,channel,status,message,reply,answer,trace,reason,elapsed_ms):
    now=time.time();day=datetime.fromtimestamp(now,VN).date().isoformat();session=_session(sid)
    answer=answer if isinstance(answer,dict) else {};trace=trace if isinstance(trace,dict) else {}
    listing=answer.get('listing') if isinstance(answer.get('listing'),dict) else {}
    def names(values):return json.dumps([v for v in values if isinstance(v,str)][:16],ensure_ascii=False) if isinstance(values,list) else '[]'
    found=searches(answer.get('stock_options'))
    with _LOCK:
        db=connect()
        try:
            with db:
                if now-_LAST_PURGE[0]>3600:
                    db.execute('DELETE FROM turns WHERE ts<?',(now-retention_days()*86400,));_LAST_PURGE[0]=now
                turn=db.execute('SELECT coalesce(max(turn),0)+1 FROM turns WHERE session=?',(session,)).fetchone()[0]
                cur=db.execute('INSERT INTO turns(ts,day,session,turn,channel,status,reason,engine,answer_mode,message,reply,tools,policy_topics,guard_reasons,needs_clarification,lookup_incomplete,shown,elapsed_ms) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (now,day,session,turn,channel,status,reason,answer.get('engine'),answer.get('answer_mode'),redact(message),redact(reply),names(trace.get('tools_used')),names(trace.get('policy_topics')),names(trace.get('guard_reasons')),
                     1 if answer.get('needs_clarification') is True else 0,1 if answer.get('lookup_incomplete') is True else 0,listing.get('shown') if type(listing.get('shown')) is int else 0,elapsed_ms))
                for row in found:
                    db.execute('INSERT INTO searches(turn_id,ts,day,model_code,size,color,category,heel_cm,occasion,query,collection,outcome,positive_skus,positive_products,complete) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (cur.lastrowid,now,day,*(row[k] for k in CRITERIA),row['outcome'],row['positive_skus'],row['positive_products'],row['complete']))
        finally:db.close()

def record(sid,message,original,shown,trace=None,channel='web',elapsed_ms=None):
    """A delivered turn. original: answer before projection (full report)."""
    if not enabled():return False
    try:
        answer=dict(shown) if isinstance(shown,dict) else {}
        if isinstance(original,dict) and 'stock_options' in original:answer['stock_options']=original['stock_options']
        _write(sid,channel,'ok',message,answer.get('reply'),answer,trace,None,elapsed_ms)
        return True
    except Exception:
        LOG.warning('MERLY_INSIGHTS_RECORD_DROPPED');return False

def record_failure(sid,message,reason,status='failed',channel='web',elapsed_ms=None):
    """A turn the visitor sent but did not get an answer for (error or limit)."""
    if not enabled():return False
    try:
        _write(sid,channel,status,message,None,{},None,str(reason)[:60] if reason else None,elapsed_ms)
        return True
    except Exception:
        LOG.warning('MERLY_INSIGHTS_RECORD_DROPPED');return False
