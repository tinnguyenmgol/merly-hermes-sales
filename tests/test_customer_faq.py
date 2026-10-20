import copy,json
from pathlib import Path
import pytest
import merly_tools as tools
ROOT=Path(__file__).resolve().parents[1]
FAQ=json.loads((ROOT/'vendor/knowledge-customer-faq.json').read_text())

def test_schema_matches_policy_topics():
    d=json.loads((ROOT/'tool-schema.json').read_text())
    enum=d['paths']['/tools/get_policy']['post']['requestBody']['content']['application/json']['schema']['properties']['topic']['enum']
    assert set(enum)==set(tools.POLICY_TOPICS)

@pytest.mark.parametrize('topic',list(FAQ['policies']))
def test_approved_customer_policies(topic,monkeypatch):
    monkeypatch.setattr(tools.h,'get',lambda *a,**kw:pytest.fail('policy must not fetch Haravan'))
    r=tools.dispatch('get_policy',{'topic':topic})
    assert r['status']=='approved' and r['text']==FAQ['policies'][topic]
    assert r['sources']==[FAQ['source']]
    assert not r['eligibility_confirmed'] and not r['stacking_confirmed']

def test_only_public_subset_and_no_unapproved_extras():
    text=json.dumps(FAQ,ensure_ascii=False).casefold()
    for forbidden in ['merly.io.vn','chatgpt.com/g/','baohanh.merlyshoes.com','lương','chấm công','attendance','giá vốn','lợi nhuận','mst','cần duyệt']:
        assert forbidden not in text
    exchange=FAQ['policies']['size_exchange']
    assert '30 ngày' not in exchange and '01 lần' not in exchange
    assert '20.000đ' in exchange and '30%' in exchange
    assert '365 ngày' in FAQ['policies']['warranty']
    assert '300.000đ sau giảm' in FAQ['policies']['shipping']
    assert '5%' in FAQ['policies']['new_customer'] and '30.000đ' in FAQ['policies']['new_customer']
    assert tools.get_policy({'topic':'store_hours'})['status']=='unverified'
    assert tools.get_policy({'topic':'store_address'})['status']=='unverified'

@pytest.fixture
def local(monkeypatch,tmp_path):
    (tmp_path/'vendor').mkdir()
    faq=copy.deepcopy(FAQ)
    old={'approved':False,'sources':[{'effective_date':'2026-09-21'}],'shipping':'older text'}
    def save():
        (tmp_path/'vendor/knowledge-customer-faq.json').write_text(json.dumps(faq))
        (tmp_path/'vendor/knowledge-public-draft.json').write_text(json.dumps(old))
    monkeypatch.setattr(tools,'ROOT',tmp_path);save()
    return faq,old,save

def test_approval_only_customer_scope(local):
    faq,old,save=local
    faq['approved']=False;save()
    assert tools.get_policy({'topic':'shipping'})['status']=='unverified'
    faq['approved']=True;faq['scope']='employees';save()
    assert tools.get_policy({'topic':'shipping'})['status']=='unverified'

def test_later_approved_policy_wins(local):
    faq,old,save=local;old['approved']=True
    old['sources'][0]['effective_date']='2026-10-01';save()
    assert tools.get_policy({'topic':'shipping'})['text']=='older text'
    old['sources'][0]['effective_date']='2026-09-01';save()
    assert tools.get_policy({'topic':'shipping'})['text']==faq['policies']['shipping']

def test_same_date_conflict_fails_closed(local):
    faq,old,save=local;old['approved']=True;save()
    r=tools.get_policy({'topic':'shipping'})
    assert r['status']=='needs_staff_confirmation' and 'text' not in r

@pytest.mark.parametrize('bad',['','2026-02-30','2026-9-21',None])
def test_undated_source_not_assumed_current(local,bad):
    faq,old,save=local;faq['source']['updated_date']=bad;save()
    assert tools.get_policy({'topic':'shipping'})['status']=='needs_staff_confirmation'

def test_sales_soul_migration_preserves_custom_text_and_is_idempotent(tmp_path):
    import run_sales
    p=tmp_path/'SOUL.md';original=b'Owner custom rules\r\nDo not create orders.\r\n'
    p.write_bytes(original)
    assert run_sales.ensure_customer_policy_prompt(tmp_path)
    assert p.read_bytes().startswith(original)
    assert 'new_customer' in p.read_text()
    assert p.stat().st_mode&0o777==0o600
    assert not run_sales.ensure_customer_policy_prompt(tmp_path)
    assert not list(tmp_path.glob('.merly-faq-*'))

def test_existing_soul_policy_block_updated_without_losing_surroundings(tmp_path):
    import run_sales
    p=tmp_path/'SOUL.md'
    p.write_text('before\n<!-- MERLY_CUSTOMER_FAQ_POLICY_BEGIN -->\nold\n<!-- MERLY_CUSTOMER_FAQ_POLICY_END -->\nafter')
    assert run_sales.ensure_customer_policy_prompt(tmp_path)
    assert p.read_text().startswith('before\n') and p.read_text().endswith('\nafter')

def test_sales_soul_does_not_follow_symlink(tmp_path):
    import run_sales
    other=tmp_path/'other-profile.md';other.write_text('untouched')
    (tmp_path/'SOUL.md').symlink_to(other)
    with pytest.raises(RuntimeError,match='symlink'):run_sales.ensure_customer_policy_prompt(tmp_path)
    assert other.read_text()=='untouched'

def test_malformed_sales_soul_markers_fail_without_write(tmp_path):
    import run_sales
    p=tmp_path/'SOUL.md';p.write_text('owner\n<!-- MERLY_CUSTOMER_FAQ_POLICY_BEGIN -->')
    before=p.read_bytes()
    with pytest.raises(RuntimeError,match='markers'):run_sales.ensure_customer_policy_prompt(tmp_path)
    assert p.read_bytes()==before
