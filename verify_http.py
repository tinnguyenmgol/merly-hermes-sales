"""Real HTTP, explicitly SYNTHETIC Hermes Responses API; not model reasoning."""
import http.client,json,os,socket,subprocess,sys,tempfile,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import safety
ROOT=Path(__file__).parent
seen=[]
class FixtureHermes(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def send(self,data):
        body=json.dumps(data).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        assert self.headers['Authorization']=='Bearer '+'K'*40
        if self.path=='/v1/capabilities':return self.send({'platform':'hermes-agent','features':{'responses_api':True}})
        assert self.path=='/v1/toolsets';self.send({'data':[{'name':'terminal','enabled':False,'tools':['terminal']}]})
    def do_POST(self):
        assert self.path=='/v1/responses';assert self.headers['Authorization']=='Bearer '+'K'*40
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));seen.append((data,self.headers['X-Hermes-Session-Key']))
        self.send({'id':'resp_fixture'+str(len(seen)),'status':'completed','output':[{'type':'reasoning','summary':[{'text':'PRIVATE'}]},{'type':'message','phase':'commentary','content':[{'type':'output_text','text':'PROGRESS'}]},{'type':'message','role':'assistant','content':[{'type':'output_text','text':'SYNTHETIC HERMES API FIXTURE'}]}]})
def post(port,message,cookie=''):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=8)
    c.request('POST','/api/chat',json.dumps({'message':message}),{'Content-Type':'application/json','Authorization':'Bearer '+'P'*40,'Cookie':cookie})
    r=c.getresponse();headers=dict(r.getheaders());data=json.loads(r.read());c.close()
    assert r.status==200,(r.status,data)
    return headers,data
with tempfile.TemporaryDirectory(dir='/workspace/tmp',prefix='merly-hermes-http-') as tmp:
    server=ThreadingHTTPServer(('127.0.0.1',0),FixtureHermes);threading.Thread(target=server.serve_forever,daemon=True).start()
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    base=f'http://127.0.0.1:{server.server_port}/v1';audit=Path(tmp)/'audit.json'
    record={'created_at':time.time(),'api_base':base,'tools':sorted(safety.NAMES),'memory_enabled':False,'user_profile_enabled':False}
    audit.write_text(json.dumps({'record':record,'signature':safety.digest(record,'K'*40)}))
    env=dict(os.environ,PILOT_ACCESS_KEY='P'*40,PILOT_SESSION_SECRET='S'*40,HERMES_PILOT_STATE_DB=tmp+'/state.db',HERMES_SALES_API_BASE=base,HERMES_SALES_API_KEY='K'*40,HERMES_SALES_ISOLATION_APPROVED='1',HERMES_CUSTOMER_DATA_APPROVED='1',HERMES_MODEL_COST_APPROVED='1',HERMES_ALLOW_HTTP='1',HERMES_SALES_ATTESTATION=str(audit))
    p=subprocess.Popen([sys.executable,'-m','gunicorn','--no-control-socket','--bind',f'127.0.0.1:{port}','--workers','1','--threads','2','sales_gateway:application'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(70):
            if p.poll() is not None:raise RuntimeError(p.stderr.read().decode())
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):break
            except OSError:time.sleep(.1)
        h,a=post(port,'size 39 chân dài bao nhiêu');cookie=h['Set-Cookie'].split(';')[0]
        _,b=post(port,'có mẫu nào cao 5cm ko',cookie)
        _,c=post(port,'hello')
        assert seen[1][0]['previous_response_id']=='resp_fixture1'
        assert 'previous_response_id' not in seen[2][0]
        assert seen[0][1]==seen[1][1]!=seen[2][1]
        assert seen[1][0]['input']=='có mẫu nào cao 5cm ko'
        assert all(x['reply']=='SYNTHETIC HERMES API FIXTURE' for x in (a,b,c))
        print('PASS_HTTP gateway -> SYNTHETIC Hermes Responses, session-key and response-chain isolation, raw user text, final-only reply')
        print('NOT_TESTED real Hermes runtime/model, live Haravan, production deploy or Dify replacement acceptance')
    finally:p.terminate();p.wait(timeout=10);server.shutdown();server.server_close()
