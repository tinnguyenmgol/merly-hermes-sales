"""Public webchat evaluation. Default dry-run; --live may incur model costs.
Records transcripts for human rubric review; never reports NLU success by itself.
"""
import argparse,json,time,os,urllib.request,urllib.error,http.cookiejar
from pathlib import Path
BASE='https://chat.merlyshoes.com'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None

def cases():return json.loads(Path(__file__).with_name('eval').joinpath('dialogue-cases.json').read_text())['cases']
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--live',action='store_true');p.add_argument('--case');p.add_argument('--out');args=p.parse_args()
    rows=[r for r in cases() if not args.case or r['id']==args.case]
    if not rows:p.error('unknown case; list cases without --live')
    if not args.live:
        print(json.dumps({'mode':'dry_run','network_calls':0,'cases':len(rows),'turns':sum(len(r['messages']) for r in rows),'ids':[r['id'] for r in rows],'semantic_evaluation':'NOT_RUN'},ensure_ascii=False));return
    if not args.out:p.error('--live requires --out; use a writable private path, not Git')
    fd=os.open(args.out,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    result={'mode':'live','semantic_evaluation':'UNSCORED_REQUIRES_HUMAN_REVIEW','cases':[],'complete':False};last=0
    def request(opener,path,data=None,csrf=None):
        raw=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
        headers={'Origin':BASE,'Content-Type':'application/json'}
        if csrf:headers['X-Merly-CSRF']=csrf
        req=urllib.request.Request(BASE+path,data=raw,headers=headers)
        try:
            with opener.open(req,timeout=60) as r:return json.loads(r.read(262144))
        except urllib.error.HTTPError as e:
            body=json.loads(e.read(262144));raise RuntimeError('HTTP '+str(e.code)+' '+str(body.get('error','unknown'))+' diagnostic='+str(body.get('diagnostic_id','none'))) from None
    try:
        for row in rows:
            opener=urllib.request.build_opener(NoRedirect,urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            session=request(opener,'/api/public/session');csrf=session['csrf'];case={'id':row['id'],'rubric':row['rubric'],'turns':[],'review':'UNSCORED'};result['cases'].append(case)
            for message in row['messages']:
                if last:time.sleep(max(0,25-(time.monotonic()-last)))
                last=time.monotonic();answer=request(opener,'/api/public/chat',{'message':message},csrf)
                case['turns'].append({'user':message,**{k:answer[k] for k in ('reply','answer_mode','lookup_incomplete','diagnostic_id') if k in answer}})
                if not isinstance(answer.get('reply'),str):raise RuntimeError('missing reply')
        result['complete']=True
    except Exception as e:
        result['error']=type(e).__name__+': '+str(e)
    finally:
        with os.fdopen(fd,'w') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'complete':result['complete'],'cases_recorded':len(result['cases']),'semantic_evaluation':result['semantic_evaluation'],'output':args.out}))
    if not result['complete']:raise SystemExit(1)
if __name__=='__main__':main()
