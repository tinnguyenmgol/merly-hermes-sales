import asyncio,json,socket
import pytest,httpx2,uvicorn
from starlette.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from qa_core import Manager,Ledger
from qa_server import create_app
TOKEN='T'*48;HOST='qa.example.test'
class FakeSession:
    sent=[]
    def __init__(self,deadline):self.cookie='C'*43;self.csrf='a'*64
    def bootstrap(self):pass
    def send(self,message):
        self.sent.append(message)
        return 200,{'reply':'QA_ACK','diagnostic_id':'a'*16}


def test_missing_auth_wrong_auth_and_wrong_host_never_start_jobs(tmp_path):
    manager=Manager(Ledger(tmp_path),True,FakeSession)
    with TestClient(create_app(TOKEN,HOST,manager),base_url='http://'+HOST) as client:
        assert client.get('/health').status_code==200
        assert client.post('/mcp',json={}).status_code==401
        assert client.post('/mcp',json={},headers={'Authorization':'Bearer wrong'}).status_code==401
        response=client.post('/mcp',json={},headers={'Authorization':'Bearer '+TOKEN,'Host':'evil.invalid'})
        assert response.status_code==421
    assert not manager.jobs

@pytest.mark.parametrize('bad',['','x'*31,'has spaces '*5,'Bearer '+'T'*48])
def test_no_default_or_malformed_auth_secret(tmp_path,bad):
    with pytest.raises(RuntimeError,match='invalid_qa_auth'):create_app(bad,HOST,Manager(Ledger(tmp_path)))


def test_real_streamable_http_mcp_start_and_poll(tmp_path):
    async def case():
        FakeSession.sent=[];manager=Manager(Ledger(tmp_path),True,FakeSession)
        app=create_app(TOKEN,HOST,manager)
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,lifespan='on'))
        task=asyncio.create_task(server.serve(sockets=[sock]))
        try:
            for _ in range(100):
                if server.started:break
                await asyncio.sleep(.01)
            assert server.started
            async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+TOKEN,'Host':HOST},trust_env=False) as client:
                async with streamable_http_client('http://127.0.0.1:'+str(port)+'/mcp',http_client=client) as streams:
                    async with ClientSession(streams[0],streams[1]) as session:
                        await session.initialize();tools=(await session.list_tools()).tools
                        assert {t.name for t in tools}=={'qa_start_chat','qa_get_result'}
                        assert next(t for t in tools if t.name=='qa_start_chat').annotations.read_only_hint is False
                        bad=await session.call_tool('qa_start_chat',{'messages':['BAD'],'test_data_only':True,'url':'http://169.254.169.254/'})
                        assert bad.is_error and not FakeSession.sent
                        started=await session.call_tool('qa_start_chat',{'messages':['ONE','TWO'],'test_data_only':True})
                        assert not started.is_error
                        run_id=started.structured_content['run_id']
                        for _ in range(100):
                            response=await session.call_tool('qa_get_result',{'run_id':run_id})
                            data=response.structured_content
                            if data['state']!='running':break
                            await asyncio.sleep(.01)
                        assert data['state']=='completed' and len(data['turns'])==2
                        assert FakeSession.sent==['ONE','TWO']
                        assert TOKEN not in json.dumps(data) and 'C'*43 not in json.dumps(data)
        # Also prove the real Hermes config loader/discovery accepts this service.
            import importlib.util,os,subprocess,sys
            try:installed=importlib.util.find_spec('tools.mcp_tool_discovery')
            except ModuleNotFoundError:installed=None
            if installed:
                home=tmp_path/'technical-hermes';home.mkdir()
                config={'mcp_servers':{'merly_chat_qa':{'url':'${MERLY_QA_MCP_URL}','headers':{'Authorization':'Bearer ${MERLY_QA_AUTH_TOKEN}','Host':HOST},'tools':{'include':['qa_start_chat','qa_get_result']},'timeout':20}}}
                (home/'config.yaml').write_text(json.dumps(config))
                script="from tools.mcp_tool_discovery import discover_mcp_tools; from tools.mcp_tool_lifecycle import shutdown_mcp_servers; from model_tools import get_tool_definitions; discover_mcp_tools(allowed_mcp_names=['merly_chat_qa']); names={d['function']['name'] for d in get_tool_definitions(enabled_toolsets=['merly_chat_qa'],quiet_mode=True,skip_tool_search_assembly=True)}; assert names=={'mcp__merly_chat_qa__qa_start_chat','mcp__merly_chat_qa__qa_get_result'},names; shutdown_mcp_servers(); print('PASS_HERMES_QA_DISCOVERY two_tools=true secret_env_interpolation=true')"
                script="import socket; original=socket.socket.connect; socket.socket.connect=lambda s,a: original(s,a) if isinstance(a,tuple) and a[0] in ('127.0.0.1','::1') else (_ for _ in ()).throw(AssertionError('external_network_forbidden')); "+script
                env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
                env.update(HOME=str(home),HERMES_HOME=str(home),MERLY_QA_AUTH_TOKEN=TOKEN,MERLY_QA_MCP_URL='http://127.0.0.1:'+str(port)+'/mcp')
                result=await asyncio.to_thread(subprocess.run,[sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=45)
                assert result.returncode==0,(result.stdout,result.stderr)
                assert 'PASS_HERMES_QA_DISCOVERY' in result.stdout
                assert TOKEN not in result.stdout+result.stderr
                print('PASS_HERMES_QA_DISCOVERY actual_sdk=true two_tools=true secret_env_interpolation=true temporary_profile_only=true')

        finally:
            server.should_exit=True;await task
    asyncio.run(case())
