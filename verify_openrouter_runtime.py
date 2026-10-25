"""Pinned Hermes provider resolution + OpenAI SDK client; no inference/key needed."""
import os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SCRIPT=r'''
import os,json,socket
from pathlib import Path
def blocked(*a,**k):raise AssertionError('unexpected_network_in_offline_verification')
socket.socket.connect=blocked
import run_sales,hermes_yaml
home=Path(os.environ['HERMES_HOME']);home.mkdir()
config=json.loads((Path(os.environ['VERIFY_REPO'])/'hermes-config.template.json').read_text())
config['model']={'provider':'gemini','default':'gemini-old-fixture'}
(home/'config.yaml').write_text(hermes_yaml.safe_dump(config))
assert run_sales.ensure_sales_model(home)
config=hermes_yaml.safe_load((home/'config.yaml').read_text())
from hermes_cli.runtime_provider import resolve_runtime_with_fallback
runtime,_=resolve_runtime_with_fallback(config,requested='openrouter',target_model=config['model']['default'],explicit_base_url=config['model']['base_url'])
assert config['model']['default']=='deepseek/deepseek-v4.1-flash-1017'
assert runtime['provider']=='openrouter'
assert runtime['base_url']=='https://openrouter.ai/api/v1'
assert runtime['api_mode']=='chat_completions'
assert runtime['api_key']==os.environ['OPENROUTER_API_KEY']
from openai import OpenAI
client=OpenAI(api_key=runtime['api_key'],base_url=runtime['base_url'])
assert str(client.base_url).rstrip('/')=='https://openrouter.ai/api/v1'
assert client.auth_headers['Authorization']=='Bearer '+os.environ['OPENROUTER_API_KEY']
client.close()
print('PASS_PINNED_HERMES_OPENROUTER migrated_from_gemini=true provider=openrouter api_mode=chat_completions model=deepseek/deepseek-v4.1-flash-1017 native_key_resolution=true inference_calls=0')
'''
def main():
    with tempfile.TemporaryDirectory(prefix='verify-openrouter-') as tmp:
        env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
        env.update({'HOME':tmp,'HERMES_HOME':str(Path(tmp)/'sales'),'OPENROUTER_API_KEY':'synthetic-openrouter-key-not-valid','MERLY_GEMINI_MODEL':'gemini-old-fixture','GOOGLE_API_KEY':'synthetic-old-google-key','VERIFY_REPO':str(ROOT),'PYTHONPATH':str(ROOT)})
        subprocess.run([sys.executable,'-c',SCRIPT],env=env,cwd=ROOT,check=True,timeout=30)
if __name__=='__main__':main()
