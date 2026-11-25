"""Owner insights: chat log + search demand, masked, bounded retention, never breaks a reply."""
import json,sqlite3,time
import pytest
import insights,insights_report
import hermes_client as client
from test_gateway import configured,call

def rows(sql):
    db=sqlite3.connect(insights.path());db.row_factory=sqlite3.Row
    try:return [dict(r) for r in db.execute(sql)]
    finally:db.close()

@pytest.mark.parametrize('text,expected',[
 ('gọi em 0912 345 678 nhé','gọi em [SĐT] nhé'),('sđt +84912345678','sđt [SĐT]'),
 ('mail chi.lan+shop@gmail.com','mail [email]'),('stk 1903 6655 4433 21','stk [số]'),
 ('mã 1676 size 38 còn màu gì','mã 1676 size 38 còn màu gì'),('giá 359.000đ','giá 359.000đ'),
 ('xem https://oa.zalo.me/2969822963244380594 nhé','xem https://oa.zalo.me/2969822963244380594 nhé')])
def test_redaction(text,expected):
    assert insights.redact(text)==expected

def discovery(positive):
    rows_=[{'product_id':1,'variant_id':11,'known_available':positive,'available':positive>0,'size':'42','color':'Đen'}]
    return {'mode':'discovery','criteria':{'size':42,'color':'Đen','category':'giày bệt','heel_cm':0.0},'variants':rows_,'products':[],'complete':True,'operation_status':'available' if positive else 'verified_zero'}

def test_turns_searches_and_report(configured,monkeypatch,capsys):
    replies=iter([{'reply':'Chị mang size nào ạ? Gọi em 0912345678','conversation_id':'resp_1','needs_clarification':True},
                  {'reply':'Hiện mẫu này đã hết hàng ạ.','conversation_id':'resp_2','stock_options':discovery(0),'_tools_used':['mcp__merly__search_products']},
                  {'reply':'Phí ship tính theo khu vực ạ.','conversation_id':'resp_3','_policy_topics':['shipping'],'_tools_used':['mcp__merly__get_policy']}])
    monkeypatch.setattr(client,'chat',lambda *a:next(replies))
    a=call('mình cần giày đi làm, sđt mình 0987 654 321');cookie=a['headers']['Set-Cookie'].split(';')[0]
    call('size 42 giày bệt đen',cookie=cookie);call('ship bao nhiêu',cookie=cookie)
    turns=rows('SELECT * FROM turns ORDER BY id')
    assert [t['turn'] for t in turns]==[1,2,3] and len({t['session'] for t in turns})==1
    assert '0987' not in turns[0]['message'] and '[SĐT]' in turns[0]['message'] and '0912345678' not in turns[0]['reply']
    assert turns[0]['needs_clarification']==1 and json.loads(turns[2]['policy_topics'])==['shipping']
    s=rows('SELECT * FROM searches')
    assert len(s)==1 and s[0]['size']==42 and s[0]['color']=='Đen' and s[0]['category']=='giày bệt' and s[0]['outcome']=='verified_zero' and s[0]['positive_skus']==0
    assert insights_report.main(['--days','7'])==0
    out=capsys.readouterr().out
    assert 'NHU CẦU CHƯA ĐÁP ỨNG' in out and 'giày bệt · size 42 · màu Đen · gót 0cm: 1 lượt → hết hàng 1' in out
    assert 'Giao hàng (1)' in out and '0987' not in out

def test_session_hash_is_not_gateway_identity(configured,monkeypatch):
    import state
    monkeypatch.setattr(client,'chat',lambda *a:{'reply':'ok','conversation_id':'resp_1'})
    a=call('hello');_,sid=state.identity(a['headers']['Set-Cookie'].split(';')[0])
    session=rows('SELECT session FROM turns')[0]['session']
    assert session!=sid and sid not in session and len(session)==16

def test_failures_and_limits_recorded(configured,monkeypatch):
    def fail(*a):raise client.HermesError('turn_not_completed')
    monkeypatch.setattr(client,'chat',fail)
    assert call('có giày size 42 ko')['status'].startswith('503')
    monkeypatch.setenv('MERLY_AI_PER_MINUTE','1')
    call('lần 2')
    got=[(t['status'],t['reason'],t['message']) for t in rows('SELECT * FROM turns ORDER BY id')]
    assert got[0]==('failed','turn_not_completed','có giày size 42 ko')
    assert got[1][0]=='limited' and got[1][1]=='ai_minute_limit'

def test_direct_stock_probe_criteria(configured,monkeypatch):
    report={'mode':'all_options','model_code':'1676','size':38,'color_filter':None,'complete':True,'operation_status':'complete','issues':[],
            'variants':[{'product_id':5,'variant_id':51,'known_available':3,'available':True,'size':'38','color':'Đen'}]}
    monkeypatch.setattr(client,'probe_stock',lambda scope:{'reply':'x','stock_options':report,'engine':'haravan-readonly','model_called':False})
    assert call('mã 1676 size 38 còn màu gì')['status'].startswith('200')
    s=rows('SELECT * FROM searches')[0]
    assert (s['model_code'],s['size'],s['outcome'],s['positive_skus'])==('1676',38,'available',1)
    assert rows('SELECT engine FROM turns')[0]['engine']=='haravan-readonly'

