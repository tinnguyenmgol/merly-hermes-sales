"""Run local operator CLI in real subprocesses; no production/customer calls."""
import json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def cli(state,*args,ok=True):
    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ};env['PYTHONPATH']=str(ROOT)
    p=subprocess.run([sys.executable,str(ROOT/'learning-service/learning_cli.py'),'--state-dir',str(state),*args],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
    assert p.returncode==(0 if ok else 2),p.stderr
    return json.loads(p.stdout)

def test_real_cli_mark_propose_review_export_report(tmp_path):
    state=tmp_path/'private';case=cli(state,'mark','0123456789abcdef')
    proposal=cli(state,'propose',case['case_id'],'--recipe','constraint_preservation')
    assert proposal['state']=='draft' and proposal['category']=='code'
    lid=proposal['lesson_id'];cli(state,'review',lid,'--decision','approve',ok=False)
    cli(state,'export',lid,ok=False)
    cli(state,'review',lid,'--decision','approve','--owner-confirmed')
    exported=cli(state,'export',lid);packet=json.loads(Path(exported['path']).read_text())
    assert packet['deployment_authorized'] is False and packet['synthetic_only']
    assert '0123456789abcdef' not in json.dumps(packet)
    assert all('id' in c and 'messages' in c and 'rubric' in c for c in packet['cases'])
    report=cli(state,'report');assert report['cases']==1 and report['lessons']=={'approved':1}
    assert report['auto_apply'] is False and report['model_calls']==0
    cli(state,'review',lid,'--decision','revoke','--owner-confirmed')
    assert not Path(exported['path']).exists()
    cli(state,'export',lid,ok=False)


def test_no_normalization_or_raw_text_input(tmp_path):
    cli(tmp_path/'private','mark',' '+('a'*16),ok=False)
