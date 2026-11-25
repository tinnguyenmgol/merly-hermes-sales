"""Owner report from the insights store. Read-only; run inside the gateway container:
    python insights_report.py                 # last 7 days
    python insights_report.py --days 30
    python insights_report.py --chats 10      # show more conversations to review
    python insights_report.py --session <id>  # one full conversation
    python insights_report.py --json          # machine-readable
"""
import argparse,json,sqlite3,statistics,sys,time
from collections import Counter
import insights

OUTCOME={'available':'còn hàng','partial_available':'còn hàng (tra chưa hết kho)','verified_zero':'hết hàng','no_variant':'không có size/màu này',
         'no_match':'không có mẫu khớp','partial_no_match':'chưa tìm ra (tra chưa hết)','metadata_missing':'thiếu dữ liệu sản phẩm',
         'source_error':'lỗi tra kho','partial':'lỗi tra kho','catalog_loading':'danh mục đang cập nhật','unverified':'lỗi tra kho'}
TOPIC={'shipping':'Giao hàng','size_exchange':'Đổi size','warranty':'Bảo hành','store_hours':'Giờ mở cửa','store_address':'Địa chỉ cửa hàng',
       'sale_returns':'Đổi trả hàng sale','new_customer':'Ưu đãi khách mới','loyalty':'Thành viên','business_orders':'Đơn số lượng lớn',
       'tiktok_exchange':'Đổi hàng TikTok','product_links':'Link sản phẩm','customer_support':'Chăm sóc khách hàng'}
REASON={'turn_not_completed':'nhà cung cấp AI từ chối/lỗi','hermes_timeout':'AI trả lời quá lâu','hermes_unavailable':'không kết nối được AI',
        'pilot_unavailable':'lỗi hệ thống','daily_budget_limit':'hết lượt AI trong ngày','ai_minute_limit':'quá nhiều lượt AI/phút',
        'ai_capacity':'AI đang bận','turn_in_progress':'khách gửi khi câu trước chưa xong','stock_rate_limit':'quá nhiều lượt tra kho',
        'stock_capacity':'kho đang bận','stock_probe_unavailable':'không tra được kho'}

def load(days):
    db=insights.connect(readonly=True)
    try:
        since=time.time()-days*86400
        db.row_factory=sqlite3.Row
        turns=[dict(r) for r in db.execute('SELECT * FROM turns WHERE ts>=? ORDER BY ts',(since,))]
        found=[dict(r) for r in db.execute('SELECT s.*,t.session FROM searches s JOIN turns t ON t.id=s.turn_id WHERE s.ts>=? ORDER BY s.ts',(since,))]
        try:events=[dict(r) for r in db.execute('SELECT * FROM events WHERE ts>=?',(since,))]
        except sqlite3.OperationalError:events=[]
        return turns,found,events
    finally:db.close()

FUNNEL=(('open_teaser','Bấm lời chào'),('open_button','Bấm nút trợ lý'),('size_chip','Chọn size nhanh'),('add_to_cart','Thêm vào giỏ từ chat'),('add_to_cart_failed','Thêm giỏ lỗi'),('checkout','Bấm thanh toán từ chat'))

def funnel(events):
    out=[]
    for name,label in FUNNEL:
        rows=[e for e in events if e['name']==name]
        out.append({'name':name,'label':label,'count':len(rows),'visitors':len({e['session'] for e in rows})})
    return out