def test_disabled_records_nothing(configured,monkeypatch):
    monkeypatch.setenv('MERLY_INSIGHTS_ENABLED','0')
    monkeypatch.setattr(client,'chat',lambda *a:{'reply':'ok','conversation_id':'resp_1'})
    call('hello')
    assert not insights.path().exists()

def test_store_failure_never_breaks_reply(configured,monkeypatch,caplog):
    monkeypatch.setattr(client,'chat',lambda *a:{'reply':'ok','conversation_id':'resp_1'})
    def broken(*a,**k):raise sqlite3.OperationalError('disk full')
    monkeypatch.setattr(insights,'connect',broken)
    r=call('hello')
    assert r['status'].startswith('200') and r['body']['reply']=='ok' and 'MERLY_INSIGHTS_RECORD_DROPPED' in caplog.text

def test_retention_purges_old_rows(configured,monkeypatch):
    monkeypatch.setattr(client,'chat',lambda *a:{'reply':'ok','conversation_id':'resp_1'})
    call('cũ')
    db=sqlite3.connect(insights.path())
    with db:db.execute('UPDATE turns SET ts=ts-40*86400')
    db.close()
    insights._LAST_PURGE[0]=0;call('mới')
    assert [t['message'] for t in rows('SELECT message FROM turns')]==['mới']

def test_invalid_retention_fails_closed_without_breaking_reply(configured,monkeypatch):
    monkeypatch.setenv('MERLY_INSIGHTS_RETENTION_DAYS','0');insights._LAST_PURGE[0]=0
    monkeypatch.setattr(client,'chat',lambda *a:{'reply':'ok','conversation_id':'resp_1'})
    assert call('hello')['body']['reply']=='ok'
    assert not insights.path().exists() or rows('SELECT count(*) n FROM turns')[0]['n']==0

def test_report_without_data(configured,capsys):
    assert insights_report.main([])==0 and 'Chưa có dữ liệu' in capsys.readouterr().out

def test_partial_check_with_stock_is_partial_available():
    report={'mode':'all_options','model_code':'1676','size':38,'complete':False,'operation_status':'partial','variants':[{'product_id':5,'variant_id':51,'known_available':2},{'product_id':6,'variant_id':61,'known_available':1}]}
    assert insights.searches(report)[0]['outcome']=='partial_available'
    report['variants']=[{'product_id':5,'variant_id':51,'known_available':0}]
    assert insights.searches(report)[0]['outcome']=='partial'

import io
import sales_gateway as gateway
from pathlib import Path

def get(path,query='',key='P'*40):
    out={};env={'REQUEST_METHOD':'GET','PATH_INFO':path,'QUERY_STRING':query,'wsgi.input':io.BytesIO(b'')}
    if key is not None:env['HTTP_AUTHORIZATION']='Bearer '+key
    def start(status,headers):out.update(status=status,headers=dict(headers))
    raw=b''.join(gateway.application(env,start));out['raw']=raw
    try:out['body']=json.loads(raw)
    except ValueError:out['body']=None
    return out

def test_admin_api_requires_key_and_returns_dashboard(configured,monkeypatch):
    monkeypatch.setattr(client,'chat',lambda *a:{'reply':'Hết hàng ạ.','conversation_id':'resp_1','stock_options':discovery(0)})
    call('giày bệt đen size 42, sđt 0912345678')
    assert get('/api/admin/insights',key=None)['status'].startswith('401')
    assert get('/api/admin/insights',key='x'*40)['status'].startswith('401')
    d=get('/api/admin/insights','days=7')['body']
    assert d['turns']==1 and d['no_data'] is False and d['unmet_demand'][0]['count']==1
    session=d['recent_sessions'][0]
    assert d['conversations'][session][0]['message']=='giày bệt đen size 42, sđt [SĐT]'
    one=get('/api/admin/conversation','session='+session)['body']
    assert one['turns'][0]['reply']=='Hết hàng ạ.'

@pytest.mark.parametrize('path,query',[('/api/admin/insights','days=0'),('/api/admin/insights','days=999'),('/api/admin/insights','chats=50'),('/api/admin/insights','days=abc'),('/api/admin/conversation','session=../../etc'),('/api/admin/conversation','')])
def test_admin_api_rejects_bad_params(configured,path,query):
    assert get(path,query)['status'].startswith('400')

def test_admin_api_without_data(configured):
    d=get('/api/admin/insights')['body']
    assert d['no_data'] is True and d['turns']==0

def test_admin_page_served_with_strict_csp(configured):
    for path in ('/admin','/admin.js','/admin.css'):
        r=get(path,key=None)
        assert r['status'].startswith('200') and "script-src 'self'" in r['headers']['Content-Security-Policy'] and r['headers']['X-Frame-Options']=='DENY'
    js=(Path(gateway.__file__).with_name('pilot-web')/'admin.js').read_text()
    assert 'innerHTML' not in js and 'insertAdjacentHTML' not in js and 'eval(' not in js

def test_admin_dashboard_explains_failure_reasons(configured,monkeypatch):
    def fail(*a):raise client.HermesError('turn_not_completed')
    monkeypatch.setattr(client,'chat',fail);call('sandal size 43')
    d=get('/api/admin/insights')['body']
    assert d['reasons']['turn_not_completed']=='nhà cung cấp AI từ chối/lỗi' and d['review_sessions']
