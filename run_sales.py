"""Entrypoint for NEW sales resources; never edits owner's existing profile."""
import os,shutil,subprocess,sys,threading,time,tempfile
from pathlib import Path
ROOT=Path(__file__).parent


def save_sales_config(path,before,config,label):
    import hermes_yaml
    after=hermes_yaml.safe_dump(config,sort_keys=False,allow_unicode=True).encode()
    if hermes_yaml.safe_load(after.decode())!=config:raise RuntimeError('sales_config_roundtrip_failed')
    def write(target,data):
        fd,name=tempfile.mkstemp(prefix='.merly-config-',dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.replace(name,target)
        finally:Path(name).unlink(missing_ok=True)
    if path.read_bytes()!=before:raise RuntimeError('sales_config_changed_during_migration')
    write(path.with_name('config.before-'+label+'-'+str(time.time_ns())+'.yaml'),before)
    write(path,after)
    if hermes_yaml.safe_load(path.read_text())!=config:raise RuntimeError('sales_config_readback_failed')


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
    save_sales_config(path,before,config,'merly-env')
    return True

def ensure_gemini_model(home):
    """Explicit operator model choice; credentials stay in process env, not YAML."""
    import hermes_yaml,re,hmac
    model=os.getenv('MERLY_GEMINI_MODEL','')
    if not model:return False
    if not re.fullmatch(r'gemini-[A-Za-z0-9._-]{1,100}',model):raise RuntimeError('invalid_gemini_model_id')
    keys=[os.getenv(k,'') for k in ('GOOGLE_API_KEY','GEMINI_API_KEY')]
    if not any(keys):raise RuntimeError('gemini_runtime_key_missing')
    if any(k!=k.strip() for k in keys):raise RuntimeError('gemini_key_whitespace')
    if all(keys) and not hmac.compare_digest(*keys):raise RuntimeError('conflicting_gemini_keys')
    path=Path(home)/'config.yaml'
    if path.is_symlink():raise RuntimeError('sales_config_symlink_not_supported')
    before=path.read_bytes();config=hermes_yaml.safe_load(before.decode())
    from audit_instance import check_config
    check_config(config)
    previous=config.get('model')
    if previous is None:previous={}
    if not isinstance(previous,dict):raise RuntimeError('existing_model_config_requires_review')
    if previous.get('provider') not in (None,'','gemini','google','google-gemini','google-ai-studio'):raise RuntimeError('existing_model_provider_requires_review')
    if previous.get('api_key'):raise RuntimeError('model_inline_key_requires_review')
    configured=dict(previous);configured.update({'provider':'gemini','default':model})
    if configured==previous:return False
    config['model']=configured
    save_sales_config(path,before,config,'gemini')
    return True

def ensure_openrouter_model(home):
    """Explicit sales-only migration; never copy credentials into config/backups."""
    import hermes_yaml,re
    key=os.getenv('OPENROUTER_API_KEY','')
    if not key:raise RuntimeError('openrouter_runtime_key_missing')
    if re.search(r'\s',key):raise RuntimeError('openrouter_key_whitespace')
    if not 20<=len(key)<=512:raise RuntimeError('invalid_openrouter_key_length')
    model=os.getenv('MERLY_OPENROUTER_MODEL','openai/gpt-oss-20b')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}/[A-Za-z0-9][A-Za-z0-9._:-]{0,149}',model):raise RuntimeError('invalid_openrouter_model_id')
    path=Path(home)/'config.yaml'
    if path.is_symlink():raise RuntimeError('sales_config_symlink_not_supported')
    before=path.read_bytes();config=hermes_yaml.safe_load(before.decode())
    from audit_instance import check_config
    check_config(config)
    previous=config.get('model')
    if previous is None:previous={}
    if not isinstance(previous,dict):raise RuntimeError('existing_model_config_requires_review')
    if previous.get('provider') not in (None,'','gemini','google','google-gemini','google-ai-studio','openrouter'):raise RuntimeError('existing_model_provider_requires_review')
    if previous.get('api_key'):raise RuntimeError('model_inline_key_requires_review')
    configured=dict(previous)
    configured.update({'provider':'openrouter','default':model,'base_url':'https://openrouter.ai/api/v1','api_mode':'chat_completions'})
    if configured==previous:return False
    config['model']=configured
    save_sales_config(path,before,config,'openrouter')
    return True

