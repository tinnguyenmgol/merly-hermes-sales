"""Actual pinned Hermes AIAgent -> local OpenAI HTTP stub. NOT a semantic/model test.
Fresh home, no credentials, no external network, no tools/paid inference.
"""
import os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).parent
SCRIPT=r'''
import os,json,socket,threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
# Fail closed before any network: only this process's numeric loopback endpoint.
connect=socket.socket.connect
socket.socket.connect=lambda s,a:connect(s,a) if isinstance(a,tuple) and a[0] in ('127.0.0.1','::1') else (_ for _ in ()).throw(AssertionError('external_network_forbidden'))
getaddrinfo=socket.getaddrinfo
socket.getaddrinfo=lambda host,*a,**kw:getaddrinfo(host,*a,**kw) if host in ('127.0.0.1','::1') else (_ for _ in ()).throw(AssertionError('external_dns_forbidden'))
seen=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  if self.path!='/v1/chat/completions':
   print('OFFLINE_OPTIONAL_ENDPOINT',self.path,flush=True)
   self.send_response(404);self.send_header('Content-Length','0');self.end_headers();return
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));seen.append(data)
  if data.get('stream'):
   events=[{'id':'offline','object':'chat.completion.chunk','created':0,'model':'offline','choices':[{'index':0,'delta':{'role':'assistant','content':'OFFLINE_TRANSPORT_ACK'},'finish_reason':None}]},{'id':'offline','object':'chat.completion.chunk','created':0,'model':'offline','choices':[{'index':0,'delta':{},'finish_reason':'stop'}]}]
   raw=(''.join('data: '+json.dumps(e)+'\n\n' for e in events)+'data: [DONE]\n\n').encode();mime='text/event-stream'
  else:
   raw=json.dumps({'id':'offline','object':'chat.completion','created':0,'model':'offline','choices':[{'index':0,'message':{'role':'assistant','content':'OFFLINE_TRANSPORT_ACK'},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}).encode();mime='application/json'
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
import hermes_yaml
root=Path(os.environ['VERIFY_REPO']);home=Path(os.environ['HERMES_HOME']);home.mkdir()
config=json.loads((root/'hermes-config.template.json').read_text());config['mcp_servers']={};config['toolsets']=[];config['platform_toolsets']={};(home/'config.yaml').write_text(hermes_yaml.safe_dump(config))
from run_agent import AIAgent
import run_agent
assert json.loads((root/'HERMES-SOURCE.json').read_text())['commit'] in str(Path(run_agent.__file__).resolve())
from policy_knowledge import context
knowledge,revision,count=context(root)
agent=AIAgent(base_url='http://127.0.0.1:'+str(server.server_port)+'/v1',api_key='synthetic-local-only',provider='openai',api_mode='chat_completions',model='gpt-4o-mini',enabled_toolsets=[],disabled_toolsets=config['agent']['disabled_toolsets']+['merly'],max_iterations=2,skip_context_files=True,skip_memory=True,skip_background_review=True,quiet_mode=True,ephemeral_system_prompt=(root/'SYSTEM-PROMPT.md').read_text()+knowledge,cwd=str(home))
try:
 raw='có freeship ko'
 result=agent.run_conversation(raw,conversation_history=[])
 assert result.get('final_response')=='OFFLINE_TRANSPORT_ACK',result.get('error')
 assert len(seen)==1
 assert not seen[0].get('tools')
 messages=seen[0]['messages'];assert messages[-1]['role']=='user' and messages[-1]['content']==raw,messages[-1]
 system='\n'.join(m['content'] for m in messages if m['role']=='system' and isinstance(m.get('content'),str))
 assert 'APPROVED_CUSTOMER_KNOWLEDGE_JSON' in system and '876 Trường Sa' in system and '300.000đ' in system
 print('PASS_PINNED_HERMES_POLICY_TRANSPORT raw_user_exact=true approved_knowledge_at_provider=true real_agent_loop=true local_http_stub=true paid_calls=0 semantic_evaluation=NOT_RUN')
finally:
 agent.close();server.shutdown();server.server_close()
'''
def main():
    with tempfile.TemporaryDirectory(prefix='policy-wire-',dir=os.getenv('TMPDIR','/workspace/tmp')) as tmp:
        env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
        env.update(HOME=tmp,HERMES_HOME=str(Path(tmp)/'sales'),VERIFY_REPO=str(ROOT),PYTHONPATH=str(ROOT))
        subprocess.run([sys.executable,'-c',SCRIPT],cwd=ROOT,env=env,check=True,timeout=75)
if __name__=='__main__':main()
