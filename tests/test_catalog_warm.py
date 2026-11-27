"""Catalog stays fresh in the stock-probe process (root cause of "một phần kho")."""
import time,threading
import pytest
import merly_tools,stock_probe
cat=merly_tools.catalog

def test_probe_process_keeps_catalog_warm(monkeypatch):
    started=[]
    monkeypatch.setattr(cat,'start',lambda:started.append(True))
    class Dummy:
        def serve_forever(self):pass
    monkeypatch.setattr(stock_probe,'make_server',lambda *a,**k:Dummy())
    stock_probe.start()
    assert started==[True]

class Clock:
    """Fake monotonic clock for the catalog module only: the test never depends on the runner's uptime
    (time.monotonic() counts from boot; a GitHub runner can start the suite < 60 s after boot)."""
    def __init__(self, now): self.now = float(now)
    def monotonic(self): return self.now


@pytest.mark.parametrize('runner_uptime', [10, 45, 60, 120, 3400])
@pytest.mark.parametrize('age,since_attempt,expect', [
    (200, None, False),   # still fresh: no refresh
    (250, None, True),    # past REFRESH_AFTER, last attempt an hour ago: refresh before the 300 s window closes
    (250, 61, True),      # past REFRESH_AFTER, last attempt outside the 60 s cooldown: refresh
    (250, 60, False),     # cooldown still in force (strictly > 60 s required)
    (250, 30, False),     # cooldown still in force
])
def test_refresh_starts_before_freshness_window_closes(monkeypatch, runner_uptime, age, since_attempt, expect):
    # The real clock is moved to `runner_uptime` too, to show it no longer matters.
    monkeypatch.setattr(time, 'monotonic', lambda base=time.monotonic() - runner_uptime, real=time.monotonic: real() - base)
    clock = Clock(1_000_000)          # the catalog's own clock, far from any boot time
    monkeypatch.setattr(cat, 'time', clock)
    synced = threading.Event()
    monkeypatch.setattr(cat, 'sync', lambda: synced.set())
    monkeypatch.setattr(cat, 'UPDATED', clock.now - age)
    monkeypatch.setattr(cat, 'LOADING', False)
    monkeypatch.setattr(cat, 'ATTEMPT', clock.now - (since_attempt if since_attempt is not None else 3600))
    monkeypatch.setattr(cat, 'PRODUCTS', [])
    cat.snapshot()
    assert synced.wait(1 if expect else 0.2) is expect
    assert cat.LOADING is expect      # a refresh in flight blocks a second one
    assert cat.REFRESH_AFTER < 300
