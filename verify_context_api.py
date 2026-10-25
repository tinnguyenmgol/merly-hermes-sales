"""Real pinned Responses HTTP -> AIAgent -> OpenAI HTTP stub -> MCP.
No paid inference. Scripted content proves wiring, NOT semantic accuracy.
"""
import os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).parent
SCRIPT=r'''
import os,json,socket,threading,asyncio,secrets,urllib.request,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
connect=socket.socket.connect
socket.socket.connect=lambda s,a:connect(s,a) if isinstance(a,tuple) and a[0] in ('127.0.0.1','::1') else (_ for _ in ()).throw(AssertionError('external_network_forbidden'))
seen=[]
class Provider(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  if self.path!='/v1/chat/completions':self.send_response(404);self.end_headers();return
  seen.append(json.loads(json.dumps(data)))
  messages=data['messages'];last=messages[-1]
  repair=any('TURN_VALIDATION_FEEDBACK_JSON (execution feedback,' in str(m.get('content','')) for m in messages if m['role']=='system')
  if 'TRIGGER_PROTOCOL_FIXTURE' in str(last.get('content')):
   message={'role':'assistant','content':'OFFLINE_RECOVERY_ACK?' if repair else '<｜DSML｜ calls>broken fixture</｜DSML｜ calls>'}
  elif last['role']=='tool':message={'role':'assistant','content':'OFFLINE_MCP_RESULT_ACK'}
  elif 'TRIGGER_MCP_FIXTURE' in str(last.get('content')):
   message={'role':'assistant','content':None,'tool_calls':[{'id':'fixture_call','type':'function','function':{'name':'mcp__merly__get_policy','arguments':'{"topic":"store_hours"}'}}]}
  else:message={'role':'assistant','content':'OFFLINE_CONTEXT_ACK'}
  if data.get('stream'):
   events=[{'id':'stub','object':'chat.completion.chunk','created':0,'model':'offline-fixture','choices':[{'index':0,'delta':message,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop'}]}]
   if message.get('tool_calls'):events[0]['choices'][0]['delta']['tool_calls'][0]['index']=0
   raw=(''.join('data: '+json.dumps(x)+'\n\n' for x in events)+'data: [DONE]\n\n').encode();mime='text/event-stream'
  else:
   raw=json.dumps({'id':'stub','object':'chat.completion','created':0,'model':'offline-fixture','choices':[{'index':0,'message':message,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}).encode();mime='application/json'
  self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
provider=ThreadingHTTPServer(('127.0.0.1',0),Provider);threading.Thread(target=provider.serve_forever,daemon=True).start()
root=Path(os.environ['VERIFY_REPO']);home=Path(os.environ['HERMES_HOME']);home.mkdir()
import hermes_yaml
config=json.loads((root/'hermes-config.template.json').read_text());config['model']={'provider':'custom','default':'offline-fixture','base_url':'http://127.0.0.1:'+str(provider.server_port)+'/v1'}
config['mcp_servers']['merly']['command']=os.environ['VERIFY_PYTHON'];config['mcp_servers']['merly']['args']=[str(root/'mcp_server.py')];config['mcp_servers']['merly']['env']={}
(home/'config.yaml').write_text(hermes_yaml.safe_dump(config));(home/'SOUL.md').write_text((root/'SYSTEM-PROMPT.md').read_text())
key=secrets.token_urlsafe(40);probe=socket.socket();probe.bind(('127.0.0.1',0));port=probe.getsockname()[1];probe.close()
from tools.mcp_tool_discovery import discover_mcp_tools
discover_mcp_tools(allowed_mcp_names=['merly'])
ready=threading.Event();errors=[]
async def serve():
 from gateway.config import PlatformConfig
 from gateway.platforms.api_server import APIServerAdapter
 adapter=APIServerAdapter(PlatformConfig(enabled=True,extra={'host':'127.0.0.1','port':port,'key':key}))
 assert await adapter.connect();ready.set()
 while not stop.is_set():await asyncio.sleep(.05)
 await adapter.disconnect()
stop=threading.Event()
def api_thread():
 try:asyncio.run(serve())
 except Exception as e:errors.append(type(e).__name__+':'+str(e));ready.set()
threading.Thread(target=api_thread,daemon=True).start();assert ready.wait(35) and not errors,errors
'''
SCRIPT+=r'''
import subprocess,sys
os.environ.update(API_SERVER_KEY=key,HERMES_SALES_API_BASE='http://127.0.0.1:'+str(port)+'/v1',HERMES_SALES_API_KEY=key,HERMES_SALES_ATTESTATION=str(home/'audit.json'),HERMES_ALLOW_HTTP='1',HERMES_PILOT_STATE_DB=str(home/'adapter.db'),PILOT_ACCESS_KEY=secrets.token_urlsafe(40),PILOT_SESSION_SECRET=secrets.token_urlsafe(40),HERMES_SALES_ISOLATION_APPROVED='1',HERMES_CUSTOMER_DATA_APPROVED='1',HERMES_MODEL_COST_APPROVED='1',MERLY_AGENT_REPAIR_ENABLED='1',MERLY_AI_PER_MINUTE='200',MERLY_AI_PER_DAY='1000')
subprocess.run([sys.executable,str(root/'audit_instance.py')],cwd=home,env=dict(os.environ),check=True,timeout=35)
from wsgiref.simple_server import make_server,WSGIRequestHandler
import sales_gateway
class Quiet(WSGIRequestHandler):
 def log_message(self,*a):pass
gateway=make_server('127.0.0.1',0,sales_gateway.application,handler_class=Quiet);threading.Thread(target=gateway.serve_forever,daemon=True).start()
cookie=''
def chat(text):
 global cookie
 data=json.dumps({'message':text}).encode();req=urllib.request.Request('http://127.0.0.1:'+str(gateway.server_port)+'/api/chat',data=data,headers={'Authorization':'Bearer '+os.environ['PILOT_ACCESS_KEY'],'Content-Type':'application/json','Cookie':cookie})
 with urllib.request.urlopen(req,timeout=45) as response:
  cookie=response.headers['Set-Cookie'].split(';')[0];out=json.load(response)
 return out
try:
 a=chat('xin chào tôi cần mua giày nữ');b=chat('size 40 màu trắng cao cao tí');c=chat('TRIGGER_MCP_FIXTURE')
 assert a['reply']==b['reply']=='OFFLINE_CONTEXT_ACK' and c['reply']=='OFFLINE_MCP_RESULT_ACK',(a,b,c)
 assert all(x['answer_mode']=='native' for x in (a,b,c))
 second=seen[1]['messages'];visible=[m for m in second if m['role'] in ('user','assistant')]
 assert visible[-1]['content']=='size 40 màu trắng cao cao tí'
 assert any(m.get('content')=='xin chào tôi cần mua giày nữ' for m in visible)
 assert any(m.get('content')=='OFFLINE_CONTEXT_ACK' for m in visible)
 system='\n'.join(m['content'] for m in second if m['role']=='system' and isinstance(m.get('content'),str))
 assert all(x in system for x in ('MERLY_DIALOGUE_CONTRACT_BEGIN','TRUSTED_RUNTIME_CONTEXT_JSON','measurement_help'))
 assert {t['function']['name'] for t in seen[-1]['tools']}=={'mcp__merly__'+n for n in ('search_products','quote_variant','get_policy','get_promotions','size_guide')}
 assert any(m['role']=='tool' and '09:30' in m.get('content','') for m in seen[-1]['messages'])
 d=chat('TRIGGER_PROTOCOL_FIXTURE');assert d['reply']=='OFFLINE_RECOVERY_ACK?' and d['answer_mode']=='native'
 e=chat('NEXT_AFTER_REPAIR');assert e['reply']=='OFFLINE_CONTEXT_ACK'
 assert not any('DSML' in str(m.get('content','')) for m in seen[-1]['messages'] if m['role']=='assistant')
 assert not any('TURN_VALIDATION_FEEDBACK_JSON (execution feedback,' in str(m.get('content','')) for m in seen[-1]['messages'] if m['role']=='system')
 cases=json.loads((root/'eval/dialogue-cases.json').read_text())['cases'];turns=0
 for case in cases:
  cookie='';expected=[]
  for text in case['messages']:
   answer=chat(text);assert answer['reply']=='OFFLINE_CONTEXT_ACK'
   expected.append(text);actual=[m['content'] for m in seen[-1]['messages'] if m['role']=='user']
   assert actual==expected,(case['id'],actual,expected)
   turns+=1
 assert len(cases)==20 and turns==43
 print('PASS_CASESET_HTTP_TRANSPORT cases=20 user_turns=43 history_isolation=true provider_scripted=true semantic_evaluation=NOT_RUN',flush=True)
 print('PASS_REAL_HTTP_RECOVERY same_turn=true safe_reply_recorded=true hidden_protocol_not_replayed=true paid_calls=0',flush=True)
 print('PASS_REAL_HTTP_CONTEXT gateway_http=true responses_http=true real_agent=true real_mcp=true provider_http_stub=true delivered_history=true paid_calls=0 semantic_evaluation=NOT_RUN',flush=True)
finally:gateway.shutdown();gateway.server_close();stop.set();provider.shutdown();provider.server_close()
'''
def main():
 with tempfile.TemporaryDirectory(prefix='context-api-',dir=os.getenv('TMPDIR','/workspace/tmp')) as tmp:
  env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
  env.update(HOME=tmp,HERMES_HOME=str(Path(tmp)/'sales'),VERIFY_REPO=str(ROOT),VERIFY_PYTHON=sys.executable,PYTHONPATH=str(ROOT),OPENAI_API_KEY='synthetic-local-only')
  subprocess.run([sys.executable,'-c',SCRIPT],env=env,cwd=ROOT,check=True,timeout=150)
if __name__=='__main__':main()
