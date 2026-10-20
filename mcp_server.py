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

def argument_error(name,arguments,reason):
    definition=DEFINITIONS.get(name)
    schema=definition['requestBody']['content']['application/json']['schema'] if definition else {'type':'object','additionalProperties':False}
    fields=set(schema.get('properties',{}))
    known={'unknown_fields','unknown_tool','required_ids','stock_scope_required','verify_specs_before_stock_scope','unknown_topic'}|{'invalid_'+field for field in fields}
    code=reason if reason in known else 'validation_failed'
    received={field:type(arguments[field]).__name__ for field in sorted(fields&set(arguments))} if isinstance(arguments,dict) else {}
    result={'status':'invalid_arguments','reason':code,'received_field_types':received,'input_schema':schema,'do_not_infer_no_stock':True,
      'repair_hint':'Correct the arguments using input_schema. Omit unused optional fields, not null/empty placeholders. Do not repeat identical failing arguments. Never guess product/variant IDs or infer zero stock from this error.'}
    if name=='search_products':
        result['stock_requirements']={'when':'check_stock=true','required':['model_code','size','stock_request_id'],'model_code':'string, not a number','size':'integer 35-43, not a quoted string','stock_request_id':'copy the exact current-turn 32 lowercase hex ID from instructions; do not invent or reuse an old one','omit':['heel_cm','category','occasion']}
    diagnostic('MERLY_TOOL_ARGUMENT_ERROR',json.dumps({'tool':name if definition else 'unknown_tool','reason':code,'received_field_types':received}))
    return result,True

def invoke(name,arguments):
    try:return merly_tools.dispatch(name,arguments),False
    except merly_tools.Invalid as exc:return argument_error(name,arguments,str(exc))
    except (TypeError,ValueError):return argument_error(name,arguments,'validation_failed')
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
