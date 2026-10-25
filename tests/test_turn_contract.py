"""Scripted contract checks, not semantic model quality scores."""
import copy,json,time
from datetime import datetime,timezone
import pytest
import turn_contract as t,hermes_client as c,state
from agent_answer import present
from test_client import approved,responses
from test_gateway import configured,call
from test_stock_options import source

def final(text):
    d=responses();d['output'][-1]['content'][0]['text']=text;return d

def test_vietnam_clock_uses_utc_rollover_not_customer_text():
    raw=t.runtime_context(datetime(2026,10,24,18,tzinfo=timezone.utc));d=json.loads(raw.rsplit('\n',1)[-1])
    assert d['local_date']=='2026-10-25' and d['weekday_vi']=='Chủ nhật' and d['utc_offset']=='+07:00'
    with pytest.raises(ValueError):t.runtime_context(datetime(2026,10,25))

@pytest.mark.parametrize('text',['<｜DSML｜ calls>bad','<|DSML| invoke>bad','<tool_call>bad','mcp__merly__search_products'])
def test_protocol_never_reaches_reply(text):
    out=present(final(text),'resp_fixture',time.time())
    assert out['answer_mode']=='protocol_guard' and out['_guard_reasons']==['protocol_text'] and text not in out['reply']

def test_one_repair_preserves_raw_input_and_only_delivered_history(approved,monkeypatch):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,p):
        seen.append(copy.deepcopy(p));return final('<｜DSML｜ calls>broken') if len(seen)==1 else final('Bạn thích gót vừa hay cao hơn để mình tìm tiếp?')
    monkeypatch.setattr(c,'request',request)
    out=c.chat('size 40 trắng cao cao tí','merly-sales:web:recovery')
    assert len(seen)==2 and out['_repair_attempts']==1 and out['answer_mode']=='native'
    assert seen[0]['input']==seen[1]['input']=='size 40 trắng cao cao tí'
    assert seen[0]['conversation_history']==seen[1]['conversation_history']==[]
    assert 'TURN_VALIDATION_FEEDBACK_JSON (execution feedback,' in seen[1]['instructions']
    assert '<｜DSML｜ calls>broken' not in seen[1]['instructions']
    assert out['_recovered_reasons']==['protocol_text']
    db=state.database()
    try:assert db.execute('SELECT count(*) FROM calls').fetchone()[0]==1
    finally:db.close()

@pytest.mark.parametrize('bad',['<｜DSML｜ calls>still broken','Size này còn hàng.','Giá 399.000đ nhé.'])
def test_bad_second_answer_is_never_accepted(approved,monkeypatch,bad):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,p):seen.append(p);return final('<｜DSML｜ calls>broken' if len(seen)==1 else bad)
    monkeypatch.setattr(c,'request',request);out=c.chat('búp bê 42','merly-sales:web:bad')
    assert len(seen)==2 and out['answer_mode']=='protocol_guard' and bad not in out['reply']

@pytest.mark.parametrize('failure',['budget','deadline','disabled'])
def test_repair_bounds_never_start_an_extra_call(approved,monkeypatch,failure):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');a=present(final('<｜DSML｜ calls>x'),'resp_fixture',time.time())
    if failure=='budget':monkeypatch.setattr(state,'reserve_checked',lambda sid:{'available':False})
    if failure=='disabled':monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','0')
    deadline=time.monotonic()+(1 if failure=='deadline' else 50)
    out=t.recover(a,{'instructions':'x'},'test',time.time(),deadline,lambda *a:pytest.fail('must not call'),present)
    assert out['_repair_attempts']==0

def test_transport_failure_never_automatically_retried(approved,monkeypatch):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');monkeypatch.setattr(c,'audit',lambda:True);calls=[]
    def request(*a):calls.append(a);raise c.HermesError('hermes_timeout')
    monkeypatch.setattr(c,'request',request)
    with pytest.raises(c.HermesError,match='hermes_timeout'):c.chat('hello','x')
    assert len(calls)==1

@pytest.mark.parametrize('bad',['yes','','true','2'])
def test_invalid_settings_fail_before_model(approved,monkeypatch,bad):
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED',bad)
    monkeypatch.setattr(c,'audit',lambda:pytest.fail('must fail before requests'))
    with pytest.raises(c.HermesError,match='invalid_agent_settings'):c.chat('hi','x')

def test_recovery_audit_is_visible_without_raw_text(configured,monkeypatch,caplog):
    import logging
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,p):
        seen.append(p);return final('<｜DSML｜ calls>UNDELIVERED_PRIVATE_SENTINEL') if len(seen)==1 else final('Bạn thích gót vừa hay cao hơn?')
    monkeypatch.setattr(c,'request',request)
    with caplog.at_level(logging.INFO,logger='merly.gateway'):out=call('RAW_PRIVATE_USER_SENTINEL')
    assert out['status'].startswith('200') and out['body']['answer_mode']=='native'
    assert 'repair_attempts' in caplog.text and 'history_messages' in caplog.text
    assert 'RAW_PRIVATE_USER_SENTINEL' not in caplog.text and 'UNDELIVERED_PRIVATE_SENTINEL' not in caplog.text
    assert out['body']['diagnostic_id'] in caplog.text
    assert not any(k.startswith('_') for k in out['body'])

def test_recovery_keeps_verified_cards_in_the_same_turn(source,approved,monkeypatch):
    from test_integrated_stock_v2 import wire,fresh
    monkeypatch.setenv('MERLY_AGENT_REPAIR_ENABLED','1');monkeypatch.setattr(c,'audit',lambda:True);seen=[]
    def request(path,p):
        seen.append(p)
        if len(seen)>1:return final('Bạn thích lựa chọn nào trong các thẻ đã kiểm tra?')
        data=final('Giá 999.000đ');data['output']=wire(fresh())[:2]+data['output'];return data
    monkeypatch.setattr(c,'request',request)
    out=c.chat('tra mẫu theo size đã chốt','merly-sales:web:cards')
    assert out['answer_mode']=='native' and out['_repair_attempts']==1
    assert out['stock_options']['complete'] and len(out['stock_options']['variants'])==20
    assert out['_recovered_reasons']==['unsupported_stock_claim']