def summarize(turns,found,chats=5,events=()):
    for s in found:
        if s['positive_skus']>0 and s['outcome'] in ('partial','source_error','unverified','catalog_loading'):s['outcome']='partial_available'
    ok=[t for t in turns if t['status']=='ok'];failed=[t for t in turns if t['status']=='failed'];limited=[t for t in turns if t['status']=='limited']
    topics=Counter(TOPIC.get(x,x) for t in ok for x in json.loads(t['policy_topics'] or '[]'))
    search_turns={s['turn_id'] for s in found}
    def top(key,fmt=str,n=10):
        return [[fmt(v),c] for v,c in Counter(s[key] for s in found if s[key] not in (None,'')).most_common(n)]
    unmet=Counter();unmet_outcomes={}
    for s in found:
        if s['positive_skus']>0:continue
        key=tuple((k,s[k]) for k in ('category','model_code','size','color','heel_cm','occasion','query') if s[k] not in (None,''))
        if not key:continue
        unmet[key]+=1;unmet_outcomes.setdefault(key,Counter())[OUTCOME.get(s['outcome'],s['outcome'])]+=1
    review=[]
    for t in reversed(turns):
        if t['session'] in review:continue
        if t['status']!='ok' or json.loads(t['guard_reasons'] or '[]') or t['lookup_incomplete']:review.append(t['session'])
        if len(review)>=chats:break
    return {
        'turns':len(turns),'visitors':len({t['session'] for t in turns}),
        'per_day':sorted(Counter(t['day'] for t in turns).items()),
        'answered':len(ok),'failed':len(failed),'limited':len(limited),
        'failure_reasons':[[REASON.get(r,r),c] for r,c in Counter(t['reason'] for t in failed+limited).most_common()],
        'quick_stock':sum(1 for t in ok if t['engine']=='haravan-readonly'),'ai':sum(1 for t in ok if t['engine']=='hermes'),
        'median_seconds':round(statistics.median(t['elapsed_ms'] for t in ok if t['elapsed_ms'] is not None)/1000,1) if any(t['elapsed_ms'] is not None for t in ok) else None,
        'product_search_turns':len(search_turns),'clarification_turns':sum(t['needs_clarification'] for t in ok),
        'policy_topics':topics.most_common(),
        'sizes':top('size'),'colors':top('color'),'categories':top('category'),'heels':top('heel_cm',lambda v:f'{v:g}cm'),
        'models':top('model_code'),'occasions':top('occasion'),'queries':top('query'),
        'outcomes':[[OUTCOME.get(k,k),c] for k,c in Counter(s['outcome'] for s in found).most_common()],
        'unmet_demand':[{'criteria':dict(k),'count':c,'outcomes':dict(unmet_outcomes[k])} for k,c in unmet.most_common(15)],
        'review_sessions':review,
        'funnel':funnel(list(events)),
    }

def dashboard(days=7,chats=10):
    """Data for the /admin page: summary plus the transcripts worth reviewing."""
    if not insights.path().exists():
        return {'days':days,'no_data':True,**summarize([],[],0),'reasons':REASON,'conversations':{}}
    turns,found,events=load(days);s=summarize(turns,found,chats,events)
    recent=[]
    for t in reversed(turns):
        if t['session'] not in recent:recent.append(t['session'])
        if len(recent)>=chats:break
    sessions=list(dict.fromkeys(s['review_sessions']+recent))[:chats*2]
    return {'days':days,'no_data':False,**s,'recent_sessions':recent,'conversations':{k:conversation(k,8) for k in sessions},'reasons':REASON,'retention_days':insights.retention_days()}

def conversation(session,limit=12):
    db=insights.connect(readonly=True)
    try:
        db.row_factory=sqlite3.Row
        return [dict(r) for r in db.execute('SELECT day,turn,status,reason,engine,message,reply,shown FROM turns WHERE session=? ORDER BY turn DESC LIMIT ?',(session,limit))][::-1]
    finally:db.close()

def describe(criteria):
    labels={'category':'','model_code':'mã ','size':'size ','color':'màu ','heel_cm':'gót ','occasion':'dịp ','query':'"'}
    out=[]
    for k,v in criteria.items():
        v=f'{v:g}cm' if k=='heel_cm' else v
        out.append(labels[k]+str(v)+('"' if k=='query' else ''))
    return ' · '.join(out)

def print_chat(session,rows,width=300):
    print(f'  ── Phiên {session} ({rows[0]["day"] if rows else ""})')
    for r in rows:
        print('   Khách:',(r['message'] or '')[:width])
        if r['status']!='ok':print('   [Không trả lời được:',REASON.get(r['reason'],r['reason']),']')
        else:print('   Bot:  ',(r['reply'] or '')[:width].replace('\n',' '),f'[{r["shown"]} thẻ]' if r['shown'] else '')

