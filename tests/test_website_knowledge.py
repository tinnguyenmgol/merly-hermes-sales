"""Public source snapshot and transport contracts, not model semantic accuracy."""
import json,re
from pathlib import Path
import pytest
import website_knowledge as w,policy_knowledge as k,merly_tools as tools,hermes_client as client
from test_client import approved,responses
ROOT=Path(__file__).resolve().parents[1]
def payload():return json.loads((ROOT/'vendor/knowledge-website-reference.json').read_text())
def write(root,data):
    (root/'vendor').mkdir(exist_ok=True)
    (root/'vendor/knowledge-website-reference.json').write_text(json.dumps(data))
    (root/'vendor/knowledge-customer-faq.json').write_bytes((ROOT/'vendor/knowledge-customer-faq.json').read_bytes())

def test_public_snapshot_is_bounded_and_fully_sourced():
    d=w.load(ROOT);assert len(d['items'])==10 and len(d['sources'])==12
    assert {i['topic'] for i in d['items']}==w.TOPICS
    assert all(i['status']=='reference_only' and all(s in d['sources'] for s in i['source_ids']) for i in d['items'])
    assert all(w.document_url(s['url']) for s in d['sources'].values())
    audit=json.loads((ROOT/'vendor/website-source-review.json').read_text());rows=audit['sources'];summary=audit['summary']
    assert summary['urls']==len(rows)==154 and summary['http200']==sum(r['status']==200 for r in rows)==154
    assert summary['pages']==sum('/pages/' in r['url'] for r in rows)==37
    assert summary['blogs']==sum('/blogs/' in r['url'] for r in rows)==117
    assert summary['no_extractable_text']==sum(r['text_chars']==0 for r in rows)==6

def test_shared_prompt_tool_and_policy_precedence():
    context,revision,count=k.context(ROOT);snapshot=json.loads(context.rsplit('\n',1)[-1]);assert count==12 and len(context.encode())<32000
    for row in snapshot['policies']:assert row==tools.get_policy({'topic':row['topic']})
    support=tools.get_policy({'topic':'customer_support'});assert support['website_reference']==w.load(ROOT)
    policy=' '.join(row['text'] for row in snapshot['policies'])
    assert '20.000đ/đơn' in policy and '30%' in policy and '365' in policy and '300.000đ' in policy
    for bad in ['JUNO','VUICUOITUAN','atada.vn','35.000đ','90 ngày','250.000vnd']:
        assert bad not in context
    assert not re.search(r'(?<![A-Za-z0-9])\d{12,18}(?![A-Za-z0-9])',context)
    assert not re.search(r'[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',context)
    links=support['website_reference']['customer_links']
    assert 'https://merlyshoes.com/pages/cau-hoi-thuong-gap' not in links
    assert 'https://merlyshoes.com/pages/chinh-sach-thanh-toan' not in links
    assert 'https://merlyshoes.com/pages/huong-dan-do-size-giay' in links

def test_native_transport_contains_sources_without_stock_calls(approved,monkeypatch):
    seen=[];monkeypatch.setattr(client,'audit',lambda:True)
    def request(path,p):seen.append((path,p));return responses()
    monkeypatch.setattr(client,'request',request)
    out=client.chat('đo vòng chân sao, đăng ký tài khoản ở đâu?','website-fixture')
    assert len(seen)==1 and seen[0][0]=='/responses'
    assert seen[0][1]['input']=='đo vòng chân sao, đăng ký tài khoản ở đâu?'
    assert 'measurement_help' in seen[0][1]['instructions'] and 'html_sha256' in seen[0][1]['instructions']
    assert set(w.load(ROOT)['customer_links'])<=set(out['source_links'])
    assert out['answer_mode']=='native' and out['approved_policy_topics']==12

@pytest.mark.parametrize('mode',['unapproved','employee_scope','bad_json','unknown_topic','bad_status','no_sources','missing_ref','bad_hash','undated_source','non_https','credentials','foreign_host','query','fragment','bad_link','duplicate_topic','too_large','symlink'])
def test_invalid_website_never_poison_approved_policies(tmp_path,mode):
    d=payload();source=next(iter(d['sources'].values()))
    if mode=='unapproved':d['approved']=False
    if mode=='employee_scope':d['scope']='employees'
    if mode=='unknown_topic':d['items'][0]['topic']='employee_payroll'
    if mode=='bad_status':d['items'][0]['status']='approved'
    if mode=='no_sources':d['sources']={}
    if mode=='missing_ref':d['items'][0]['source_ids']=['missing']
    if mode=='bad_hash':source['html_sha256']='invalid'
    if mode=='undated_source':source['retrieved_at']='2026-10-23'
    if mode=='non_https':source['url']='http://merlyshoes.com/pages/lien-he'
    if mode=='credentials':source['url']='https://u:pass@merlyshoes.com/pages/lien-he'
    if mode=='foreign_host':source['url']='https://merlyshoes.com.evil.invalid/pages/lien-he'
    if mode=='query':source['url']+='?token=UNTRUSTED_SENTINEL'
    if mode=='fragment':source['url']+='#UNTRUSTED_SENTINEL'
    if mode=='bad_link':d['customer_links']=['javascript:alert(1)']
    if mode=='duplicate_topic':d['items'][1]['topic']=d['items'][0]['topic']
    d['items'][0]['text']='UNTRUSTED_SENTINEL'
    write(tmp_path,d);p=tmp_path/'vendor/knowledge-website-reference.json'
    if mode=='bad_json':p.write_text('{')
    if mode=='too_large':p.write_text(' '*65537)
    if mode=='symlink':target=tmp_path/'outside.json';p.rename(target);p.symlink_to(target)
    with pytest.raises(w.InvalidWebsiteKnowledge):w.load(tmp_path)
    text,_,count=k.context(tmp_path)
    assert count==12 and 'UNTRUSTED_SENTINEL' not in text and '20.000đ/đơn' in text
    assert k.get(tmp_path,'customer_support')['status']=='approved'
    assert k.get(tmp_path,'customer_support')['website_reference']['status']=='unverified'

def test_missing_file_is_optional_and_revision_tracks_website(tmp_path):
    write(tmp_path,payload());before=k.context(tmp_path)[1]
    d=payload();d['items'][0]['text']+=' Thay đổi bản tham khảo.';write(tmp_path,d)
    assert k.context(tmp_path)[1]!=before
    (tmp_path/'vendor/knowledge-website-reference.json').unlink()
    assert w.load(tmp_path) is None and 'website_reference' not in k.get(tmp_path,'customer_support')
    assert k.context(tmp_path)[2]==12

def test_images_package_curated_loader():
    assert '!website_knowledge.py' in (ROOT/'.dockerignore').read_text()
    for name in ('Dockerfile.hermes','Dockerfile.adapter'):
        assert 'COPY website_knowledge.py policy_knowledge.py' in (ROOT/name).read_text()
    assert set(tools.TOOLS)=={'search_products','quote_variant','size_guide','get_policy','get_promotions'}
