import asyncio,json,time
import pytest
from qa_core import Manager,Ledger,Rejected,validate_messages,safe_result
from qa_transport import TransportError
class FakeSession:
    calls=[]
    def __init__(self,deadline):self.cookie='C'*43;self.csrf='a'*64;self.number=0;self.deadline=deadline
    def bootstrap(self):pass
    def send(self,message):
        self.number+=1;self.calls.append(message)
        if message=='FAIL':return 503,{'error_category':'response_incomplete','diagnostic_id':'f'*16,'secret':'PRIVATE_RAW_SENTINEL'}
        return 200,{'reply':'ACK '+self.cookie+' '+self.csrf,'diagnostic_id':'a'*16}

def run(coro):return asyncio.run(coro)
async def settled(manager):
    if manager.tasks:await asyncio.gather(*list(manager.tasks))


def test_same_session_multi_turn_result_redacts_secrets_and_persists_only_usage(tmp_path):
    async def case():
        FakeSession.calls=[];manager=Manager(Ledger(tmp_path),True,FakeSession)
        started=await manager.start(['FIRST','SECOND'],True);await settled(manager)
        result=manager.result(started['run_id'])
        assert result['state']=='completed' and len(result['turns'])==2
        assert FakeSession.calls==['FIRST','SECOND']
        assert all('C'*43 not in r['reply'] and 'a'*64 not in r['reply'] for r in result['turns'])
        assert not any(k.startswith('_') for k in result)
        assert b'FIRST' not in manager.ledger.path.read_bytes() and b'ACK' not in manager.ledger.path.read_bytes()
        assert manager.ledger.path.stat().st_mode&0o777==0o600
    run(case())


def test_failure_stops_without_retry_and_cooldown_survives_restart(tmp_path):
    async def case():
        FakeSession.calls=[];manager=Manager(Ledger(tmp_path),True,FakeSession)
        start=await manager.start(['FIRST','FAIL','NEVER_SEND'],True);await settled(manager)
        result=manager.result(start['run_id'])
        assert result['state']=='failed' and FakeSession.calls==['FIRST','FAIL']
        assert result['turns'][-1]['diagnostic_id']=='f'*16
        assert 'PRIVATE_RAW_SENTINEL' not in json.dumps(result)
        restarted=Manager(Ledger(tmp_path),True,FakeSession)
        with pytest.raises(Rejected) as e:await restarted.start(['NEW'],True)
        assert e.value.code=='qa_busy_or_cooldown'
    run(case())


def test_daily_reservation_survives_service_restart(tmp_path):
    async def case():
        for i in range(10):
            manager=Manager(Ledger(tmp_path),True,FakeSession)
            await manager.start(['ONE'],True);await settled(manager)
        manager=Manager(Ledger(tmp_path),True,FakeSession)
        with pytest.raises(Rejected) as e:await manager.start(['ELEVENTH'],True)
        assert e.value.code=='qa_daily_budget'
    run(case())

@pytest.mark.parametrize('messages,consent',[([],True),(['x']*6,True),(['x'*1001],True),([None],True),([' '],True),(['x'],False),(['x'],1),('x',True)])
def test_invalid_calls_never_consume_quota(tmp_path,messages,consent):
    manager=Manager(Ledger(tmp_path),True,FakeSession)
    with pytest.raises(Rejected):run(manager.start(messages,consent))
    with manager.ledger.db() as db:assert db.execute('SELECT count(*) FROM usage').fetchone()[0]==0


def test_no_live_approval_and_no_result_token_normalization(tmp_path):
    manager=Manager(Ledger(tmp_path),False,FakeSession)
    with pytest.raises(Rejected) as e:run(manager.start(['ONE'],True))
    assert e.value.code=='live_testing_not_approved'
    with pytest.raises(Rejected):manager.result(' '+('a'*32))


def test_reply_redaction_happens_before_truncation_boundary():
    session=FakeSession(time.monotonic()+1)
    reply='x'*5980+session.cookie+' end'
    result=safe_result(200,{'reply':reply},1,session)
    assert 'C'*10 not in result['reply'] and '[REDACTED]' in result['reply']


def test_expired_result_is_removed_from_memory(tmp_path):
    async def case():
        manager=Manager(Ledger(tmp_path),True,FakeSession)
        start=await manager.start(['ONE'],True);await settled(manager)
        manager.jobs[start['run_id']]['_created']-=901
        with pytest.raises(Rejected):manager.result(start['run_id'])
        assert start['run_id'] not in manager.jobs
    run(case())


def test_two_service_instances_cannot_reserve_parallel_jobs(tmp_path):
    first=Ledger(tmp_path);second=Ledger(tmp_path)
    first.reserve(5,'first')
    with pytest.raises(Rejected) as e:second.reserve(1,'second')
    assert e.value.code=='qa_busy_or_cooldown'


def test_no_symlink_to_another_service_database(tmp_path):
    other=tmp_path/'other.sqlite3';other.write_bytes(b'UNTOUCHED')
    (tmp_path/'qa-limits.sqlite3').symlink_to(other)
    with pytest.raises(Rejected):Ledger(tmp_path)
    assert other.read_bytes()==b'UNTOUCHED'


def test_raise_daily_limit_preserves_old_usage_and_allows_only_remaining_slots(tmp_path,monkeypatch):
    import qa_core as core
    assert core.MAX_RUNS_DAY==10 and core.MAX_MESSAGES==5 and core.MAX_MESSAGES_DAY==50
    ledger=Ledger(tmp_path)
    # Existing day's three full runs under the old deployed limit.
    with monkeypatch.context() as old:
        old.setattr(core,'MAX_RUNS_DAY',3);old.setattr(core,'MAX_MESSAGES_DAY',15)
        for i in range(3):
            job=f'{i:032x}';ledger.reserve(5,job);ledger.release(job)
        with pytest.raises(Rejected,match='qa_daily_budget'):ledger.reserve(1,'f'*32)
    # Reopening the SAME volume under the raised limit does not reset counters.
    restarted=Ledger(tmp_path)
    for i in range(3,10):
        job=f'{i:032x}';restarted.reserve(5,job);restarted.release(job)
    with restarted.db() as db:
        assert db.execute('SELECT runs,turns FROM usage').fetchall()==[(10,50)]
    with pytest.raises(Rejected,match='qa_daily_budget'):restarted.reserve(1,'e'*32)
    with restarted.db() as db:
        assert db.execute('SELECT runs,turns FROM usage').fetchall()==[(10,50)]
