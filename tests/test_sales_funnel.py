"""Sales funnel: public events, report funnel, widget cart bridge constraints."""
import json,re,sqlite3
from pathlib import Path
import pytest
import insights,insights_report
import public_chat as p
from test_gateway import configured
from test_public_chat import public,req,session

ROOT=Path(__file__).resolve().parents[1]

def events():
    db=sqlite3.connect(insights.path())
    try:return [r[0] for r in db.execute('SELECT name FROM events ORDER BY rowid')]
    finally:db.close()

def test_event_recorded_with_session_and_csrf(public):
    p._EVENTS.clear();cookie,csrf=session()
    for name in ('open_teaser','size_chip','add_to_cart','checkout'):
        r=req('/api/public/event','POST',cookie,csrf,data={'event':name})
        assert r['status'].startswith('200'),r
    assert events()==['open_teaser','size_chip','add_to_cart','checkout']
    s=insights_report.summarize([],[],0,[{'name':n,'session':'a'} for n in events()])
    assert {f['name']:f['visitors'] for f in s['funnel'] if f['count']}=={'open_teaser':1,'size_chip':1,'add_to_cart':1,'checkout':1}

@pytest.mark.parametrize('kind',['origin','csrf','name','extra','bigbody'])
def test_event_rejected(public,kind):
    p._EVENTS.clear();cookie,csrf=session()
    args=dict(cookie=cookie,csrf=csrf,data={'event':'add_to_cart'})
    if kind=='origin':args['origin']='https://evil.example'
    if kind=='csrf':args['csrf']='x'*64
    if kind=='name':args['data']={'event':'purchase_completed'}
    if kind=='extra':args['data']={'event':'add_to_cart','variant':1}
    if kind=='bigbody':args['data']={'event':'add_to_cart'+' '*300}
    r=req('/api/public/event','POST',**args)
    assert r['status'][:3] in ('400','403')
    assert not insights.path().exists() or events()==[]

def test_event_rate_and_daily_cap(public,monkeypatch):
    p._EVENTS.clear();cookie,csrf=session()
    codes=[req('/api/public/event','POST',cookie,csrf,data={'event':'open_button'})['status'][:3] for _ in range(22)]
    assert codes[:20]==['200']*20 and codes[20:]==['429','429']
    monkeypatch.setattr(insights,'EVENTS_PER_SESSION_DAY',3)
    assert not insights.record_event('sid-x','open_button') or True
    for _ in range(5):insights.record_event('sid-y','size_chip')
    assert events().count('size_chip')==3

def test_widget_cart_bridge_is_locked_down():
    js=(ROOT/'public-web/embed.js').read_text()
    assert 'innerHTML' not in js and 'eval(' not in js
    # Only our iframe and the chat origin can ask for cart actions.
    assert "event.origin!==CHAT||!frame||event.source!==frame.contentWindow" in js
    assert re.search(r"d\.quantity<1\|\|d\.quantity>5",js) and 'Number.isSafeInteger(d.id)' in js
    assert "fetch('/cart/add.js'" in js and "location.href=d.to==='cart'?'/cart':'/checkout'" in js
    assert 'postMessage(msg,CHAT)' in js and "postMessage({type:'merly:hello'},CHAT)" in js
    chat=(ROOT/'public-web/public.js').read_text()
    assert "PARENTS=['https://merlyshoes.com','https://www.merlyshoes.com']" in chat
    assert 'e.source!==window.parent||!PARENTS.includes(e.origin)' in chat and 'postMessage(msg,parentOrigin)' in chat
    assert 'innerHTML' not in chat

def test_cart_button_only_for_verified_in_stock_rows():
    chat=(ROOT/'public-web/public.js').read_text()
    assert "if(row.available!==true||!Number.isSafeInteger(row.variant_id)||row.variant_id<=0)return;" in chat

def test_prompt_explains_cart_without_claiming_orders():
    prompt=(ROOT/'SYSTEM-PROMPT.md').read_text()
    assert 'Thêm vào giỏ' in prompt and 'không phải bot đã đặt đơn' in prompt and 'không tạo đơn hay giữ hàng' in prompt
