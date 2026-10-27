"""Real pinned Hermes/MCP loop: reproduce cap4, verify migrated cap8.
Provider is a loopback HTTP fixture; it tests execution, NOT Vietnamese semantics.
"""
import os,sys,tempfile,subprocess
from pathlib import Path
from verify_context_api import SCRIPT,ROOT

PROVIDER=r'''  chain=any(m.get('role')=='user' and m.get('content')=='BUDGET_CHAIN_FIXTURE' for m in messages)
  if chain:
   from agent.context_compressor import MAX_ITERATIONS_SUMMARY_REQUEST
   summary=any(m.get('role')=='user' and m.get('content')==MAX_ITERATIONS_SUMMARY_REQUEST for m in messages)
   steps=sum(m.get('role')=='tool' for m in messages)
   needed={'legacy':5,'fixed':5,'exhausted':100,'boundary':7}[os.environ['VERIFY_BUDGET_MODE']]
   if summary:message={'role':'assistant','content':'FORCED_SUMMARY_FIXTURE_NOT_A_COMPLETED_TURN'}
   elif steps<needed:
    topics=['store_hours','store_address','shipping','size_exchange','warranty']
    message={'role':'assistant','content':None,'tool_calls':[{'id':'step_'+str(steps),'type':'function','function':{'name':'mcp__merly__get_policy','arguments':json.dumps({'topic':topics[steps%len(topics)]})}}]}
   else:message={'role':'assistant','content':'NATIVE_COMPLETE_AFTER_TOOL_CHAIN'}
  elif 'TRIGGER_PROTOCOL_FIXTURE' '''

SETUP=r'''
mode=os.environ['VERIFY_BUDGET_MODE']
# Simulate an existing volume; editing only the new template is NOT sufficient.
config['agent']['max_turns']=4
(home/'config.yaml').write_text(hermes_yaml.safe_dump(config))
from run_sales import ensure_sales_execution_budget,ensure_sales_execution_prompt
if mode!='legacy':
 before_model=config['model'].copy()
 assert ensure_sales_execution_budget(home)
 migrated=hermes_yaml.safe_load((home/'config.yaml').read_text())
 assert migrated['agent']['max_turns']==8 and migrated['agent']['run_budget_seconds']==40
 assert migrated['model']==before_model
 assert not ensure_sales_execution_budget(home)
 assert len(list(home.glob('config.before-sales-execution-budget-*')))==1
 ensure_sales_execution_prompt(home)
# Observe actual constructor values; do not alter the real loop or its result.
from run_agent import AIAgent
loaded=[];original_init=AIAgent.__init__
def observed_init(self,*args,**kwargs):
 original_init(self,*args,**kwargs)
 if kwargs.get('platform')=='api_server':loaded.append((self.max_iterations,self.run_budget_seconds))
AIAgent.__init__=observed_init
'''

TEST=r'''
try:
 import urllib.error,hermes_client
 native_received=[];original_request=hermes_client.request
 def observed_request(path,payload=None):
  data=original_request(path,payload)
  if path=='/responses':native_received.append(data)
  return data
 hermes_client.request=observed_request
 try:answer=chat('BUDGET_CHAIN_FIXTURE');http_status=200
 except urllib.error.HTTPError as exc:http_status=exc.code;answer=json.load(exc)
 expected=4 if mode=='legacy' else 8
 assert loaded and all(item==(expected,40) for item in loaded),loaded
 if mode in ('legacy','exhausted'):
  assert http_status==503 and answer['reason_code']=='turn_not_completed' and native_received[-1]['status']=='incomplete',answer
  assert len(seen)==expected+1,(mode,len(seen))
  assert 'reply' not in answer # never accept the forced summary as a complete result
 else:
  assert http_status==200 and answer['reply']=='NATIVE_COMPLETE_AFTER_TOOL_CHAIN' and native_received[-1]['status']=='completed',answer
  expected_calls=6 if mode=='fixed' else 8
  assert len(seen)==expected_calls,(mode,len(seen))
  assert all('iteration-summary:' not in str(x) for x in seen)
 print('PASS_ITERATION_HTTP mode='+mode+' max_iterations='+str(expected)+' run_budget_seconds=40 provider_calls='+str(len(seen))+' http_status='+str(http_status)+' real_agent=true real_mcp=true model_preserved=true provider_scripted=true paid_calls=0 semantic_evaluation=NOT_RUN',flush=True)
finally:gateway.shutdown();gateway.server_close();stop.set();provider.shutdown();provider.server_close()
'''

def program():
 script=SCRIPT.split('try:\n a=chat(',1)[0]
 needle="  if 'TRIGGER_PROTOCOL_FIXTURE' "
 assert script.count(needle)==1
 script=script.replace(needle,PROVIDER)
 anchor="key=secrets.token_urlsafe(40);probe=socket.socket();"
 assert script.count(anchor)==1
 return script.replace(anchor,SETUP+'\n'+anchor)+TEST

def main():
 modes=sys.argv[1:] or ['legacy','fixed','boundary','exhausted']
 assert set(modes)<= {'legacy','fixed','boundary','exhausted'}
 for mode in modes:
  with tempfile.TemporaryDirectory(prefix='iteration-'+mode+'-',dir=os.getenv('TMPDIR','/workspace/tmp')) as tmp:
   env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
   env.update(HOME=tmp,HERMES_HOME=str(Path(tmp)/'sales'),VERIFY_REPO=str(ROOT),VERIFY_PYTHON=sys.executable,PYTHONPATH=str(ROOT),OPENAI_API_KEY='synthetic-local-only',VERIFY_BUDGET_MODE=mode)
   result=subprocess.run([sys.executable,'-c',program()],env=env,cwd=ROOT,timeout=100)
   if result.returncode:raise SystemExit('Iteration fixture failed: '+mode)
 print('PASS_ITERATION_SUITE modes='+','.join(modes),flush=True)
if __name__=='__main__':main()
