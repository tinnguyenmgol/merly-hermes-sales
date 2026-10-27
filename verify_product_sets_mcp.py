"""Actual MCP -> pinned native Responses serializer -> adapter, synthetic Haravan.
No real inventory or model calls; checks one/many product sets and uncertainty.
"""
import asyncio,json,os,sys,time
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from tools.mcp_tool_handlers import _render_call_tool_result
from gateway.platforms.api_server_openai_routes import OpenAICompatRoutesMixin as NativeAPI
from agent_answer import present
from customer_listing import project
ROOT=Path(__file__).resolve().parent
RUNNER=r'''import sys,runpy,copy
sys.path[:0]=[sys.argv[1],sys.argv[1]+'/tests']
import merly_tools as t
from test_stock_options import product,api_response
products=[]
for i in range(5):
 p=product(100+i,6 if i==0 else 1)
 p.update(title='Giày cao gót 7cm FixtureModel'+str(i),handle='fixture-'+str(i))
 for v in p['variants']:v.update(option1='Nâu',option2='40')
 products.append(p)
t.catalog.start=lambda:None
t.catalog.snapshot=lambda:copy.deepcopy(products)
t.catalog.status=lambda:{'ready':True,'age_seconds':1}
t.enrichment=lambda:{}
def get(resource,params):
 pid=int(resource.split('/')[1]);p=next(p for p in products if p['id']==pid)
 return api_response(p,resource,params)
t.h.get=get
t.h.inventory=lambda ids,locs:[{'variant_id':int(vid),'loc_id':loc,'qty_available':1 if int(vid)//1000!=104 and n==0 else 0} for vid in ids.split(',') for n,loc in enumerate(t.LOCATIONS)]
runpy.run_path(sys.argv[1]+'/mcp_server.py',run_name='__main__')
'''
async def main():
 env={k:os.environ[k] for k in ('PATH','HOME','TMPDIR') if k in os.environ}
 params=StdioServerParameters(command=sys.executable,args=['-P','-c',RUNNER,str(ROOT)],env=env)
 async with stdio_client(params) as (read,write):
  async with ClientSession(read,write,read_timeout_seconds=20) as session:
   await session.initialize();assert len((await session.list_tools()).tools)==5
   base={'heel_cm':7,'size':40,'color':'Nâu','check_stock':True}
   async def ask(extra):
    args={**base,**extra};started=time.time();result=await session.call_tool('search_products',args);assert not result.is_error
    messages=[{'role':'assistant','tool_calls':[{'id':'set_call','type':'function','function':{'name':'mcp__merly__search_products','arguments':json.dumps(args)}}]},{'role':'tool','tool_call_id':'set_call','content':_render_call_tool_result(result,'merly')}]
    items=NativeAPI._extract_output_items({'messages':messages,'final_response':'NATIVE_FIXTURE_REPLY'})
    answer=present({'output':items},'resp_set_fixture',started)
    return answer,project(answer)
   answer,view=await ask({})
   assert answer['stock_options']['selection']['products']==4
   assert len({r['product_id'] for r in view['stock_options']['variants']})==4
   assert view['listing']['shown']==4 and all(r['known_available']>0 for r in view['stock_options']['variants'])
   answer,view=await ask({'query':'FixtureModel1'})
   assert answer['stock_options']['selection']['kind']=='single_product' and view['listing']['shown']==1
   answer,view=await ask({'occasion':'UNVERIFIED_OCCASION_FIXTURE'})
   assert answer['stock_options']['operation_status']=='metadata_missing' and not view.get('stock_options')
   assert 'dịp sử dụng' in view['reply'] and 'chiều cao gót' not in view['reply']
   assert answer['_lookup_diagnostics'][0]['unverified_criteria']==['occasion']
   answer,view=await ask({'query':'FixtureModel4'})
   assert answer['stock_options']['operation_status']=='verified_zero' and view['listing']['shown']==0
   print('PASS_PRODUCT_SETS_MCP actual_mcp=true native_responses_serializer=true one_product=true multiple_distinct_products=true exact_skus=true positive_only=true max4=true metadata_reason_preserved=true zero_distinct_from_unknown=true safe_diagnostics=true tools5=true synthetic_source=true live_stock=false live_model=false')
if __name__=='__main__':asyncio.run(main())
