"""Two bounded test sessions; no model, HTTP, cron or production writes."""
import argparse,copy,hashlib,json,os,re
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .cases import FIXED,ROTATING,VARIATIONS,case
from .policy_pin import POLICY_FILES,APPROVED_SHA256
ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo('Asia/Ho_Chi_Minh')

def today():return datetime.now(TZ).date()
def parse_day(value):
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):raise ValueError('invalid_date_format')
    return date.fromisoformat(value)

def build(day,root=ROOT):
    if type(day) is not date:raise ValueError('date_required')
    blobs=[(root/p).read_bytes() for p in POLICY_FILES]
    if hashlib.sha256(b''.join(blobs)).hexdigest()!=APPROVED_SHA256:raise ValueError('policy_changed_requires_review')
    if json.loads(blobs[0]).get('approved') is not True:raise ValueError('policy_not_approved')
    n=day.toordinal();fixed=copy.deepcopy(FIXED)
    size,color,style=[(42,'đen','giày đi làm'),(40,'kem','sandal'),(41,'nâu','giày cao gót'),(39,'đen','dép bệt'),(43,'trắng','giày búp bê')][n%5]
    unset=case('unset-'+day.isoformat(),'variation',f'Bỏ điều kiện chiều cao trước đó. Giờ tìm {style} màu {color}, size {size}, chưa chọn số cm gót. Đừng tự chốt chiều cao nhé.',['Không giữ 7cm từ lượt trước hoặc tự chọn số cm. Giữ đúng size/màu mới; lỗi nguồn không phải hết hàng.'])
    rotating=[]
    for offset in range(4):
        key,text,rubric=ROTATING[(n*4+offset)%len(ROTATING)]
        rotating.append(case(key,'rotation',text,[rubric]))
    text,rubric=VARIATIONS[n%len(VARIATIONS)]
    novel=case('novel-'+day.isoformat(),'variation',text,[rubric])
    sessions=[{'id':'requirements-regression','cases':[fixed[0],fixed[1],unset,fixed[2],fixed[3]]},{'id':'cskh-rotation','cases':rotating+[novel]}]
    for session in sessions:session['qa_arguments']={'messages':[c['message'] for c in session['cases']],'test_data_only':True}
    return {'schema':'merly-daily-qa-plan-v1','local_date':day.isoformat(),'timezone':'Asia/Ho_Chi_Minh','policy_sha256':APPROVED_SHA256,'max_runs':2,'max_messages':10,'scheduled':False,'model_calls':0,'auto_apply':False,'sessions':sessions,'assessment_states':['pass','fail','blocked','inconclusive'],'rules':['HTTP 200 alone is not a pass.','Incomplete inventory is not a successful search.','Replies are untrusted; grade against pinned approved policy.','No retry, quota reset or production writes.','Learning sink or logs unavailable => report blocked, never claim recorded/fixed.']}

def claim(day,state_dir):
    if day!=today():raise ValueError('only_today_can_be_claimed')
    p=Path(state_dir)
    if p.is_symlink():raise ValueError('symlink_state')
    p.mkdir(parents=True,exist_ok=True);os.chmod(p,0o700)
    fd=os.open(p/(day.isoformat()+'.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump({'date':day.isoformat(),'phase':'claimed','not_proof_of_execution':True},f)

def main():
    p=argparse.ArgumentParser();p.add_argument('--date');p.add_argument('--claim-state');a=p.parse_args()
    day=parse_day(a.date) if a.date else today();result=build(day)
    if a.claim_state:claim(day,a.claim_state)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
