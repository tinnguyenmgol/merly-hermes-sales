"""Fixed-resource GET-only Coolify diagnostics. No deploy/env/terminal API."""
import json,os,re,urllib.request,urllib.error
HOST='https://panel.merlyshoes.com'
RESOURCE='f3rhymt285isnfqa5pjmcnbx'
MAX_BYTES=8*1024*1024
class ReadError(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw):return None

def fetch(skip=0,take=1):
    if type(skip) is not int or not 0<=skip<=9 or type(take) is not int or not 1<=take<=3:raise ReadError('invalid_window')
    token=os.getenv('COOLIFY_DIAGNOSTICS_TOKEN','').strip()
    if not token:raise ReadError('missing_token')
    url=HOST+'/api/v1/deployments/applications/'+RESOURCE+'?skip='+str(skip)+'&take='+str(take)
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json'},method='GET')
    try:
        with urllib.request.build_opener(NoRedirect).open(req,timeout=15) as r:raw=r.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:raise ReadError('response_too_large')
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get('deployments'),list):raise ReadError('unsupported_api_response')
        rows=data['deployments']
        if len(rows)>take or any(not isinstance(row,dict) for row in rows):raise ReadError('invalid_deployments')
        return rows
    except urllib.error.HTTPError as e:raise ReadError('coolify_http_'+str(e.code)) from None
    except (urllib.error.URLError,OSError,TimeoutError):raise ReadError('coolify_unreachable') from None
    except (ValueError,TypeError):raise ReadError('invalid_response') from None

def metadata(row):
    return {k:str(row[k])[:120] for k in ('deployment_uuid','status','commit','created_at','updated_at') if row.get(k) is not None}

def clean(text):
    token=os.getenv('COOLIFY_DIAGNOSTICS_TOKEN','')
    if token:text=text.replace(token,'[REDACTED]')
    text=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',text)
    lines=[];hidden=0
    for line in text.splitlines():
        if re.search(r'(?i)(token|secret|password|authorization|bearer|private.?key|api.?key|-----BEGIN|[?&](?:key|auth)=)',line):
            lines.append('[REDACTED SENSITIVE LINE]');hidden+=1;continue
        lines.append(re.sub(r'https?://\S+','[URL]',line)[:3000])
    return lines,hidden

def recent_deployments():
    rows=fetch(take=3)
    return {'resource_uuid':RESOURCE,'returned_rows':len(rows),'deployments':[metadata(r) for r in rows]}

def build_log(offset=0,lines=200):
    if type(lines) is not int or not 20<=lines<=400:raise ReadError('invalid_line_count')
    rows=fetch(skip=offset,take=1)
    if not rows:return {'status':'no_deployment_at_offset','resource_uuid':RESOURCE}
    row=rows[0];raw=row.get('logs')
    if raw is None or raw=='':return {'status':'logs_missing_or_redacted','deployment':metadata(row)}
    if isinstance(raw,str):
        try:raw=json.loads(raw)
        except ValueError:pass
    if isinstance(raw,list):text='\n'.join(str(item.get('output','')) for item in raw if isinstance(item,dict))
    elif isinstance(raw,str):text=raw
    else:raise ReadError('unsupported_log_format')
    safe,hidden=clean(text);tail='\n'.join(safe[-lines:])
    return {'status':'ok','resource_uuid':RESOURCE,'deployment':metadata(row),'lines_returned':len(safe[-lines:]),'sensitive_lines_hidden':hidden,'truncated':len(safe)>lines or len(tail)>48000,'log':tail[-48000:],'untrusted_data':True}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--offset',type=int,default=0);p.add_argument('--lines',type=int,default=200);a=p.parse_args()
    try:print(json.dumps(build_log(a.offset,a.lines),ensure_ascii=False))
    except ReadError as e:print(json.dumps({'status':'blocked','error':str(e)}));raise SystemExit(1)
