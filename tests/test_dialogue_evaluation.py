"""Scripted contract checks, not semantic model quality scores."""
import json,sys
from pathlib import Path
import pytest
import evaluate_dialogue as e

def test_twenty_cases_are_eval_only():
    cases=e.cases();assert len(cases)==20 and len({r['id'] for r in cases})==20
    assert sum(len(r['messages']) for r in cases)==43
    assert all(r['rubric'] and r['semantic_result']=='requires_real_model_and_review' for r in cases)
    root=Path(e.__file__).parent
    assert 'dialogue-cases.json' not in (root/'hermes_client.py').read_text()
    assert 'dialogue-cases.json' not in (root/'merly_tools.py').read_text()

def test_dry_run_never_calls_network(monkeypatch,capsys):
    monkeypatch.setattr(sys,'argv',['evaluate_dialogue.py'])
    monkeypatch.setattr(e.urllib.request,'build_opener',lambda *a:pytest.fail('network forbidden'))
    e.main();out=json.loads(capsys.readouterr().out)
    assert out['network_calls']==0 and out['semantic_evaluation']=='NOT_RUN'

@pytest.mark.parametrize('args',[['--case','not-a-case'],['--live']])
def test_requires_explicit_valid_evaluation_scope(monkeypatch,args):
    monkeypatch.setattr(sys,'argv',['evaluate_dialogue.py']+args)
    with pytest.raises(SystemExit) as exc:e.main()
    assert exc.value.code==2

def test_live_cannot_overwrite_existing_file(monkeypatch,tmp_path):
    p=tmp_path/'keep.json';p.write_text('KEEP')
    monkeypatch.setattr(sys,'argv',['evaluate_dialogue.py','--live','--out',str(p)])
    with pytest.raises(FileExistsError):e.main()
    assert p.read_text()=='KEEP'
