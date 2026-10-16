"""Build-time pinned source fetch. No shell installer or mutable main branch."""
import hashlib,json,tarfile,urllib.request
from pathlib import Path
pin=json.loads(Path(__file__).with_name('HERMES-SOURCE.json').read_text())
dest=Path('/opt/hermes-src');dest.mkdir(exist_ok=True)
archive=dest/'source.tar.gz'
with urllib.request.urlopen('https://codeload.github.com/NousResearch/hermes-agent/tar.gz/'+pin['commit'],timeout=60) as r,archive.open('wb') as f:
    while chunk:=r.read(1024*1024):f.write(chunk)
with archive.open('rb') as f:
    if hashlib.file_digest(f,'sha256').hexdigest()!=pin['archive_sha256']:raise RuntimeError('source_checksum_mismatch')
with tarfile.open(archive) as t:t.extractall(dest,filter='data')
archive.unlink()
