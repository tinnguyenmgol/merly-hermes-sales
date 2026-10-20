"""Fixed read-only internal stock probe; no model or arbitrary URL/tool."""
import hmac,json,os,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

def make_server(address=('0.0.0.0',8644)):
    key=os.environ.get('API_SERVER_KEY','')
    if len(key)<32:raise RuntimeError('stock_probe_requires_dedicated_api_key')
    import merly_tools as tools
    restore_lock=threading.Lock();restored=[0.0]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def send(self,code,body):
            raw=json.dumps(body,ensure_ascii=False).encode()
            self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
        def do_POST(self):
            if self.path not in ('/stock','/catalog-search'):return self.send(404,{'error':'not_found'})
            if not hmac.compare_digest(self.headers.get('Authorization','').encode(),('Bearer '+key).encode()):return self.send(401,{'error':'unauthorized'})
            self.connection.settimeout(15)
            try:
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError()
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=4096:raise ValueError()
                data=json.loads(self.rfile.read(n))
                if self.path=='/catalog-search':
                    if not isinstance(data,dict) or set(data)!={'heel_cm','size','limit'}:raise ValueError()
                    tools.validate(data,{'heel_cm':(float,0,15),'size':(int,35,43),'limit':(int,1,4)})
                elif not isinstance(data,dict) or set(data)-{'model_code','size','color'} or not {'model_code','size'}<=set(data):raise ValueError()
                if self.path=='/stock':tools.validate(data,{'model_code':(str,1,32),'size':(int,35,43),'color':(str,1,40)})
            except (ValueError,TypeError):return self.send(400,{'error':'invalid_scope'})
            try:
                if self.path=='/stock':tools.catalog.restore()
                else:
                    with restore_lock:
                        if time.monotonic()-restored[0]>=5:
                            tools.catalog.restore();restored[0]=time.monotonic()
                self.send(200,tools.dispatch('search_products',data if self.path=='/catalog-search' else {**data,'check_stock':True}))
            except Exception:self.send(503,{'error':'source_unavailable'})
    return ThreadingHTTPServer(address,Handler)

def start():
    server=make_server()
    threading.Thread(target=server.serve_forever,daemon=True,name='merly-stock-probe').start()
    print(json.dumps({'status':'readonly_stock_probe_ready','port':8644}),flush=True)
    return server
