"""Private metadata cases; no transcripts. Approval is local-operator only."""
import json,os,re,secrets,sqlite3,time,hashlib
from pathlib import Path
from contextlib import closing
from learning_contract import validate
from recipes import RECIPES,suggest,bundle
TTL=30*24*3600
class ReviewError(ValueError):pass

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ReviewError('invalid_id')
    return value

class Store:
    def __init__(self,directory,clock=time.time,capacity=10000):
        self.directory=Path(directory);self.clock=clock;self.capacity=capacity
        if self.directory.is_symlink():raise ReviewError('unsafe_state_path')
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(self.directory,0o700)
        self.path=self.directory/'learning.sqlite3';self.exports=self.directory/'approved-exports'
        if self.path.is_symlink() or self.exports.is_symlink():raise ReviewError('unsafe_state_path')
        self.exports.mkdir(mode=0o700,exist_ok=True);os.chmod(self.exports,0o700)
        with closing(self.db()) as db,db:
            db.executescript('''CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,diagnostic TEXT UNIQUE NOT NULL,event TEXT NOT NULL,hash TEXT NOT NULL,created REAL NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS lessons(id TEXT PRIMARY KEY,case_id TEXT UNIQUE NOT NULL REFERENCES cases(id) ON DELETE CASCADE,recipe TEXT NOT NULL,spec TEXT NOT NULL,state TEXT NOT NULL,reviewed REAL);
CREATE TABLE IF NOT EXISTS audit(lesson_id TEXT REFERENCES lessons(id) ON DELETE CASCADE,action TEXT NOT NULL,at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS case_expiry ON cases(expires);''')
        os.chmod(self.path,0o600);self.purge()
    def db(self):
        db=sqlite3.connect(self.path,timeout=2);db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA secure_delete=ON');db.execute('PRAGMA max_page_count=8192')
        return db
    def purge(self):
        with closing(self.db()) as db,db:
            n=db.execute('DELETE FROM cases WHERE expires<=?',(self.clock(),)).rowcount
            active={r[0] for r in db.execute("SELECT id FROM lessons WHERE state='approved'")}
        for p in self.exports.iterdir():
            if re.fullmatch('[0-9a-f]{32}\\.json',p.name) and p.stem not in active:p.unlink(missing_ok=True)
        return n
    def ingest(self,event):
        event=validate(event);self.purge();raw=json.dumps(event,sort_keys=True,separators=(',',':'));digest=hashlib.sha256(raw.encode()).hexdigest();now=self.clock()
        with closing(self.db()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT id,hash FROM cases WHERE diagnostic=?',(event['diagnostic_id'],)).fetchone()
            if row:
                if row['hash']!=digest:raise ReviewError('diagnostic_conflict')
                return {'case_id':row['id'],'created':False}
            if db.execute('SELECT count(*) FROM cases').fetchone()[0]>=self.capacity:raise ReviewError('capacity')
            cid=secrets.token_hex(16);db.execute('INSERT INTO cases VALUES(?,?,?,?,?,?)',(cid,event['diagnostic_id'],raw,digest,now,now+TTL))
        return {'case_id':cid,'created':True}
    def mark(self,diagnostic_id):
        event=validate({'diagnostic_id':diagnostic_id,'outcome':'staff_marked','reason_codes':['staff_reported'],'criterion_fields':[],'tools':[],'tool_statuses':[]})
        self.purge()
        with closing(self.db()) as db:
            row=db.execute('SELECT id FROM cases WHERE diagnostic=?',(diagnostic_id,)).fetchone()
            if row:return {'case_id':row[0],'created':False,'existing_evidence_preserved':True}
        return self.ingest(event)
    def case(self,cid):
        identifier(cid);self.purge()
        with closing(self.db()) as db:
            r=db.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone()
            if not r:raise ReviewError('not_found')
            return {'case_id':r['id'],'event':json.loads(r['event']),'created_at':r['created'],'expires_at':r['expires'],'evidence_sha256':r['hash']}
    def list_cases(self):
        self.purge()
        with closing(self.db()) as db:
            return [dict(r) for r in db.execute('SELECT c.id AS case_id,c.diagnostic AS diagnostic_id,c.created,c.expires,l.id AS lesson_id,l.state,l.recipe FROM cases c LEFT JOIN lessons l ON l.case_id=c.id ORDER BY c.created DESC LIMIT 100')]
    def propose(self,cid,recipe_id=None):
        case=self.case(cid);explicit=recipe_id is not None;recipe_id=suggest(case['event']) if recipe_id is None else recipe_id
        if not isinstance(recipe_id,str) or recipe_id not in RECIPES:raise ReviewError('unknown_recipe')
        spec=json.dumps(RECIPES[recipe_id],ensure_ascii=False,sort_keys=True,separators=(',',':'))
        with closing(self.db()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT id,state FROM lessons WHERE case_id=?',(cid,)).fetchone()
            if row:
                lid=row[0]
                if explicit:
                    if row[1]!='draft':raise ReviewError('invalid_transition')
                    db.execute('UPDATE lessons SET recipe=?,spec=? WHERE id=?',(recipe_id,spec,lid))
                    db.execute('INSERT INTO audit VALUES(?,?,?)',(lid,'revise_draft',self.clock()))
            else:
                lid=secrets.token_hex(16);db.execute('INSERT INTO lessons VALUES(?,?,?,?,?,?)',(lid,cid,recipe_id,spec,'draft',None))
        return self.lesson(lid)
    def lesson(self,lid):
        identifier(lid);self.purge()
        with closing(self.db()) as db:
            row=db.execute('SELECT l.*,c.hash,c.diagnostic FROM lessons l JOIN cases c ON c.id=l.case_id WHERE l.id=?',(lid,)).fetchone()
            if not row:raise ReviewError('not_found')
            spec=json.loads(row['spec'])
            return {'lesson_id':row['id'],'case_id':row['case_id'],'diagnostic_id':row['diagnostic'],'recipe_id':row['recipe'],'state':row['state'],'reviewed_at':row['reviewed'],'proposal_is_hypothesis':True,'evidence_sha256':row['hash'],'category':spec['category'],'instruction_candidate':spec['lesson'],'proposal_sha256':hashlib.sha256(row['spec'].encode()).hexdigest(),'verification_status':'pending_offline_and_live_tests','deployment_authorized':False}
    def review(self,lid,decision,owner_confirmed=False):
        identifier(lid);self.purge()
        if owner_confirmed is not True:raise ReviewError('owner_confirmation_required')
        if decision not in ('approve','reject','revoke'):raise ReviewError('invalid_decision')
        with closing(self.db()) as db,db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state FROM lessons WHERE id=?',(lid,)).fetchone()
            if not row:raise ReviewError('not_found')
            if not (row[0]=='draft' and decision in ('approve','reject') or row[0]=='approved' and decision=='revoke'):raise ReviewError('invalid_transition')
            state='approved' if decision=='approve' else 'rejected';now=self.clock()
            db.execute('UPDATE lessons SET state=?,reviewed=? WHERE id=?',(state,now,lid));db.execute('INSERT INTO audit VALUES(?,?,?)',(lid,decision,now))
        if state!='approved':(self.exports/(lid+'.json')).unlink(missing_ok=True)
        return self.lesson(lid)
    def export(self,lid):
        identifier(lid);self.purge()
        with closing(self.db()) as db:
            row=db.execute('SELECT l.recipe,l.spec,l.state,c.hash FROM lessons l JOIN cases c ON c.id=l.case_id WHERE l.id=? AND c.expires>?',(lid,self.clock())).fetchone()
            if not row:raise ReviewError('not_found')
            if row['state']!='approved':raise ReviewError('approval_required')
            spec=json.loads(row['spec'])
        return bundle(lid,row['recipe'],row['hash'],spec)
    def export_file(self,lid):
        data=self.export(lid);path=self.exports/(identifier(lid)+'.json')
        raw=json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2).encode()
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        self.purge()
        if not path.exists():raise ReviewError('expired_during_export')
        return str(path)
    def analyze(self):
        self.purge()
        with closing(self.db()) as db:
            ids=[r[0] for r in db.execute('SELECT c.id FROM cases c LEFT JOIN lessons l ON l.case_id=c.id WHERE l.id IS NULL ORDER BY c.created LIMIT 100')]
        rows=[self.propose(cid) for cid in ids]
        return {'analysis_mode':'rules_only_hypotheses','model_calls':0,'drafts_created':len(rows),'proposals':rows,'auto_apply':False}
    def report(self):
        self.purge()
        with closing(self.db()) as db:
            return {'cases':db.execute('SELECT count(*) FROM cases').fetchone()[0],'lessons':{r[0]:r[1] for r in db.execute('SELECT state,count(*) FROM lessons GROUP BY state')},'retention_days':30,'model_calls':0,'auto_apply':False,'live_acceptance':'NOT_RUN'}
