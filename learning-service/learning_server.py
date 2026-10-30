"""Private ingest-only HTTP. No HTTP approval/export/configuration endpoints."""
import os,json,hmac,re,threading,logging
from learning_store import Store,ReviewError
from learning_contract import InvalidEvent,json_object

def create_app(store,token):
    if not isinstance(token,str) or not re.fullmatch('[A-Za-z0-9_-]{32,128}',token):raise ValueError('invalid_ingest_secret')
    def app(env,start):
        def respond(status,data):
            raw=json.dumps(data).encode();start(status,[('Content-Type','application/json'),('Content-Length',str(len(raw))),('Cache-Control','no-store')]);return [raw]
        method=env.get('REQUEST_METHOD');path=env.get('PATH_INFO')
        if path=='/health' and method=='GET':return respond('200 OK',{'status':'ready'})
        if path!='/v1/cases' or method!='POST':return respond('404 Not Found',{'error':'not_found'})
        if not hmac.compare_digest(env.get('HTTP_AUTHORIZATION','').encode(),('Bearer '+token).encode()):return respond('401 Unauthorized',{'error':'unauthorized'})
        try:
            if env.get('CONTENT_TYPE','').split(';')[0]!='application/json':raise InvalidEvent('invalid_content_type')
            size=int(env.get('CONTENT_LENGTH','0'))
            if not 0<size<=4096:raise InvalidEvent('body_limit')
            data=json.loads(env['wsgi.input'].read(size),object_pairs_hook=json_object)
            result=store.ingest(data)
            return respond('201 Created' if result['created'] else '200 OK',result)
        except ReviewError as exc:return respond('409 Conflict',{'error':'case_conflict' if str(exc)=='diagnostic_conflict' else 'unavailable'})
        except (InvalidEvent,ValueError,TypeError):return respond('400 Bad Request',{'error':'invalid_metadata'})
        except Exception:return respond('503 Service Unavailable',{'error':'learning_unavailable'})
    return app

def create_application():
    os.umask(0o077);store=Store(os.getenv('MERLY_LEARNING_STATE_DIR','/data'))
    app=create_app(store,os.getenv('MERLY_LEARNING_INGEST_TOKEN',''))
    stop=threading.Event()
    threading.Thread(target=maintenance,args=(store,stop),daemon=True,name='learning-retention').start()
    app.learning_stop_event=stop
    return app


def maintenance(store,stop,interval=60):
    while not stop.wait(interval):
        try:store.purge()
        except Exception:logging.getLogger('learning').warning('LEARNING_PURGE_FAILED')
