"""Real MCP2 initialize/list/call roundtrip; no model or Haravan token needed."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).parent
async def main():
    env=dict(os.environ);env.pop('HARAVAN_ACCESS_TOKEN',None)
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'mcp_server.py')],env=env,cwd=str(ROOT))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write,read_timeout_seconds=15) as session:
            await session.initialize();listing=await session.list_tools()
            expected={'search_products','quote_variant','size_guide','get_policy','get_promotions'}
            assert {t.name for t in listing.tools}==expected
            assert all(t.annotations.read_only_hint is True for t in listing.tools)
            result=await session.call_tool('size_guide',{'size':39})
            payload=result.structured_content or json.loads(result.content[0].text)
            assert payload['chart'][0]['length_cm']==24.5
            result=await session.call_tool('size_guide',{'length_cm':26.5})
            payload=result.structured_content or json.loads(result.content[0].text)
            assert payload['chart'][0]['size']==43
            blocked=await session.call_tool('size_guide',{'size':True})
            assert blocked.is_error
            print('PASS_REAL_MCP initialize, exactly five read-only tools, size39=24.5cm,26.5cm=size43, invalid arguments rejected')
            print('NOT_TESTED Hermes model reasoning/live sales dialogue')
if __name__=='__main__':asyncio.run(main())
