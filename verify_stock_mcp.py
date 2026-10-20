"""Actual MCP + pinned Hermes serialization, explicitly synthetic Haravan fixtures."""
import asyncio,json,os,sys
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests'))
from test_stock_options import TOKEN
from test_stock_report import envelope
from stock_report import extract
async def main():
    runner="""import sys,runpy,copy
sys.path[:0]=[sys.argv[1],sys.argv[1]+'/tests']
import merly_tools as t
from test_stock_options import product
p=product()
t.catalog.start=lambda:None
t.catalog.snapshot=lambda:[copy.deepcopy(p)]
t.catalog.status=lambda:{'ready':True,'age_seconds':1}
t.h.get=lambda *a:{'product':copy.deepcopy(p)}
t.h.inventory=lambda ids,locs:[{'variant_id':int(vid),'loc_id':loc,'qty_available':1 if n==0 else 0} for vid in ids.split(',') for n,loc in enumerate(t.LOCATIONS)]
runpy.run_path(sys.argv[1]+'/mcp_server.py',run_name='__main__')
"""
    env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR') if k in os.environ}
    args=StdioServerParameters(command=sys.executable,args=['-P','-c',runner,str(ROOT)],env=env)
    async with stdio_client(args) as (read,write):
        async with ClientSession(read,write,read_timeout_seconds=20) as session:
            await session.initialize();tools=await session.list_tools();assert len(tools.tools)==5
            args={'model_code':'1514','size':38,'check_stock':True,'stock_request_id':TOKEN}
            wrong=dict(args);wrong['size']='38'
            rejected=await session.call_tool('search_products',wrong)
            assert rejected.is_error and rejected.structured_content['reason']=='invalid_size'
            from tools.mcp_tool_handlers import _render_call_tool_result
            rejection_for_model=json.dumps(_render_call_tool_result(rejected,'merly'))
            assert 'invalid_size' in rejection_for_model and 'input_schema' in rejection_for_model
            result=await session.call_tool('search_products',args)
            assert not result.is_error
            from tools.mcp_tool_handlers import _render_call_tool_result
            wrapped=_render_call_tool_result(result,'merly')
            items=envelope(result.structured_content['stock_report']);items[1]['output']=wrapped
            report,requested=extract(items,TOKEN)
            assert requested and report['complete'] and len(report['variants'])==20
            assert {'Kem','Chì Bóng'}<={v['color'] for v in report['variants']}
            print('PASS_REAL_MCP_HERMES_SERIALIZATION actionable_error_reaches_model=true rejected_then_corrected=true all20=true Kem_and_ChiBong_present=true tools_remain5=true synthetic_source_only=true live_Haravan_calls=0 live_model_calls=0')
if __name__=='__main__':asyncio.run(main())