def ensure_sales_auxiliary(home):
    """No paid title-generation calls in isolated sales; preserve other settings."""
    import hermes_yaml,copy
    path=Path(home)/'config.yaml'
    if path.is_symlink():raise RuntimeError('sales_config_symlink_not_supported')
    before=path.read_bytes();config=hermes_yaml.safe_load(before.decode())
    from audit_instance import check_config
    check_config(config)
    auxiliary=config.get('auxiliary',{})
    if not isinstance(auxiliary,dict):raise RuntimeError('invalid_sales_auxiliary_config')
    title=auxiliary.get('title_generation',{})
    if not isinstance(title,dict):raise RuntimeError('invalid_sales_title_config')
    if title.get('enabled') is False:return False
    changed=copy.deepcopy(auxiliary);changed['title_generation']={**title,'enabled':False}
    config['auxiliary']=changed
    save_sales_config(path,before,config,'sales-auxiliary')
    return True

def sales_execution_budget():
    """Single source of truth; keep the wall budget inside the 45s API timeout."""
    import json,math
    agent=json.loads((ROOT/'hermes-config.template.json').read_text())['agent']
    turns=agent['max_turns'];seconds=agent['run_budget_seconds']
    if type(turns) is not int or not 1<=turns<=16:raise RuntimeError('invalid_sales_iteration_budget')
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<45:raise RuntimeError('invalid_sales_time_budget')
    return {'max_turns':turns,'run_budget_seconds':seconds}

def ensure_sales_execution_budget(home):
    """Sync only two owned execution fields in the dedicated sales volume."""
    import hermes_yaml
    from audit_instance import check_config
    path=Path(home)/'config.yaml'
    if path.is_symlink():raise RuntimeError('sales_config_symlink_not_supported')
    before=path.read_bytes();config=hermes_yaml.safe_load(before.decode());check_config(config)
    agent=config.get('agent',{})
    if not isinstance(agent,dict):raise RuntimeError('invalid_sales_agent_config')
    model=config.get('model',{})
    if isinstance(model,dict) and model.get('api_key'):raise RuntimeError('model_inline_key_requires_review')
    desired=sales_execution_budget()
    if all(type(agent.get(k)) is type(v) and agent.get(k)==v for k,v in desired.items()):return False
    config['agent']={**agent,**desired}
    save_sales_config(path,before,config,'sales-execution-budget')
    return True

def ensure_sales_execution_prompt(home):
    """Replace only the managed execution block/legacy cap, not custom SOUL text."""
    begin='<!-- MERLY_EXECUTION_POLICY_BEGIN -->';end='<!-- MERLY_EXECUTION_POLICY_END -->'
    def span(text):
        if text.count(begin)!=1 or text.count(end)!=1:raise RuntimeError('invalid_execution_policy_markers')
        start=text.index(begin);stop=text.index(end)
        if stop<start:raise RuntimeError('invalid_execution_policy_markers')
        return start,stop+len(end)
    source=(ROOT/'SYSTEM-PROMPT.md').read_text();a,b=span(source);block=source[a:b]
    path=Path(home)/'SOUL.md'
    if path.is_symlink():raise RuntimeError('sales_soul_symlink_not_supported')
    before=path.read_bytes();text=before.decode()
    if begin in text or end in text:
        a,b=span(text);after=(text[:a]+block+text[b:]).encode()
    else:
        # This is a previous app-owned prompt setting, NOT customer-phrase routing.
        legacy='Tối đa ba vòng công cụ/lượt. '
        if text.count(legacy)>1:raise RuntimeError('ambiguous_legacy_execution_policy')
        after=(text.replace(legacy,block+'\n\n',1) if legacy in text else text+'\n\n'+block+'\n').encode()
    if after==before:return False
    fd,name=tempfile.mkstemp(prefix='.merly-execution-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(after);stream.flush();os.fsync(stream.fileno())
        if path.read_bytes()!=before:raise RuntimeError('sales_soul_changed_during_migration')
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)
    if path.read_bytes()!=after:raise RuntimeError('sales_soul_readback_failed')
    return True

def ensure_sales_model(home):
    provider=os.getenv('MERLY_SALES_PROVIDER','')
    if provider not in ('','gemini','openrouter'):raise RuntimeError('invalid_sales_provider')
    if provider=='openrouter' or (not provider and os.getenv('OPENROUTER_API_KEY')):return ensure_openrouter_model(home)
    if not provider:
        import hermes_yaml
        path=Path(home)/'config.yaml'
        if path.is_symlink():raise RuntimeError('sales_config_symlink_not_supported')
        config=hermes_yaml.safe_load(path.read_text())
        model=config.get('model') if isinstance(config,dict) else None
        if isinstance(model,dict) and model.get('provider')=='openrouter':return ensure_openrouter_model(home)
    return ensure_gemini_model(home)

