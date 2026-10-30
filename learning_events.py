"""Opt-in best-effort metadata delivery; never block/retry customer inference."""
import os,re,json,queue,threading,urllib.request,logging
from learning_contract import capture
URL='http://learning-review:8090/v1/cases'
_QUEUE=queue.Queue(maxsize=64);_LOCK=threading.Lock();_THREAD=None
LOG=logging.getLogger('merly.learning')
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def send(event,token):
    req=urllib.request.Request(URL,data=json.dumps(event,separators=(',',':')).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    with urllib.request.build_opener(NoRedirect).open(req,timeout=1) as response:
        if response.status not in (200,201):raise ValueError('delivery_failed')
        response.read(1024)

def worker():
    while True:
        event,token=_QUEUE.get()
        try:send(event,token)
        except Exception:LOG.warning('MERLY_LEARNING_DELIVERY_DROPPED')
        finally:_QUEUE.task_done()

def emit(diagnostic_id,answer=None,trace=None,failure=None):
    global _THREAD
    # Disabled by default. Never accept an endpoint or a filesystem path.
    if os.getenv('MERLY_LEARNING_ENABLED')!='1':return False
    token=os.getenv('MERLY_LEARNING_INGEST_TOKEN','')
    if not re.fullmatch('[A-Za-z0-9_-]{32,128}',token):
        LOG.warning('MERLY_LEARNING_INVALID_CONFIG');return False
    try:
        event=capture(diagnostic_id,answer,trace,failure)
        if event is None:return False
        with _LOCK:
            if _THREAD is None or not _THREAD.is_alive():
                _THREAD=threading.Thread(target=worker,daemon=True,name='learning-delivery');_THREAD.start()
        _QUEUE.put_nowait((event,token));return True
    except Exception:
        LOG.warning('MERLY_LEARNING_CAPTURE_DROPPED');return False
