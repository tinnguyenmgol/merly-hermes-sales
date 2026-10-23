"""Real local Gunicorn(1 worker/4 threads),100 complete literal stock requests with AI budget full; NO inference."""
import json,os,socket,subprocess,sys,tempfile,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='merly-fast-load-',dir=os.getenv('TMPDIR','/workspace/tmp')) as tmp:
    env=dict(os.environ,PYTHONPATH=str(ROOT),MERLY_PUBLIC_CHAT_ENABLED='1',MERLY_PUBLIC_ORIGIN='https://chat.merlyshoes.com',PILOT_ACCESS_KEY='P'*40,PILOT_SESSION_SECRET='S'*40,HERMES_PILOT_STATE_DB=tmp+'/state.db',HERMES_SALES_API_BASE='https://offline.invalid/v1',HERMES_SALES_API_KEY='T'*40,HERMES_SALES_ISOLATION_APPROVED='1',HERMES_CUSTOMER_DATA_APPROVED='1',HERMES_MODEL_COST_APPROVED='1')
    from fast_limits import DEFAULTS
    for k,v in DEFAULTS.items():env['MERLY_'+k]=str(v)
    os.environ['HERMES_PILOT_STATE_DB']=env['HERMES_PILOT_STATE_DB']
    import state
    db=state.database()
    with db:db.executemany('INSERT INTO calls VALUES(?)',[(time.time(),)]*100)
    db.close()
    Path(tmp,'load_app.py').write_text("import sales_gateway as g,hermes_client as c\ndef forbidden(*a,**kw):raise AssertionError('inference forbidden')\nc.chat=forbidden\nc.probe_stock=lambda scope:{'reply':'SYNTHETIC inventory','model_called':False}\napplication=g.application\n")
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    cmd=[sys.executable,'-m','gunicorn','--no-control-socket','--chdir',tmp,'--bind','127.0.0.1:'+str(port),'--workers','1','--threads','4','--timeout','60','--access-logfile',os.devnull,'load_app:application']
    with open(Path(tmp,'server.log'),'w+') as log:
        proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=log)
        base='http://127.0.0.1:'+str(port)
        def session():
            with urllib.request.urlopen(base+'/api/public/session',timeout=20) as r:return r.headers['Set-Cookie'].split(';')[0],json.load(r)['csrf']
        try:
            for _ in range(100):
                try:session();break
                except Exception:
                    if proc.poll() is not None:log.seek(0);raise RuntimeError(log.read())
                    time.sleep(.05)
            import asyncio,aiohttp
            async def exercise():
                timeout=aiohttp.ClientTimeout(total=25)
                async with aiohttp.ClientSession(timeout=timeout,connector=aiohttp.TCPConnector(limit=100)) as client:
                    async def visitor():
                        async with client.get(base+'/api/public/session') as r:
                            return r.headers['Set-Cookie'].split(';')[0],(await r.json())['csrf']
                    sessions=await asyncio.gather(*(visitor() for _ in range(100)))
                    async def post(visitor,message):
                        cookie,csrf=visitor;start=time.perf_counter()
                        async with client.post(base+'/api/public/chat',json={'message':message},headers={'Origin':'https://chat.merlyshoes.com','Cookie':cookie,'X-Merly-CSRF':csrf}) as r:
                            return r.status,await r.json(),time.perf_counter()-start
                    rows=await asyncio.gather(*(post(s,'mẫu 1514 38 còn màu gì') for s in sessions))
                    assert all((status==200 and body.get('reply')=='SYNTHETIC inventory' and body.get('model_called') is False) or (status==429 and body.get('error')=='stock_capacity') for status,body,_ in rows),rows
                    assert any(status==200 for status,_,_ in rows)
                    blocked=await post(sessions[0],'địa chỉ shop')
                    assert blocked[0]==429 and blocked[1]['error']=='daily_budget_limit'
                    stock=await post(sessions[0],'mẫu 1514 38 còn màu gì')
                    assert stock[0]==200 and stock[1]['model_called'] is False
                    return rows,blocked,stock
            rows,blocked,stock=asyncio.run(exercise())
            db=state.database();assert db.execute('SELECT count(*) FROM calls').fetchone()[0]==100;db.close()
            times=sorted(t for _,_,t in rows)
            result={'requests':len(rows),'http200':sum(status==200 for status,_,_ in rows),'http429_backpressure':sum(status==429 for status,_,_ in rows),'local_only':True,'inference_calls':0,'ai_budget_already_full':True,'all_status_p50_ms':round(times[49]*1000,1),'all_status_p95_ms':round(times[94]*1000,1),'all_status_max_ms':round(times[-1]*1000,1),'stock_with_full_ai_budget':stock[0],'policy_ai_blocked':blocked[0]}
            if os.getenv('MERLY_LOAD_REPORT'):Path(os.environ['MERLY_LOAD_REPORT']).write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result))
        except Exception:
            log.flush();log.seek(0);print(log.read()[-9000:]);raise
        finally:proc.terminate();proc.wait(timeout=10)