def render(days,s,chats):
    pct=lambda a,b:f'{round(100*a/b)}%' if b else '0%'
    print(f'BÁO CÁO TRỢ LÝ MERLY · {days} ngày gần nhất')
    print('='*60)
    print(f'Tổng lượt khách nhắn: {s["turns"]} · Số khách (phiên chat): {s["visitors"]}')
    print(f'Trả lời được: {s["answered"]} ({pct(s["answered"],s["turns"])}) · Lỗi: {s["failed"]} · Bị giới hạn lượt: {s["limited"]}')
    print(f'Tra tồn nhanh theo mã: {s["quick_stock"]} · Tư vấn AI: {s["ai"]} · Thời gian trả lời (trung vị): {s["median_seconds"]}s')
    if s['per_day']:print('Theo ngày:',', '.join(f'{d}: {c}' for d,c in s['per_day']))
    if s['failure_reasons']:print('Lý do không trả lời được:',', '.join(f'{r} ({c})' for r,c in s['failure_reasons']))
    if any(f['count'] for f in s['funnel']):
        print('\nPHỄU CHỐT ĐƠN (khách)')
        for f in s['funnel']:
            if f['count']:print(f'- {f["label"]}: {f["visitors"]} khách ({f["count"]} lần)')
    print('\nKHÁCH HỎI GÌ')
    print(f'- Tìm/tra hàng: {s["product_search_turns"]} lượt · Bot phải hỏi lại khách: {s["clarification_turns"]} lượt')
    if s['policy_topics']:print('- Chính sách:',', '.join(f'{t} ({c})' for t,c in s['policy_topics']))
    print('\nKHÁCH TÌM GÌ')
    for label,key in (('Size','sizes'),('Màu','colors'),('Kiểu','categories'),('Chiều cao gót','heels'),('Mã mẫu','models'),('Dịp','occasions'),('Từ khoá','queries')):
        if s[key]:print(f'- {label}:',', '.join(f'{v} ({c})' for v,c in s[key]))
    if s['outcomes']:print('- Kết quả tra:',', '.join(f'{v} ({c})' for v,c in s['outcomes']))
    print('\nNHU CẦU CHƯA ĐÁP ỨNG (khách tìm nhưng không có hàng để giới thiệu)')
    if not s['unmet_demand']:print('- Chưa có')
    for row in s['unmet_demand']:
        print(f'- {describe(row["criteria"])}: {row["count"]} lượt →',', '.join(f'{k} {v}' for k,v in row['outcomes'].items()))
    if chats and s['review_sessions']:
        print(f'\nĐOẠN CHAT NÊN XEM LẠI (lỗi hoặc bot chưa trả lời trọn) · tối đa {chats}')
        for session in s['review_sessions']:print_chat(session,conversation(session,8))
    print('\nĐã che số điện thoại, email và dãy số dài. Xem một phiên: python insights_report.py --session <mã phiên>')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--days',type=int,default=7);p.add_argument('--chats',type=int,default=5)
    p.add_argument('--session');p.add_argument('--json',action='store_true')
    a=p.parse_args(argv)
    if not 1<=a.days<=365 or not 0<=a.chats<=50:p.error('days 1-365, chats 0-50')
    if not insights.path().exists():print('Chưa có dữ liệu (chưa có lượt chat nào được ghi).');return 0
    if a.session:
        rows=conversation(a.session,50)
        if a.json:print(json.dumps(rows,ensure_ascii=False,indent=2))
        elif rows:print_chat(a.session,rows,2000)
        else:print('Không tìm thấy phiên này (có thể đã quá hạn lưu).')
        return 0
    turns,found,events=load(a.days);s=summarize(turns,found,a.chats,events)
    if a.json:print(json.dumps(s,ensure_ascii=False,indent=2))
    else:render(a.days,s,a.chats)
    return 0

if __name__=='__main__':sys.exit(main())
