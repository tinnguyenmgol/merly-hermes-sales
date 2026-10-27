"""Bounded QA jobs. Persist only usage counters, never transcripts or credentials."""
import asyncio,copy,os,re,secrets,sqlite3,time
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from qa_transport import ChatSession,TransportError
MAX_MESSAGES=5;MAX_RUNS_DAY=3;MAX_MESSAGES_DAY=15;RUN_SECONDS=300;RETENTION=900
class Rejected(Exception):
    def __init__(self,code):self.code=code

class Ledger:
    def __init__(self,directory):
        directory=Path(directory)
        if directory.is_symlink():raise Rejected('unsafe_state_path')
        directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.path=directory/'qa-limits.sqlite3'
        if self.path.is_symlink():raise Rejected('unsafe_state_path')
        with closing(self.db()) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS usage(day TEXT PRIMARY KEY,runs INTEGER NOT NULL,turns INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS lease(id INTEGER PRIMARY KEY,job TEXT,until REAL)')
        os.chmod(self.path,0o600)
    def db(self):
        db=sqlite3.connect(self.path,timeout=5);db.execute('PRAGMA journal_mode=DELETE');return db
    def reserve(self,n,job):
        now=time.time();day=datetime.fromtimestamp(now,timezone.utc).date().isoformat()
        db=self.db()
        try:
            db.execute('BEGIN IMMEDIATE')
            lease=db.execute('SELECT until FROM lease WHERE id=1').fetchone()
            if lease and lease[0]>now:raise Rejected('qa_busy_or_cooldown')
            row=db.execute('SELECT runs,turns FROM usage WHERE day=?',(day,)).fetchone() or (0,0)
            if row[0]>=MAX_RUNS_DAY or row[1]+n>MAX_MESSAGES_DAY:raise Rejected('qa_daily_budget')
            db.execute('INSERT OR REPLACE INTO usage VALUES(?,?,?)',(day,row[0]+1,row[1]+n))
            db.execute('INSERT OR REPLACE INTO lease VALUES(1,?,?)',(job,now+RUN_SECONDS+60))
            db.execute('DELETE FROM usage WHERE day<?',(day,));db.commit()
        finally:db.close()
    def release(self,job):
        with closing(self.db()) as db,db:db.execute('DELETE FROM lease WHERE job=?',(job,))

def validate_messages(messages,test_data_only):
    if test_data_only is not True:raise Rejected('synthetic_test_data_required')
    if not isinstance(messages,list) or not 1<=len(messages)<=MAX_MESSAGES:raise Rejected('invalid_messages')
    if any(not isinstance(s,str) or not 1<=len(s.strip())<=1000 or len(s)>1000 or '\x00' in s for s in messages):raise Rejected('invalid_messages')

def redact(text,session):
    for value in (getattr(session,'cookie',None),getattr(session,'csrf',None)):
        if value:text=text.replace(value,'[REDACTED]')
    return text

def safe_result(status,data,elapsed,session):
    result={'http_status':status,'elapsed_ms':elapsed}
    trace=data.get('diagnostic_id')
    if isinstance(trace,str) and re.fullmatch('[0-9a-f]{16}',trace):result['diagnostic_id']=trace
    category=data.get('error_category')
    if category in ('timeout','configuration','response_incomplete','upstream_limit','request_failed'):result['error_category']=category
    if status!=200:return result
    reply=data.get('reply')
    if not isinstance(reply,str) or not reply.strip():raise TransportError('invalid_reply')
    clean=redact(reply,session)
    result['reply']=clean[:6000];result['reply_truncated']=len(clean)>6000
    cards=[];report=data.get('stock_options',{})
    groups=report.get('groups',[]) if isinstance(report,dict) and report.get('mode')=='groups' else [report]
    if not isinstance(groups,list):groups=[]
    rows=[]
    for group in groups[:8]:
        if isinstance(group,dict) and isinstance(group.get('variants'),list):rows.extend(group['variants'][:4])
    if isinstance(data.get('quotes'),list):rows.extend(data['quotes'][:4])
    for row in rows:
        if not isinstance(row,dict) or not all(type(row.get(k)) is int and 0<row[k]<10**16 for k in ('product_id','variant_id','known_available')):continue
        card={k:row[k] for k in ('product_id','variant_id','known_available')}
        for key in ('size','color','title'):
            if isinstance(row.get(key),str):card[key]=redact(row[key],session)[:300]
        if type(row.get('price_vnd')) is int and row['price_vnd']>=0:card['price_vnd']=row['price_vnd']
        cards.append(card)
        if len(cards)==4:break
    result['cards']=cards
    return result

class Manager:
    def __init__(self,ledger,approved=False,session_factory=ChatSession):
        self.ledger=ledger;self.approved=approved;self.session_factory=session_factory
        self.jobs={};self.tasks=set();self.active=None;self.lock=asyncio.Lock()
    async def start(self,messages,test_data_only):
        validate_messages(messages,test_data_only)
        if not self.approved:raise Rejected('live_testing_not_approved')
        async with self.lock:
            self.jobs={k:v for k,v in self.jobs.items() if time.monotonic()-v['_created']<RETENTION}
            if self.active:raise Rejected('qa_busy_or_cooldown')
            job=secrets.token_hex(16);self.ledger.reserve(len(messages),job)
            self.jobs[job]={'run_id':job,'state':'running','turns':[],'total_turns':len(messages),'_created':time.monotonic()}
            self.active=job
            task=asyncio.create_task(self.work(job,tuple(messages)));self.tasks.add(task);task.add_done_callback(self.tasks.discard)
            return {'run_id':job,'state':'running','poll_after_seconds':3,'warning':'Live chat may incur model cost; no automatic retries.'}
    def result(self,job):
        if not isinstance(job,str) or not re.fullmatch('[0-9a-f]{32}',job):raise Rejected('invalid_run_id')
        data=self.jobs.get(job)
        if not data or time.monotonic()-data['_created']>=RETENTION:
            self.jobs.pop(job,None);raise Rejected('run_not_found')
        return copy.deepcopy({k:v for k,v in data.items() if not k.startswith('_')})
    async def work(self,job,messages):
        data=self.jobs[job];session=None;completed=False
        try:
            session=self.session_factory(time.monotonic()+RUN_SECONDS)
            data['phase']='session'
            await asyncio.to_thread(session.bootstrap)
            data['phase']='chat'
            for message in messages:
                began=time.monotonic();status,body=await asyncio.to_thread(session.send,message)
                data['turns'].append(safe_result(status,body,round((time.monotonic()-began)*1000),session))
                if status!=200:data.update(state='failed',error='chat_http_error');return
            data['state']='completed';data['phase']='finished';completed=True
        except TransportError as exc:
            data.update(state='failed',error=exc.code)
            if type(exc.http_status) is int and 100<=exc.http_status<=599:data['http_status']=exc.http_status
        except asyncio.CancelledError:data.update(state='failed',error='service_stopped');raise
        except Exception:data.update(state='failed',error='qa_internal_error')
        finally:
            if session:session.cookie=None;session.csrf=None
            self.active=None
            if completed:self.ledger.release(job)
            # Failure retains the durable lease to avoid duplicate uncertain inference.
    async def close(self):
        for task in list(self.tasks):task.cancel()
        if self.tasks:await asyncio.gather(*self.tasks,return_exceptions=True)
