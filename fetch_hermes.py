"""Pinned HTTPS source fetch: bounded retries, verified archive, staged extraction."""
import hashlib,http.client,json,os,random,re,ssl,tarfile,tempfile,time
import urllib.error,urllib.request
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path,PurePosixPath
RETRY_CODES={408,429,500,502,503,504}
MAX_BYTES=256*1024*1024

def retry_after(value,now):
    if value is None:return None
    value=value.strip()
    if re.fullmatch(r'[0-9]+',value):return int(value)
    try:
        date=parsedate_to_datetime(value)
        if date.tzinfo is None:date=date.replace(tzinfo=timezone.utc)
        return max(0,date.timestamp()-now)
    except (ValueError,TypeError,OverflowError):return None

def validate_pin(pin):
    if pin.get('repository')!='https://github.com/NousResearch/hermes-agent':raise ValueError('unexpected_repository')
    if not re.fullmatch(r'[0-9a-f]{40}',pin.get('commit','')):raise ValueError('invalid_commit')
    if not re.fullmatch(r'[0-9a-f]{64}',pin.get('archive_sha256','')):raise ValueError('invalid_sha256')

def extract_verified(pin,archive,dest):
    """Identical checksum/path checks for bundled and explicitly downloaded source."""
    validate_pin(pin)
    archive=Path(archive);dest=Path(dest)
    if archive.stat().st_size>MAX_BYTES:raise RuntimeError('source_size_limit')
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=pin['archive_sha256']:raise RuntimeError('source_checksum_mismatch')
    dest.mkdir(parents=True,exist_ok=True)
    root='hermes-agent-'+pin['commit'];target=dest/root
    if target.exists():raise RuntimeError('source_target_already_exists')
    with tempfile.TemporaryDirectory(prefix='.hermes-extract-',dir=dest) as stage:
        with tarfile.open(archive) as source:
            for member in source.getmembers():
                parts=PurePosixPath(member.name).parts
                if not parts or parts[0]!=root or '..' in parts:raise RuntimeError('unexpected_archive_path')
            source.extractall(stage,filter='data')
        extracted=Path(stage)/root
        if not extracted.is_dir():raise RuntimeError('missing_source_root')
        extracted.rename(target)
    return target

def fetch_source(pin,dest,*,archive_path=None,attempts=5,budget=300,opener=None,sleep=None,clock=None,wall=None,jitter=None):
    validate_pin(pin)
    if archive_path is not None:
        result=extract_verified(pin,archive_path,dest)
        print('source_bundle_verified network_requests=0',flush=True)
        return result
    if not 1<=attempts<=10 or budget<=0:raise ValueError('invalid_retry_policy')
    opener=opener or urllib.request.urlopen;sleep=sleep or time.sleep
    clock=clock or time.monotonic;wall=wall or time.time;jitter=jitter or random.uniform
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    root='hermes-agent-'+pin['commit'];target=dest/root
    if target.exists():raise RuntimeError('source_target_already_exists')
    deadline=clock()+budget
    url='https://codeload.github.com/NousResearch/hermes-agent/tar.gz/'+pin['commit']
    for attempt in range(1,attempts+1):
        remaining=deadline-clock()
        if remaining<=0:raise RuntimeError('source_download_budget_exhausted')
        fd,name=tempfile.mkstemp(prefix='.hermes-source-',suffix='.part',dir=dest)
        archive=Path(name);reason=None;server_wait=None
        try:
            with os.fdopen(fd,'wb') as output:
                request=urllib.request.Request(url,headers={'User-Agent':'Merly-Hermes-Pinned-Build/1.0','Accept':'application/octet-stream'})
                with opener(request,timeout=min(60,remaining)) as response:
                    size=0;digest=hashlib.sha256()
                    expected=response.headers.get('Content-Length')
                    expected=int(expected) if expected is not None else None
                    if expected is not None and not 0<=expected<=MAX_BYTES:raise RuntimeError('source_size_limit')
                    while True:
                        if clock()>=deadline:raise TimeoutError('download_deadline')
                        block=response.read(1024*1024)
                        if not block:break
                        size+=len(block)
                        if size>MAX_BYTES:raise RuntimeError('source_size_limit')
                        output.write(block);digest.update(block)
                    if expected is not None and size!=expected:raise http.client.IncompleteRead(b'',expected-size)
                output.flush();os.fsync(output.fileno())
            if digest.hexdigest()!=pin['archive_sha256']:raise RuntimeError('source_checksum_mismatch')
            extract_verified(pin,archive,dest)
            print('source_download_verified attempts='+str(attempt),flush=True)
            return target
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_CODES:raise RuntimeError('source_http_'+str(e.code)) from None
            reason='http_'+str(e.code);server_wait=retry_after(e.headers.get('Retry-After'),wall())
            e.close()
        except urllib.error.URLError as e:
            if isinstance(e.reason,ssl.SSLCertVerificationError):raise RuntimeError('source_tls_verification_failed') from None
            reason='network_error'
        except ssl.SSLCertVerificationError:
            raise RuntimeError('source_tls_verification_failed') from None
        except (TimeoutError,ConnectionError,http.client.IncompleteRead):reason='incomplete_or_timed_out'
        finally:archive.unlink(missing_ok=True)
        if attempt==attempts:raise RuntimeError('source_download_retries_exhausted:'+reason)
        wait=max(server_wait or 0,min(30,2**attempt)+jitter(0,1))
        if wait>=deadline-clock():raise RuntimeError('source_retry_after_exceeds_budget:'+reason)
        print('source_download_retry attempt='+str(attempt)+' reason='+reason+' wait_seconds='+str(round(wait,2)),flush=True)
        sleep(wait)
    raise RuntimeError('source_download_failed')

if __name__=='__main__':
    pin=json.loads(Path(__file__).with_name('HERMES-SOURCE.json').read_text())
    import argparse
    parser=argparse.ArgumentParser(description='Extract pinned local Hermes source; no source network fetch in builds')
    parser.add_argument('--destination',type=Path,default=Path('/opt/hermes-src'))
    args=parser.parse_args()
    bundled=Path(__file__).resolve().parent/'build-sources'/('hermes-agent-'+pin['commit']+'.tar.gz')
    fetch_source(pin,args.destination,archive_path=bundled)
