"""Offline planner only; no scheduler/model/live QA calls."""
from collections import Counter
from datetime import date,timedelta
from pathlib import Path
import json,stat,subprocess,sys
import pytest
from qa_plans import daily

def test_daily_budget_and_rotation_over_full_year():
    covered=set();previous=set()
    for offset in range(366):
        p=daily.build(date(2026,1,1)+timedelta(days=offset))
        assert p['max_runs']==2 and p['max_messages']==10
        assert p['scheduled'] is False and p['auto_apply'] is False and p['model_calls']==0
        cases=[c for s in p['sessions'] for c in s['cases']]
        assert len(cases)==10 and len({c['id'] for c in cases})==10
        assert Counter(c['group'] for c in cases)=={'regression':4,'rotation':4,'variation':2}
        for s in p['sessions']:
            assert len(s['qa_arguments']['messages'])==5
            assert s['qa_arguments']['test_data_only'] is True
            assert all(1<=len(m)<=1000 for m in s['qa_arguments']['messages'])
        selected={c['id'] for c in cases if c['group']=='rotation'}
        assert not previous&selected
        covered|=selected;previous=selected
    assert len(covered)==11

def test_same_day_deterministic_and_not_mutable_global():
    day=date(2026,10,30);a=daily.build(day);b=daily.build(day)
    assert a==b
    a['sessions'][0]['cases'][0]['message']='changed'
    assert daily.build(day)==b

@pytest.mark.parametrize('bad',['2026-1-01','2026-10-32','20261030','today','2026-10-30 '])
def test_literal_date_format_is_not_silently_normalized(bad):
    with pytest.raises(ValueError):daily.parse_day(bad)

def test_policy_change_blocks_plan_until_human_review(tmp_path):
    for f in daily.POLICY_FILES:
        p=tmp_path/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((daily.ROOT/f).read_bytes())
    p=tmp_path/daily.POLICY_FILES[0];p.write_bytes(p.read_bytes()+b' ')
    with pytest.raises(ValueError,match='policy_changed_requires_review'):daily.build(date(2026,10,30),tmp_path)

def test_claim_is_once_per_local_day_and_is_not_execution_proof(tmp_path,monkeypatch):
    day=date(2026,10,30);monkeypatch.setattr(daily,'today',lambda:day)
    daily.claim(day,tmp_path/'state')
    with pytest.raises(FileExistsError):daily.claim(day,tmp_path/'state')
    with pytest.raises(ValueError):daily.claim(day-timedelta(days=1),tmp_path/'state')
    p=tmp_path/'state'/f'{day}.json'
    assert json.loads(p.read_text())['not_proof_of_execution'] is True
    assert stat.S_IMODE(p.stat().st_mode)==0o600

def test_cli_actually_outputs_valid_tool_arguments():
    p=subprocess.run([sys.executable,'-m','qa_plans.daily','--date','2026-10-30'],cwd=daily.ROOT,capture_output=True,text=True,check=True)
    plan=json.loads(p.stdout)
    assert plan['local_date']=='2026-10-30' and len(plan['sessions'])==2
    assert sum(len(s['qa_arguments']['messages']) for s in plan['sessions'])==10