def ensure_customer_policy_prompt(home):
    """Update only FAQ block in dedicated SALES SOUL; preserve other instructions."""
    begin='<!-- MERLY_CUSTOMER_FAQ_POLICY_BEGIN -->'
    end='<!-- MERLY_CUSTOMER_FAQ_POLICY_END -->'
    def span(text):
        if text.count(begin)!=1 or text.count(end)!=1:raise RuntimeError('invalid_customer_policy_markers')
        start=text.index(begin);stop=text.index(end)
        if stop<start:raise RuntimeError('invalid_customer_policy_markers')
        return start,stop+len(end)
    source=(ROOT/'SYSTEM-PROMPT.md').read_text();start,stop=span(source);block=source[start:stop]
    path=Path(home)/'SOUL.md'
    if path.is_symlink():raise RuntimeError('sales_soul_symlink_not_supported')
    before=path.read_bytes();text=before.decode()
    if begin in text or end in text:
        start,stop=span(text);after=(text[:start]+block+text[stop:]).encode()
    else:after=before+b'\n\n'+block.encode()+b'\n'
    if before==after:return False
    fd,name=tempfile.mkstemp(prefix='.merly-faq-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(after);stream.flush();os.fsync(stream.fileno())
        if path.read_bytes()!=before:raise RuntimeError('sales_soul_changed_during_migration')
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)
    if path.read_bytes()!=after:raise RuntimeError('sales_soul_readback_failed')
    return True

def main():
    role=os.getenv('PILOT_ROLE','hermes')
    if role=='gateway':
        import fast_limits
        for name in fast_limits.DEFAULTS:fast_limits.limit(name)
        if fast_limits.limit('AI_CONCURRENT')+fast_limits.limit('STOCK_CONCURRENT')>3:raise RuntimeError('fast_worker_reservation_required')
        if os.getenv('HARAVAN_ACCESS_TOKEN'):raise RuntimeError('gateway_must_not_hold_haravan_token')
        if any(os.getenv(k) for k in ('GEMINI_API_KEY','GOOGLE_API_KEY','OPENROUTER_API_KEY')):raise RuntimeError('gateway_must_not_hold_model_key')
        os.execvp(sys.executable,[sys.executable,'-m','gunicorn','--no-control-socket','--bind','0.0.0.0:8080','--workers','1','--threads','4','--timeout','60','sales_gateway:application'])
    if role!='hermes':raise RuntimeError('invalid_role')
    home=Path(os.environ['HERMES_HOME']).resolve()
    if home.name in ('default','data','.hermes') or str(home).startswith('/opt/data'):raise RuntimeError('dedicated_sales_home_required')
    if len(os.getenv('API_SERVER_KEY',''))<32:raise RuntimeError('new_sales_api_key_required')
    if not os.getenv('HERMES_SALES_API_BASE'):raise RuntimeError('sales_listener_base_required')
    home.mkdir(parents=True,exist_ok=True)
    if not (home/'config.yaml').exists():shutil.copy2(ROOT/'hermes-config.template.json',home/'config.yaml')
    if not (home/'SOUL.md').exists():shutil.copy2(ROOT/'SYSTEM-PROMPT.md',home/'SOUL.md')
    ensure_customer_policy_prompt(home)
    ensure_merly_child_env(home)
    ensure_sales_model(home)
    ensure_sales_auxiliary(home)
    budget_changed=ensure_sales_execution_budget(home)
    prompt_changed=ensure_sales_execution_prompt(home)
    import json
    print(json.dumps({'status':'sales_execution_policy_ready',**sales_execution_budget(),'config_migrated':budget_changed,'prompt_migrated':prompt_changed}),flush=True)
    os.environ.setdefault('MERLY_MCP_PYTHON',sys.executable)
    def audit():
        return subprocess.run([sys.executable,str(ROOT/'audit_instance.py')],cwd=home).returncode==0
    if not audit():raise RuntimeError('startup_audit_failed')
    from stock_probe import start as start_stock_probe
    stock_probe_server=start_stock_probe()
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
