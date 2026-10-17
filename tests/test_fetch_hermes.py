"""Synthetic HTTP fixtures; no live network, credentials or production state."""
import hashlib,io,tarfile,urllib.error,ssl
from email.utils import formatdate
import pytest
import fetch_hermes as f
COMMIT='a'*40
ROOT='hermes-agent-'+COMMIT

def archive(path=None):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as t:
        data=b'verified fixture';item=tarfile.TarInfo(path or ROOT+'/hello.txt');item.size=len(data);t.addfile(item,io.BytesIO(data))
    return stream.getvalue()

class Response(io.BytesIO):
    def __init__(self,data,length=None):
        super().__init__(data);self.headers={'Content-Length':str(len(data) if length is None else length)}

class Harness:
    def __init__(self,events):self.events=list(events);self.time=0;self.waits=[];self.calls=0
    def open(self,request,timeout):
        assert request.full_url.startswith('https://codeload.github.com/')
        assert 0<timeout<=60
        self.calls+=1;event=self.events.pop(0)
        if isinstance(event,Exception):raise event
        return event
    def sleep(self,seconds):self.waits.append(seconds);self.time+=seconds
    def run(self,tmp_path,data,**kw):
        pin={'repository':'https://github.com/NousResearch/hermes-agent','commit':COMMIT,'archive_sha256':hashlib.sha256(data).hexdigest()}
        return f.fetch_source(pin,tmp_path,opener=self.open,sleep=self.sleep,clock=lambda:self.time,wall=lambda:1000+self.time,jitter=lambda a,b:0,**kw)

def error(code=429,delay=None):
    headers={} if delay is None else {'Retry-After':delay}
    return urllib.error.HTTPError('https://fixture.invalid',code,'fixture',headers,None)

def test_429_then_success(tmp_path):
    data=archive();h=Harness([error(delay='7'),Response(data)])
    path=h.run(tmp_path,data)
    assert (path/'hello.txt').read_bytes()==b'verified fixture'
    assert h.calls==2 and h.waits==[7]
    assert len(list(tmp_path.iterdir()))==1

def test_exhaustion_cleans_partial(tmp_path):
    h=Harness([error() for _ in range(5)])
    with pytest.raises(RuntimeError,match='retries_exhausted'):h.run(tmp_path,archive())
    assert h.calls==5 and h.waits==[2,4,8,16]
    assert not list(tmp_path.iterdir())

def test_partial_restarts_from_empty_file(tmp_path):
    data=archive();h=Harness([Response(data[:12],len(data)),Response(data)])
    assert h.run(tmp_path,data).is_dir()
    assert h.calls==2 and h.waits==[2]

def test_wrong_checksum_not_retried_or_extracted(tmp_path):
    h=Harness([Response(b'wrong archive')])
    with pytest.raises(RuntimeError,match='checksum_mismatch'):h.run(tmp_path,archive())
    assert h.calls==1 and not list(tmp_path.iterdir())

@pytest.mark.parametrize('code',[408,500,502,503,504])
def test_transient_http(tmp_path,code):
    data=archive();h=Harness([error(code),Response(data)])
    assert h.run(tmp_path,data).is_dir()

@pytest.mark.parametrize('code',[401,403,404])
def test_permanent_http_not_retried(tmp_path,code):
    h=Harness([error(code)])
    with pytest.raises(RuntimeError,match='source_http_'+str(code)):h.run(tmp_path,archive())
    assert h.calls==1 and not h.waits

def test_retry_after_http_date(tmp_path):
    data=archive();h=Harness([error(delay=formatdate(1011,usegmt=True)),Response(data)])
    h.run(tmp_path,data);assert h.waits==[11]

def test_retry_after_larger_than_budget_stops(tmp_path):
    h=Harness([error(delay='3600')])
    with pytest.raises(RuntimeError,match='retry_after_exceeds_budget'):h.run(tmp_path,archive(),budget=20)
    assert h.calls==1 and not h.waits and not list(tmp_path.iterdir())

def test_network_timeout_then_success(tmp_path):
    data=archive();h=Harness([TimeoutError(),Response(data)])
    assert h.run(tmp_path,data).is_dir() and h.calls==2

def test_certificate_failure_never_bypassed(tmp_path):
    h=Harness([urllib.error.URLError(ssl.SSLCertVerificationError('fixture'))])
    with pytest.raises(RuntimeError,match='tls_verification_failed'):h.run(tmp_path,archive())
    assert h.calls==1 and not h.waits

def test_archive_path_traversal_rejected(tmp_path):
    data=archive(ROOT+'/../../outside');h=Harness([Response(data)])
    with pytest.raises(RuntimeError,match='unexpected_archive_path'):h.run(tmp_path,data)
    assert not list(tmp_path.iterdir())

@pytest.mark.parametrize('value',[None,'nonsense','-1','1.2'])
def test_invalid_retry_after_uses_fallback(value):assert f.retry_after(value,1000) is None

def test_invalid_pin_rejected_before_network(tmp_path):
    h=Harness([])
    with pytest.raises(ValueError):f.fetch_source({'commit':'BAD','repository':'other'},tmp_path,opener=h.open)
    assert h.calls==0
