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
    known={'unknown_fields','unknown_tool','required_ids','stock_scope_required','stock_check_required','verify_specs_before_stock_scope','unknown_topic'}|{'invalid_'+field for field in fields}
    code=reason if reason in known else 'validation_failed'
    received={field:type(arguments[field]).__name__ for field in sorted(fields&set(arguments))} if isinstance(arguments,dict) else {}
    result={'status':'invalid_arguments','reason':code,'received_field_types':received,'input_schema':schema,'do_not_infer_no_stock':True,
      'repair_hint':'Correct the arguments using input_schema. Omit unused optional fields, not null/empty placeholders. Do not repeat identical failing arguments. Never guess product/variant IDs or infer zero stock from this error.'}
    if name=='search_products':
        result['stock_requirements']={'when':'check_stock=true','required':['size'],'model_code':'optional exact string; do not invent for criteria search','size':'integer 35-43, not a quoted string','criteria':['query','collection','heel_cm','category','occasion','color']}
    if name=='search_products' and code=='stock_scope_required' and isinstance(arguments,dict) and arguments.get('check_stock') is True and 'size' not in arguments:
        result['needs_clarification']={'fields':['size'],'source_read_attempted':False}
        result['repair_hint']='Ask the customer for the missing confirmed size. Preserve their other criteria. Do not invent a size or repeat the same call; no source lookup has run.'
    if code=='stock_check_required':result['repair_hint']='Customer search requires check_stock=true and confirmed size. Without size ask the customer. Catalog-only results cannot be listed.'
    diagnostic('MERLY_TOOL_ARGUMENT_ERROR',json.dumps({'tool':name if definition else 'unknown_tool','reason':code,'received_field_types':received}))
    return result,True

def invoke(name,arguments):
    try:
        if name=='search_products':
            merly_tools.validate(arguments,merly_tools.SEARCH_FIELDS)
            # Public sales MCP has no catalog-only listing mode. Internal
            # discovery retains candidate_only and does not use this entrypoint.
            if arguments.get('check_stock',True) is not True:raise merly_tools.Invalid('stock_check_required')
            if 'size' not in arguments:
                return {'status':'needs_clarification','missing_fields':['size'],'next_action':'ask_missing_customer_fields','source_read_attempted':False,'stock_checked':False,'products':[]},False
            arguments=dict(arguments)
            arguments.setdefault('check_stock',True)
        return merly_tools.dispatch(name,arguments),False
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
