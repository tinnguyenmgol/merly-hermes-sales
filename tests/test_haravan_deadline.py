"""Deadline propagation with local byte responses only; no Haravan requests."""
import io,time
import pytest
import merly_tools
h=merly_tools.h

def test_nested_deadline_caps_transport_and_resets(monkeypatch):
    monkeypatch.setenv('HARAVAN_ACCESS_TOKEN','synthetic-test-token')
    monkeypatch.setattr(h.time,'monotonic',lambda:100.0);timeouts=[]
    class Local:
        def open(self,req,timeout):timeouts.append(timeout);return io.BytesIO(b'{"products":[]}')
    monkeypatch.setattr(h.urllib.request,'build_opener',lambda *a:Local())
    with h.request_deadline(104):
        with h.request_deadline(110):assert h.get('products',{})=={'products':[]}
        assert h._REQUEST_DEADLINE.get()==104
    assert h._REQUEST_DEADLINE.get() is None
    h.get('products',{})
    assert timeouts==[4,12]

def test_expired_deadline_never_opens_network(monkeypatch):
    monkeypatch.setattr(h.time,'monotonic',lambda:100.0)
    monkeypatch.setattr(h.urllib.request,'build_opener',lambda *a:pytest.fail('network forbidden'))
    with h.request_deadline(99):
        with pytest.raises(h.HaravanError,match='request_budget_exceeded'):h.get('products',{})
    assert h._REQUEST_DEADLINE.get() is None

@pytest.mark.parametrize('bad',[True,float('nan'),float('inf'),'100'])
def test_invalid_deadline_not_coerced(bad):
    with pytest.raises(h.HaravanError,match='invalid_request_deadline'):
        with h.request_deadline(bad):pytest.fail('must reject')

def test_exception_does_not_leak_deadline():
    with pytest.raises(RuntimeError):
        with h.request_deadline(time.monotonic()+5):raise RuntimeError('fixture')
    assert h._REQUEST_DEADLINE.get() is None

def test_reused_worker_has_no_deadline_from_previous_request():
    from concurrent.futures import ThreadPoolExecutor
    def first():
        with h.request_deadline(time.monotonic()+5):return h._REQUEST_DEADLINE.get() is not None
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(first).result()
        assert pool.submit(h._REQUEST_DEADLINE.get).result() is None
