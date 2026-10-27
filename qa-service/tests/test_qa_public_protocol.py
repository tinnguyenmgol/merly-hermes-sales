"""Actual public WSGI session+CSRF contract, synthetic model, no live requests."""
import asyncio,io,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import sales_gateway as g,hermes_client as c,dialogue
from qa_transport import ChatSession
from qa_core import Manager,Ledger
class Bridge:
    sock=None
    def __init__(self,timeout):pass
    def connect(self):pass
    def request(self,method,path,body=None,headers=None):
        raw=body or b'';result={}
        env={'REQUEST_METHOD':method,'PATH_INFO':path,'CONTENT_TYPE':headers.get('Content-Type',''),'CONTENT_LENGTH':str(len(raw)),'HTTP_ORIGIN':headers.get('Origin',''),'HTTP_COOKIE':headers.get('Cookie',''),'HTTP_X_MERLY_CSRF':headers.get('X-Merly-CSRF',''),'wsgi.input':io.BytesIO(raw)}
        def start(status,values):result.update(status=int(status.split()[0]),headers=values)
        result['body']=b''.join(g.application(env,start));self.result=result
    def getresponse(self):
        result=self.result
        class Response:
            status=result['status'];body=io.BytesIO(result['body'])
            def read1(self,n):return self.body.read(n)
            def getheaders(self):return result['headers']
        return Response()
    def close(self):pass

def test_manager_uses_real_public_cookie_csrf_and_same_conversation(tmp_path,monkeypatch):
    env={'MERLY_PUBLIC_CHAT_ENABLED':'1','MERLY_PUBLIC_ORIGIN':'https://chat.merlyshoes.com','PILOT_ACCESS_KEY':'P'*40,'PILOT_SESSION_SECRET':'S'*40,'HERMES_PILOT_STATE_DB':str(tmp_path/'public.db'),'HERMES_SALES_API_BASE':'https://offline.invalid/v1','HERMES_SALES_API_KEY':'K'*40,'HERMES_SALES_ISOLATION_APPROVED':'1','HERMES_CUSTOMER_DATA_APPROVED':'1','HERMES_MODEL_COST_APPROVED':'1'}
    for key,value in env.items():monkeypatch.setenv(key,value)
    observed=[]
    def model(message,user,cid):
        observed.append((message,user,dialogue.history(dialogue.sid(user))))
        return {'reply':'SYNTHETIC_NATIVE_REPLY','conversation_id':'resp_public_qa'}
    monkeypatch.setattr(c,'chat',model)
    async def case():
        manager=Manager(Ledger(tmp_path/'qa'),True,lambda deadline:ChatSession(deadline,Bridge))
        started=await manager.start(['Giày kiểm thử','Chọn size 42 màu đen'],True)
        await asyncio.gather(*list(manager.tasks))
        result=manager.result(started['run_id'])
        assert result['state']=='completed' and all(t['http_status']==200 for t in result['turns'])
        assert len(observed)==2 and observed[0][1]==observed[1][1]
        assert len(observed[1][2])==2 and observed[1][2][0]['content']=='Giày kiểm thử'
        assert 'csrf' not in json.dumps(result) and 'S'*40 not in json.dumps(result)
    asyncio.run(case())
