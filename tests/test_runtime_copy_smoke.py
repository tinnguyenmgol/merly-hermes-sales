"""Copied-runtime smoke test, not a Docker build or live model test."""
import fnmatch,json,os,shlex,shutil,subprocess,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]

def included(path):
    result=True
    for pattern in (ROOT/'.dockerignore').read_text().splitlines():
        if not pattern or pattern.startswith('#'):continue
        if fnmatch.fnmatchcase(path,pattern.lstrip('!').rstrip('/')):result=pattern.startswith('!')
    return result

def materialize(name,target):
    copied=set()
    for line in (ROOT/name).read_text().splitlines():
        if not line.startswith('COPY '):continue
        tokens=shlex.split(line);destination=tokens[-1]
        for source in tokens[1:-1]:
            p=ROOT/source
            # Build-time SDK archive is not a runtime module; pip dependencies
            # are supplied by the test interpreter, not copied from the repo.
            if source.rstrip('/')=='build-sources':continue
            if p.is_file():
                if included(source):shutil.copy2(p,target/p.name);copied.add(p.name)
            else:
                assert destination.startswith('./')
                out=target/destination
                for f in p.rglob('*'):
                    if f.is_file() and '__pycache__' not in f.parts and included(str(f.relative_to(ROOT))):
                        dest=out/f.relative_to(p);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
    return copied

SCRIPT=r'''
import sys,json,time
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root))
import agent_answer,customer_listing,mcp_server
assert Path(agent_answer.__file__).parent==root
q='Chị đi size mấy để em kiểm tra đúng yêu cầu ạ?'
def response(text,items=()):
 return {'output':list(items)+[{'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}]}
a=customer_listing.project(agent_answer.present(response(q),'resp_copied',time.time()))
assert a['reply']==q and a['needs_clarification'] and a['listing']['shown']==0
result,error=mcp_server.invoke('search_products',{'check_stock':True,'heel_cm':5,'color':'Đen'})
assert not error and result['status']=='needs_clarification' and result['source_read_attempted'] is False
items=[{'type':'function_call','name':'mcp__merly__search_products','call_id':'missing','arguments':'{"check_stock":true}'},{'type':'function_call_output','call_id':'missing','output':json.dumps(result)}]
a=customer_listing.project(agent_answer.present(response(q,items),'resp_missing',time.time()))
assert a['reply']==q and a['listing']['shown']==0
assert Path(sys.modules['clarification'].__file__).parent==root
print('COPIED_RUNTIME_OK')
'''

def run(target):
    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ};env['HOME']=str(target)
    return subprocess.run([sys.executable,'-I','-c',SCRIPT,str(target)],cwd=target,env=env,capture_output=True,text=True,timeout=30)

@pytest.mark.parametrize('dockerfile',['Dockerfile.adapter','Dockerfile.hermes'])
def test_actual_runtime_copy_supports_first_ai_reply(tmp_path,dockerfile):
    copied=materialize(dockerfile,tmp_path)
    assert 'clarification.py' in copied,'runtime helper omitted by COPY/.dockerignore'
    p=run(tmp_path)
    assert p.returncode==0,p.stderr
    assert p.stdout.strip()=='COPIED_RUNTIME_OK'

@pytest.mark.parametrize('dockerfile',['Dockerfile.adapter','Dockerfile.hermes'])
def test_missing_helper_reproduces_failure_without_repo_fallback(tmp_path,dockerfile):
    materialize(dockerfile,tmp_path);(tmp_path/'clarification.py').unlink(missing_ok=True)
    p=run(tmp_path)
    assert p.returncode!=0 and "No module named 'clarification'" in p.stderr
