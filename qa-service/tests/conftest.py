import sys,socket
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    original=socket.socket.connect
    def checked(self,address):
        if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):return original(self,address)
        raise AssertionError('offline_test_forbids_external_network')
    monkeypatch.setattr(socket.socket,'connect',checked)
