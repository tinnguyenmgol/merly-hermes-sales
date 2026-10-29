"""Run INSIDE a dedicated Hermes sales install. No model invocation; no profile edits."""
import contextlib,json,os,sys,time
from pathlib import Path
from safety import NAMES,digest

def check_config(config):
    if config.get('memory',{}).get('memory_enabled') is not False or config.get('memory',{}).get('user_profile_enabled') is not False:raise ValueError('disable_global_memory')
    if config.get('memory',{}).get('provider',''):raise ValueError('external_memory_disallowed')
    if config.get('platform_toolsets',{}).get('api_server')!=['merly']:raise ValueError('api_tools_must_be_merly_only')
    if config.get('tools',{}).get('tool_search',{}).get('enabled')!='off':raise ValueError('tool_search_bridge_must_be_off')
    servers=config.get('mcp_servers',{})
    if set(servers)!={'merly'}:raise ValueError('unexpected_mcp_server')
    include=servers['merly'].get('tools',{}).get('include')
    if not isinstance(include,list) or {'mcp__merly__'+n for n in include}!=NAMES:raise ValueError('wrong_mcp_allowlist')
    if config.get('gateway',{}).get('multiplex_profiles'):raise ValueError('multiplex_not_allowed')

def check_model_definitions(definitions):
    """Validate the schema actually exposed by Hermes, not just tool names."""
    functions={d['function']['name']:d['function'] for d in definitions}
    if set(functions)!=NAMES:raise ValueError('runtime_tool_inventory_mismatch')
    schema=functions['mcp__merly__search_products'].get('parameters',{})
    size=schema.get('properties',{}).get('size',{})
    if size.get('type')!='integer' or size.get('minimum')!=35 or size.get('maximum')!=43:raise ValueError('model_size_schema_invalid')
    if 'size' not in schema.get('required',[]):raise ValueError('model_size_must_be_required')

def main():
    home=Path(os.environ['HERMES_HOME']).resolve()
    if home.name in ('default','data','.hermes') or home==Path.home():raise ValueError('dedicated_sales_home_required')
    # Do not import owner runtime/profile. Operator supplies this dedicated install.
    adapter_dir=str(Path(__file__).resolve().parent)
    sys.path[:]=[p for p in sys.path if p not in ('',adapter_dir)]
    with contextlib.redirect_stdout(sys.stderr):
        from hermes_cli.config import load_config
        config=load_config();check_config(config)
        from hermes_constants import get_hermes_home
        if Path(get_hermes_home()).resolve()!=home:raise ValueError('runtime_home_mismatch')
        from tools.mcp_tool_discovery import discover_mcp_tools
        discover_mcp_tools(allowed_mcp_names=['merly'])
        from model_tools import get_tool_definitions
        definitions=get_tool_definitions(enabled_toolsets=['merly'],disabled_toolsets=config.get('agent',{}).get('disabled_toolsets',[]),quiet_mode=True,skip_tool_search_assembly=True)
        check_model_definitions(definitions)
        names={d['function']['name'] for d in definitions}
        if names!=NAMES:raise ValueError('runtime_tool_inventory_mismatch')
        model_defs=get_tool_definitions(enabled_toolsets=['merly'],disabled_toolsets=config.get('agent',{}).get('disabled_toolsets',[]),quiet_mode=True)
        check_model_definitions(model_defs)
    base=os.environ['HERMES_SALES_API_BASE'].rstrip('/');key=os.environ['API_SERVER_KEY']
    if len(key)<32:raise ValueError('dedicated_api_key_required')
    record={'created_at':time.time(),'api_base':base,'tools':sorted(names),'memory_enabled':False,'user_profile_enabled':False}
    out=Path(os.environ['HERMES_SALES_ATTESTATION']);out.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(str(out),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as f:json.dump({'record':record,'signature':digest(record,key)},f)
    print(json.dumps({'status':'startup_inventory_verified','tools':sorted(names),'expires_in_hours':24,'model_size_required':True}))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps({'status':'NOT_VERIFIED','error_type':type(e).__name__}));raise SystemExit(1)
