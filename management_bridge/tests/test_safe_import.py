"""Actual MCP transport in safe/isolated Python, no credentials or API requests."""
import asyncio,os,sys
from pathlib import Path
import pytest
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
SERVER=Path(__file__).resolve().parents[1]/'server.py'

@pytest.mark.parametrize('flags',[[],['-P'],['-I']])
def test_reader_uses_verified_sibling_not_cwd(tmp_path,flags):
    (tmp_path/'reader.py').write_text("raise RuntimeError('untrusted cwd must not be imported')")
    env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR') if k in os.environ}
    env['PYTHONSAFEPATH']='1';env['PYTHONPATH']=str(tmp_path)
    async def check():
        args=StdioServerParameters(command=sys.executable,args=[*flags,str(SERVER)],env=env,cwd=str(tmp_path))
        async with stdio_client(args) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=10) as session:
                await session.initialize();tools=await session.list_tools()
                assert {t.name for t in tools.tools}=={'recent_hermes_deployments','hermes_build_log'}
                assert all(t.annotations.read_only_hint for t in tools.tools)
                result=await session.call_tool('hermes_build_log',{})
                assert result.is_error and result.structured_content['error']=='missing_token'
    asyncio.run(check())
