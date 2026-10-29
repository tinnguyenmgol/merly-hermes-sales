"""Owner-approved policy content/provenance delivery, no live customer lookup."""
from pathlib import Path
import json
import policy_knowledge as p
ROOT=Path(__file__).resolve().parents[1]


def test_first_purchase_registration_policy_is_approved_without_personal_attestation():
    row=p.get(ROOT,'new_customer')
    assert row['status']=='approved'
    assert 'chưa từng mua hàng' in row['text'] and 'tạo tài khoản sẽ được giảm ngay 5%' in row['text']
    assert 'tối đa 30.000đ' in row['text']
    assert row['eligibility_confirmed'] is False and row['stacking_confirmed'] is False
    assert any(s['file']=='POLICY-ACCOUNT-DISCOUNTS-OWNER.md' for s in row['sources'])


def test_existing_customer_uses_history_without_resetting_tiers():
    row=p.get(ROOT,'loyalty')
    assert row['status']=='approved'
    assert 'theo lịch sử mua hàng' in row['text'] and 'từ 5% đến 20%' in row['text']
    assert all(t in row['text'] for t in ('Member+','Silver+','Gold+','Diamond+','Platinum+'))
    assert row['eligibility_confirmed'] is False


def test_rules_reach_same_native_context_and_shipping_policy_is_unchanged():
    instructions,revision,count=p.context(ROOT)
    snapshot=json.loads(instructions.rsplit('\n',1)[-1])
    assert snapshot['personal_eligibility_verified'] is False and snapshot['stacking_verified'] is False
    rows={r['topic']:r for r in snapshot['policies']}
    assert 'tạo tài khoản sẽ được giảm ngay 5%' in rows['new_customer']['text']
    assert 'theo lịch sử mua hàng' in rows['loyalty']['text']
    assert '300.000đ sau giảm' in rows['shipping']['text']
    assert len(revision)==64
