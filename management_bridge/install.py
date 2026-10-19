"""Operator-run install into the confirmed active management home, never sales."""
import copy,hashlib,json,os,sys,tempfile,time,urllib.request
from pathlib import Path
SOURCE_COMMIT='7ede5b0ebf25eaf06b0abf1aa3b43f939c25a4ea'
HASHES={'reader.py': 'ed5f6b9a411c793e35cdd0cd306521c1f676b1b47558fd6625f99209cb1a9437', 'server.py': 'c8820ad002510d33b10970363e4c22b9e51d2a0861ccfb9e847aec1f2350c42c'}
NAME='merly_coolify_logs'

def merge(config,python,script):
    if not isinstance(config,dict):raise ValueError('invalid_config')
    c=copy.deepcopy(config);servers=c.setdefault('mcp_servers',{})
    if not isinstance(servers,dict):raise ValueError('invalid_mcp_config')
    previous=set(servers)
    entry={'command':python,'args':[script],'env':{'COOLIFY_DIAGNOSTICS_TOKEN':'${COOLIFY_DIAGNOSTICS_TOKEN}'},'trust':'untrusted','timeout':20,'tools':{'include':['recent_hermes_deployments','hermes_build_log']}}
    if NAME in servers and (servers[NAME].get('command')!=python or servers[NAME].get('args')!=[script]):raise ValueError('existing_server_conflict')
    if NAME in c.get('agent',{}).get('disabled_toolsets',[]):raise ValueError('server_explicitly_disabled')
    platforms=c.get('platform_toolsets',{})
    if not isinstance(platforms,dict):raise ValueError('invalid_platform_config')
    raw=platforms.get('telegram')
    if raw is not None:
        if not isinstance(raw,list) or any(not isinstance(v,str) for v in raw):raise ValueError('telegram_policy_needs_review')
        if 'no_mcp' in raw:raise ValueError('telegram_mcp_explicitly_disabled')
        explicit=any(v in previous or (v.startswith('mcp-') and v[4:] in previous) for v in raw)
        # Keep all existing choices; do not accidentally narrow auto-enabled servers.
        if explicit and NAME not in raw:raw.append(NAME)
    servers[NAME]=entry
    return c

def atomic(path,data,mode=0o600,preserve_owner=False):
    owner=path.stat() if preserve_owner and path.exists() else None
    fd,temp=tempfile.mkstemp(prefix='.coolify-mcp-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            os.fchmod(f.fileno(),mode)
            if owner is not None:
                current=os.fstat(f.fileno())
                if (current.st_uid,current.st_gid)!=(owner.st_uid,owner.st_gid):os.fchown(f.fileno(),owner.st_uid,owner.st_gid)
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:Path(temp).unlink(missing_ok=True)

def install(home,python,loads,dumps,download):
    home=Path(home).resolve();config=home/'config.yaml'
    if config.is_symlink():raise ValueError('config_symlink_not_supported')
    original=config.read_bytes() if config.exists() else b''
    before=loads(original.decode()) if original else {}
    directory=home/'integrations/coolify-diagnostics'
    if not directory.resolve().is_relative_to(home):raise ValueError('integration_outside_home')
    updated=merge(before,python,str(directory/'server.py'))
    payload={}
    for name,expected in HASHES.items():
        data=download(name)
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('download_checksum_mismatch')
        compile(data,name,'exec');payload[name]=data
    serialized=dumps(updated).encode()
    if loads(serialized.decode())!=updated:raise ValueError('config_roundtrip_failed')
    directory.mkdir(parents=True,exist_ok=True,mode=0o711)
    for name,data in payload.items():atomic(directory/name,data,mode=0o644)
    if (config.read_bytes() if config.exists() else b'')!=original:raise ValueError('config_changed_retry')
    backup=home/'config-backups/coolify-diagnostics'
    if not backup.resolve().is_relative_to(home):raise ValueError('backup_outside_home')
    backup.mkdir(parents=True,exist_ok=True,mode=0o700)
    atomic(backup/('config-'+str(time.time_ns())+'.yaml'),original)
    atomic(config,serialized,preserve_owner=True)
    if loads(config.read_text())!=updated:raise ValueError('config_readback_failed')
    return {'status':'INSTALLED','tool_names':updated['mcp_servers'][NAME]['tools']['include'],'token_printed':False,'reload_required':True}

def main():
    from hermes_constants import get_hermes_home
    import hermes_yaml
    from mcp.server import Server
    import inspect
    home=get_hermes_home().resolve()
    if str(home)!='/opt/data':raise ValueError('not_confirmed_management_home')
    if not os.getenv('COOLIFY_DIAGNOSTICS_TOKEN','').strip():raise ValueError('runtime_token_missing')
    if 'on_list_tools' not in inspect.signature(Server).parameters:raise ValueError('mcp_sdk2_required_no_packages_changed')
    def download(name):
        url='https://raw.githubusercontent.com/tinnguyenmgol/merly-hermes-sales/'+SOURCE_COMMIT+'/management_bridge/'+name
        with urllib.request.urlopen(url,timeout=20) as r:data=r.read(100001)
        if len(data)>100000:raise ValueError('download_size_limit')
        return data
    result=install(home,sys.executable,hermes_yaml.safe_load,lambda v:hermes_yaml.safe_dump(v,sort_keys=False,allow_unicode=True),download)
    print(json.dumps(result))
if __name__=='__main__':
    try:main()
    except Exception as e:
        safe={'not_confirmed_management_home','runtime_token_missing','mcp_sdk2_required_no_packages_changed','existing_server_conflict','telegram_mcp_explicitly_disabled','telegram_policy_needs_review','download_checksum_mismatch','config_changed_retry'}
        reason=str(e) if isinstance(e,ValueError) and str(e) in safe else type(e).__name__
        print(json.dumps({'status':'INSTALL_BLOCKED','reason':reason,'token_printed':False}));raise SystemExit(1)
