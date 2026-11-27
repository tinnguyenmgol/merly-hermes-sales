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

@pytest.mark.parametrize('age,expect',[(200,False),(250,True)])
def test_refresh_starts_before_freshness_window_closes(monkeypatch,age,expect):
    synced=threading.Event()
    monkeypatch.setattr(cat,'sync',lambda:synced.set())
    monkeypatch.setattr(cat,'UPDATED',time.monotonic()-age);monkeypatch.setattr(cat,'LOADING',False);monkeypatch.setattr(cat,'ATTEMPT',0.0)
    monkeypatch.setattr(cat,'PRODUCTS',[])
    cat.snapshot()
    assert synced.wait(1 if expect else 0.2) is expect
    assert cat.REFRESH_AFTER<300
