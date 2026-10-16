"""MCP2 stdio server: five fixed read-only Merly tools, no arbitrary execution."""
import asyncio,json,sys
from pathlib import Path
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as t
import merly_tools
def diagnostic(*args,**kwargs):
    kwargs['file']=sys.stderr
    print(*args,**kwargs)
merly_tools.h.print=diagnostic
ROOT=Path(__file__).parent
SCHEMA=json.loads((ROOT/'tool-schema.json').read_text())
DEFINITIONS={op['post']['operationId']:op['post'] for op in SCHEMA['paths'].values()}

async def list_tools(ctx,params):
    return t.ListToolsResult(tools=[t.Tool(name=name,description=definition['summary'],inputSchema=definition['requestBody']['content']['application/json']['schema'],annotations=t.ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False)) for name,definition in DEFINITIONS.items()])

def invoke(name,arguments):
    try:return merly_tools.dispatch(name,arguments),False
    except (merly_tools.Invalid,TypeError,ValueError):return {'status':'invalid_arguments'},True
    except merly_tools.h.HaravanError:return {'status':'source_unavailable','do_not_infer_no_stock':True},True
    except Exception:return {'status':'tool_unavailable'},True

async def call_tool(ctx,params):
    result,error=await asyncio.to_thread(invoke,params.name,params.arguments if params.arguments is not None else {})
    return t.CallToolResult(content=[t.TextContent(text=json.dumps(result,ensure_ascii=False))],structuredContent=result,isError=error)

server=Server('merly-sales',version='0.1.0',on_list_tools=list_tools,on_call_tool=call_tool)
async def main():
    merly_tools.catalog.start()
    async with stdio_server() as (read,write):
        await server.run(read,write,server.create_initialization_options())
if __name__=='__main__':asyncio.run(main())
