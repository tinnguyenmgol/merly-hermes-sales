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
    known={'invalid_heel_cm','invalid_heel_mode','unknown_fields','unknown_tool','required_ids','stock_scope_required','missing_required_fields','stock_check_required','inconsistent_heel_requirement','conflicting_heel_selection','verify_specs_before_stock_scope','unknown_topic'}|{'invalid_'+field for field in fields}
    code=reason if reason in known else 'validation_failed'
    received={field:type(arguments[field]).__name__ for field in sorted(fields&set(arguments))} if isinstance(arguments,dict) else {}
    result={'status':'invalid_arguments','reason':code,'received_field_types':received,'input_schema':schema,'do_not_infer_no_stock':True,
      'repair_hint':'Correct the arguments using the tool declared schema. Omit unused optional fields, not null/empty placeholders. Do not repeat identical failing arguments. Never guess product/variant IDs or infer zero stock from this error.'}
    if name=='search_products':
        result['stock_requirements']={'when':'check_stock=true','required':['size','heel_selection'],'model_code':'optional exact string; do not invent for criteria search','size':'integer 35-43, not a quoted string','criteria':['query','collection','heel_selection','category','occasion','color']}
    if name=='search_products' and code=='stock_scope_required' and isinstance(arguments,dict) and arguments.get('check_stock') is True and 'size' not in arguments:
        result['needs_clarification']={'fields':['size'],'source_read_attempted':False}
        result['repair_hint']='Ask the customer for the missing confirmed size. Preserve their other criteria. Do not invent a size or repeat the same call; no source lookup has run.'
    if name=='search_products' and code=='missing_required_fields':
        result.update(missing_fields=['size'],source_read_attempted=False,stock_checked=False,next_action='recover_confirmed_fields_or_ask')
        result['repair_hint']='This TOOL CALL omitted required size; that does not prove the customer omitted it. Read the original current message and delivered customer history. If size was already explicitly confirmed, resend with that size and all current criteria. Ask the customer ONLY if no confirmed size exists or choices conflict. Never invent size or repeat the same incomplete call.'
    if code in ('inconsistent_heel_requirement','invalid_heel_selection','conflicting_heel_selection'):result['repair_hint']='Use ONLY heel_selection: a numeric string in cm (0 to 15) for the latest confirmed height, or unspecified. No heel_mode, separate heel_cm, units, comma, null or foot length. Never guess height.'
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
                argument_error(name,arguments,'missing_required_fields')
                from tool_payload import missing_size_feedback
                return missing_size_feedback(),False  # input control, not a server failure
            arguments=dict(arguments)
            arguments.setdefault('check_stock',True)
        return merly_tools.dispatch(name,arguments),False
    except merly_tools.Invalid as exc:return argument_error(name,arguments,str(exc))
    except (TypeError,ValueError):return argument_error(name,arguments,'validation_failed')
    except merly_tools.h.HaravanError:return {'status':'source_unavailable','do_not_infer_no_stock':True},True
    except Exception:return {'status':'tool_unavailable'},True

def wire_feedback(result):
    """Keep typed failures intact below the pinned SDK's error-text bound.
    Full schemas are already exposed by list_tools; duplicating them in isError
    text makes SDK tool_error truncate JSON mid-object. Never repair cut JSON.
    """
    from tool_payload import missing_size_feedback
    if result==missing_size_feedback():return result
    if not isinstance(result,dict) or result.get('status') not in ('invalid_arguments','source_unavailable','tool_unavailable'):return result
    keys=('status','reason','do_not_infer_no_stock','missing_fields','next_action','source_read_attempted','stock_checked','repair_hint','received_field_types')
    out={k:result[k] for k in keys if k in result}
    if result.get('status')=='invalid_arguments':out['required_fields']=result.get('input_schema',{}).get('required',[])
    if len(json.dumps(out,ensure_ascii=False))>1500:
        out.pop('received_field_types',None)
        out['repair_hint']='Use the declared tool schema and original customer input/history. Recover confirmed fields; ask only if genuinely unknown. Never guess IDs, stock, size or height.'
    if len(json.dumps(out,ensure_ascii=False))>1500:raise ValueError('oversized_wire_feedback')
    return out

async def call_tool(ctx,params):
    result,error=await asyncio.to_thread(invoke,params.name,params.arguments if params.arguments is not None else {})
    result=wire_feedback(result)
    return t.CallToolResult(content=[t.TextContent(text=json.dumps(result,ensure_ascii=False))],structuredContent=result,isError=error)

server=Server('merly-sales',version='0.1.0',on_list_tools=list_tools,on_call_tool=call_tool)
async def main():
    merly_tools.catalog.start()
    async with stdio_server() as (read,write):
        await server.run(read,write,server.create_initialization_options())
if __name__=='__main__':asyncio.run(main())
