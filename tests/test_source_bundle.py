"""Local source bundle: no network fallback, original upstream checksum retained."""
import hashlib,io,json,tarfile
from pathlib import Path
import pytest
import fetch_hermes as f
ROOT=Path(__file__).resolve().parents[1]
COMMIT='a'*40

def fixture(tmp_path):
    p=tmp_path/'fixture.tar.gz'
    with tarfile.open(p,'w:gz') as archive:
        info=tarfile.TarInfo('hermes-agent-'+COMMIT+'/hello');data=b'offline-fixture';info.size=len(data);archive.addfile(info,io.BytesIO(data))
    return p,{'repository':'https://github.com/NousResearch/hermes-agent','commit':COMMIT,'archive_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def forbidden(*a,**k):raise AssertionError('local build must not contact network')

def test_bundle_extracts_with_network_forbidden(tmp_path,monkeypatch):
    p,pin=fixture(tmp_path);monkeypatch.setattr(f.urllib.request,'urlopen',forbidden)
    target=f.fetch_source(pin,tmp_path/'out',archive_path=p,opener=forbidden)
    assert (target/'hello').read_bytes()==b'offline-fixture' and p.exists()

def test_corrupt_bundle_fails_without_fallback(tmp_path,monkeypatch):
    p,pin=fixture(tmp_path);p.write_bytes(b'corrupted');monkeypatch.setattr(f.urllib.request,'urlopen',forbidden)
    with pytest.raises(RuntimeError,match='checksum_mismatch'):f.fetch_source(pin,tmp_path/'out',archive_path=p)
    assert not (tmp_path/'out').exists()

def test_missing_bundle_fails_without_fallback(tmp_path,monkeypatch):
    p,pin=fixture(tmp_path);p.unlink();monkeypatch.setattr(f.urllib.request,'urlopen',forbidden)
    with pytest.raises(FileNotFoundError):f.fetch_source(pin,tmp_path/'out',archive_path=p)

def test_repeat_extract_to_existing_target_refused(tmp_path):
    p,pin=fixture(tmp_path);f.fetch_source(pin,tmp_path/'out',archive_path=p)
    with pytest.raises(RuntimeError,match='target_already_exists'):f.fetch_source(pin,tmp_path/'out',archive_path=p)

def test_actual_upstream_bundle_matches_original_pin():
    pin=json.loads((ROOT/'HERMES-SOURCE.json').read_text())
    p=ROOT/'build-sources'/('hermes-agent-'+pin['commit']+'.tar.gz')
    assert p.is_file() and p.stat().st_size<100*1024*1024
    with p.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==pin['archive_sha256']
    assert 'COPY build-sources/ ./build-sources/' in (ROOT/'Dockerfile.hermes').read_text()
