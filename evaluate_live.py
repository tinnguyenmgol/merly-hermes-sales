"""Capture REAL pilot replies for manual review; never synthesize model answers."""
import argparse,http.cookiejar,json,os,urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from hermes_client import NoRedirect
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--case',required=True);p.add_argument('--live',action='store_true');p.add_argument('--gateway',default='http://127.0.0.1:8789')
a=p.parse_args()
suite=json.loads(Path(__file__).with_name('acceptance.json').read_text())
case=next((c for c in suite['cases'] if c['name']==a.case),None)
if not case:p.error('unknown case')
if not a.live:
    print(json.dumps({'status':'NOT_RUN','requires':'--live and separately configured approved Hermes app','case':case},ensure_ascii=False));raise SystemExit(0)
if not all(os.getenv(k)=='1' for k in ('HERMES_CUSTOMER_DATA_APPROVED','HERMES_MODEL_COST_APPROVED','HERMES_SALES_ISOLATION_APPROVED')):p.error('Data/cost approvals required even for live evaluation')
key=os.getenv('PILOT_ACCESS_KEY','')
if len(key)<32:p.error('PILOT_ACCESS_KEY missing; never paste it into chat')
# Loopback tests need explicit cookie forwarding because production cookies are Secure.
url=urlsplit(a.gateway)
if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost')):p.error('HTTPS required outside loopback')
opener=urllib.request.build_opener(NoRedirect);cookie=''
for text in case['turns']:
    req=urllib.request.Request(a.gateway.rstrip('/')+'/api/chat',data=json.dumps({'message':text}).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key,'Cookie':cookie})
    try:
        with opener.open(req,timeout=50) as r:
            data=json.load(r);cookie=(r.headers.get('Set-Cookie') or cookie).split(';')[0]
    except Exception as e:
        print(json.dumps({'status':'LIVE_FAILED','error_type':type(e).__name__,'no_automatic_retry':True}));raise SystemExit(1)
    print(json.dumps({'case':a.case,'user':text,'actual_response':data,'human_review_required':True},ensure_ascii=False))
