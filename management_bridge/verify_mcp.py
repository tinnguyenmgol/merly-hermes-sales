"""Real MCP transport, no live token. NOT proof of Coolify connectivity."""
import asyncio,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR') if k in os.environ};env['PYTHONSAFEPATH']='1'
    async with stdio_client(StdioServerParameters(command=sys.executable,args=['-P',str(Path(__file__).resolve().with_name('server.py'))],env=env)) as (read,write):
        async with ClientSession(read,write,read_timeout_seconds=10) as session:
            await session.initialize();listing=await session.list_tools()
            assert {t.name for t in listing.tools}=={'recent_hermes_deployments','hermes_build_log'}
            assert all(t.annotations.read_only_hint is True for t in listing.tools)
            result=await session.call_tool('hermes_build_log',{})
            assert result.is_error and result.structured_content['error']=='missing_token'
            blocked=await session.call_tool('hermes_build_log',{'resource_uuid':'other-app'})
            assert blocked.is_error
            print('PASS_REAL_MCP exactly2 read-only diagnostics tools; no token fails closed; resource override blocked')
            print('NOT_TESTED live Coolify or management-profile integration')
if __name__=='__main__':asyncio.run(main())
