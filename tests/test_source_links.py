import json
from source_links import collect
URL='https://merlyshoes.com/products/real-fixture'
def trace(data):return [{'type':'function_call','call_id':'1','name':'mcp__merly__search_products'},{'type':'function_call_output','call_id':'1','output':json.dumps(data)}]
def test_only_source_result_links():
    data={'products':[{'product_url':URL},{'product_url':URL},{'product_url':'https://evil.invalid/'},{'product_url':'https://merlyshoes.com/products/fixture?token=x'}]}
    assert collect(trace(data))==[URL]
    assert collect([{'type':'message','content':[{'text':URL}]}])==[]
def test_wrappers_and_null_lists_do_not_crash():
    assert collect(trace({'products':None,'variants':None}))==[]
    assert collect(trace({'structuredContent':{'stock_report':{'variants':[{'product_url':URL}]}}}))==[URL]
    assert collect(trace({'product_url':'https://[broken'}))==[]

def test_duplicate_calls_or_failed_tool_not_trusted():
    data={'product_url':URL}
    items=trace(data);items.insert(1,items[0].copy())
    assert collect(items)==[]
    assert collect(trace({'status':'tool_unavailable','product_url':URL}))==[]

def test_bad_call_identifier_cannot_crash_reply():
    assert collect([{'type':'function_call_output','call_id':[],'output':'{}'}])==[]
