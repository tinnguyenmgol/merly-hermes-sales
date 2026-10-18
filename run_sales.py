"""Entrypoint for NEW sales resources; never edits owner's existing profile."""
import os,shutil,subprocess,sys,threading,time,tempfile
from pathlib import Path
ROOT=Path(__file__).parent


def ensure_merly_child_env(home):
    """Narrow migration for existing sales volumes; preserves model/provider/settings."""
    import hermes_yaml
    from audit_instance import check_config
    path=Path(home)/'config.yaml'
    if path.is_symlink():raise RuntimeError('sales_config_symlink_not_supported')
    before=path.read_bytes()
    config=hermes_yaml.safe_load(before.decode())
    check_config(config)
    server=config['mcp_servers']['merly']
    required={'HARAVAN_ACCESS_TOKEN':'${HARAVAN_ACCESS_TOKEN}','CATALOG_CACHE_PATH':'${CATALOG_CACHE_PATH}'}
    previous=server.get('env',{})
    if not isinstance(previous,dict) or set(previous)-set(required):raise RuntimeError('unexpected_merly_child_environment')
    if any(previous[k]!=required[k] for k in previous):raise RuntimeError('conflicting_merly_child_environment')
    if previous==required:return False
    server['env']=required
    after=hermes_yaml.safe_dump(config,sort_keys=False,allow_unicode=True).encode()
    if hermes_yaml.safe_load(after.decode())!=config:raise RuntimeError('sales_config_roundtrip_failed')
    def write(target,data):
        fd,name=tempfile.mkstemp(prefix='.merly-config-',dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.replace(name,target)
        finally:Path(name).unlink(missing_ok=True)
    if path.read_bytes()!=before:raise RuntimeError('sales_config_changed_during_migration')
    write(path.with_name('config.before-merly-env-'+str(time.time_ns())+'.yaml'),before)
    write(path,after)
    if hermes_yaml.safe_load(path.read_text())!=config:raise RuntimeError('sales_config_readback_failed')
    return True

def main():
    role=os.getenv('PILOT_ROLE','hermes')
    if role=='gateway':
        if os.getenv('HARAVAN_ACCESS_TOKEN'):raise RuntimeError('gateway_must_not_hold_haravan_token')
        os.execvp(sys.executable,[sys.executable,'-m','gunicorn','--no-control-socket','--bind','0.0.0.0:8080','--workers','1','--threads','4','--timeout','60','sales_gateway:application'])
    if role!='hermes':raise RuntimeError('invalid_role')
    home=Path(os.environ['HERMES_HOME']).resolve()
    if home.name in ('default','data','.hermes') or str(home).startswith('/opt/data'):raise RuntimeError('dedicated_sales_home_required')
    if len(os.getenv('API_SERVER_KEY',''))<32:raise RuntimeError('new_sales_api_key_required')
    if not os.getenv('HERMES_SALES_API_BASE'):raise RuntimeError('sales_listener_base_required')
    home.mkdir(parents=True,exist_ok=True)
    if not (home/'config.yaml').exists():shutil.copy2(ROOT/'hermes-config.template.json',home/'config.yaml')
    if not (home/'SOUL.md').exists():shutil.copy2(ROOT/'SYSTEM-PROMPT.md',home/'SOUL.md')
    ensure_merly_child_env(home)
    os.environ.setdefault('MERLY_MCP_PYTHON',sys.executable)
    def audit():
        return subprocess.run([sys.executable,str(ROOT/'audit_instance.py')],cwd=home).returncode==0
    if not audit():raise RuntimeError('startup_audit_failed')
    def refresh():
        while True:
            time.sleep(12*3600)
            if not audit():Path(os.environ['HERMES_SALES_ATTESTATION']).unlink(missing_ok=True)
    threading.Thread(target=refresh,daemon=True).start()
    import signal
    proc=subprocess.Popen([sys.executable,'-m','hermes_cli.main','gateway','run'],cwd=home)
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda signum,frame:proc.send_signal(signum))
    raise SystemExit(proc.wait())
if __name__=='__main__':main()
