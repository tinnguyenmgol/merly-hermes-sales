import copy,json,shlex,sys,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from test_runtime_copy_smoke import included

def test_optional_compose_preserves_existing_stack_and_storage():
    base=json.loads((ROOT/'compose.hermes.json').read_text());learning=json.loads((ROOT/'compose.hermes-learning.json').read_text());reconstructed=copy.deepcopy(learning)
    added=reconstructed['services'].pop('learning-review');reconstructed['volumes'].pop('learning-review-data')
    env=reconstructed['services']['sales-gateway']['environment'];env.pop('MERLY_LEARNING_ENABLED');env.pop('MERLY_LEARNING_INGEST_TOKEN')
    assert reconstructed==base
    assert not added.get('ports') and added['read_only'] and added['cap_drop']==['ALL']
    assert added['volumes']==['learning-review-data:/data'] and added['mem_limit']=='128m'
    assert set(added['environment'])=={'MERLY_LEARNING_INGEST_TOKEN','MERLY_LEARNING_STATE_DIR'}
    for name in ('hermes-sales','sales-gateway'):
        assert not any('learning-review-data' in v for v in learning['services'][name]['volumes'])
    assert 'MERLY_LEARNING_INGEST_TOKEN' not in learning['services']['hermes-sales']['environment']


def test_actual_learning_copy_imports_in_isolated_interpreter(tmp_path):
    for line in (ROOT/'Dockerfile.learning').read_text().splitlines():
        if line.startswith('COPY '):
            for src in shlex.split(line)[1:-1]:
                assert included(src) and (ROOT/src).is_file()
                shutil.copy2(ROOT/src,tmp_path/Path(src).name)
    code="import sys;sys.path.insert(0,sys.argv[1]);import learning_contract,learning_store,learning_server,learning_cli,recipes;print('LEARNING_IMAGE_IMPORTS_OK')"
    p=subprocess.run([sys.executable,'-I','-c',code,str(tmp_path)],cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert p.returncode==0,p.stderr
    assert p.stdout.strip()=='LEARNING_IMAGE_IMPORTS_OK'
