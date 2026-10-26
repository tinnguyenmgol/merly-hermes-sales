"""Bounded, isolated history of delivered turns; no intent parsing or learned facts.
The adapter owns the transcript so fast replies and safety overrides are visible
on the next Hermes turn. Old cards are references, never fresh stock evidence.
"""
import json,time
import state
TTL=1800
MAX_SESSIONS=64
MAX_TURNS=8
MAX_BYTES=64000

def _db():
    db=state.database()
    db.execute('CREATE TABLE IF NOT EXISTS dialogue_v2 (sid TEXT PRIMARY KEY, turns TEXT NOT NULL, seen REAL NOT NULL)')
    return db

def sid(user):
    prefix='merly-sales:web:'
    return user[len(prefix):] if user.startswith(prefix) else user

def _view(answer):
    def compact(value):
        if isinstance(value,dict):return {k:compact(v) for k,v in value.items() if k not in ('image_url','image_scope')}
        if isinstance(value,list):return [compact(v) for v in value]
        return value
    view={k:compact(answer[k]) for k in ('stock_options','products','quotes') if k in answer}
    if view and isinstance(answer.get('listing'),dict) and answer['listing'].get('shown',0)>0:view['listing']=compact(answer['listing'])
    if answer.get('clarification_options'):view['choices_shown']=list(answer['clarification_options'])
    if not view:return ''
    raw=json.dumps(view,ensure_ascii=False,separators=(',',':'))
    # Never cut a JSON object or invent missing card positions.
    if len(raw.encode())>40000:
        return 'Thẻ của lượt này quá dài nên không được giữ lại. Nếu cần chọn mẫu, phải tra lại; không đoán thứ tự thẻ.'
    return '\n[Thẻ/lựa chọn đã hiển thị; dữ liệu LỊCH SỬ, không xác nhận tồn/giá hiện tại; gợi ý chưa phải khách xác nhận]\n'+raw

@state.serialized
def history(key):
    db=_db()
    try:
        row=db.execute('SELECT turns FROM dialogue_v2 WHERE sid=? AND seen>=?',(key,time.time()-TTL)).fetchone()
        turns=json.loads(row[0]) if row else []
        result=[]
        for turn in turns:
            result.extend([{'role':'user','content':turn['user']},{'role':'assistant','content':turn['reply']+turn.get('view','')}])
        return result
    finally:db.close()

@state.serialized
def record(key,message,answer):
    if not isinstance(message,str) or not 1<=len(message)<=2000 or not isinstance(answer.get('reply'),str) or not 1<=len(answer['reply'])<=12000:raise ValueError('invalid_delivered_turn')
    now=time.time();db=_db()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM dialogue_v2 WHERE seen<?',(now-TTL,))
            row=db.execute('SELECT turns FROM dialogue_v2 WHERE sid=?',(key,)).fetchone()
            turns=json.loads(row[0]) if row else []
            turns.append({'user':message,'reply':answer['reply'],'view':_view(answer)})
            turns=turns[-MAX_TURNS:]
            while len(turns)>1 and len(json.dumps(turns,ensure_ascii=False).encode())>MAX_BYTES:turns.pop(0)
            raw=json.dumps(turns,ensure_ascii=False)
            # Keep actual speech even if a large card set has to be omitted.
            if len(raw.encode())>MAX_BYTES:
                turns[-1]['view']='\n[Không lưu bộ thẻ quá dài; cần tra mới trước khi chọn.]'
                raw=json.dumps(turns,ensure_ascii=False)
            if len(raw.encode())>MAX_BYTES:raise ValueError('delivered_turn_too_large')
            db.execute('INSERT INTO dialogue_v2 VALUES(?,?,?) ON CONFLICT(sid) DO UPDATE SET turns=excluded.turns,seen=excluded.seen',(key,raw,now))
            db.execute('DELETE FROM dialogue_v2 WHERE sid IN (SELECT sid FROM dialogue_v2 ORDER BY seen DESC,sid LIMIT -1 OFFSET ?)',(MAX_SESSIONS,))
    finally:db.close()

@state.serialized
def forget(key):
    db=_db()
    try:
        with db:db.execute('DELETE FROM dialogue_v2 WHERE sid=?',(key,))
    finally:db.close()
