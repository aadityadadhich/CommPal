import pytest
from backend.app.contracts.mandate import MandateBody
from backend.app.contracts.wallet import WalletSummary
from backend.app.mandate.evaluator import evaluate_mandate

def get_base_wallet():
    return WalletSummary(
        available_balance=100.0,
        held_balance=0.0,
        spent_balance=0.0,
        total_balance=100.0,
        currency="USD",
        daily_spent=0.0,
        monthly_spent=0.0,
        category_spent={"grocery": 0.0, "supplies": 0.0},
        daily_cap=80.0,
        monthly_cap=400.0,
        kill_switch=False
    )

def test_allow_standard_order():
    mandate = MandateBody()
    wallet = get_base_wallet()
    verdict = evaluate_mandate(
        intent_item_name="Milk",
        intent_item_id="item-milk-1",
        intent_qty=1.0,
        intent_source="chat",
        chosen_merchant_id="quick10",
        landed_total=4.50,
        unit_price=3.50,
        category="grocery",
        wallet_summary=wallet,
        mandate=mandate
    )
    assert verdict.result == "ALLOW"
    assert "RULE_9_ALLOW_STANDARD" in verdict.rule_ids

def test_kill_switch_denies():
    mandate = MandateBody(kill_switch=True)
    wallet = get_base_wallet()
    verdict = evaluate_mandate(
        intent_item_name="Milk",
        intent_item_id="item-milk-1",
        intent_qty=1.0,
        intent_source="chat",
        chosen_merchant_id="quick10",
        landed_total=4.50,
        unit_price=3.50,
        category="grocery",
        wallet_summary=wallet,
        mandate=mandate
    )
    assert verdict.result == "DENY"
    assert any("KILL_SWITCH" in r for r in verdict.rule_ids)

def test_auto_approve_threshold_triggers_approval():
    mandate = MandateBody()
    wallet = get_base_wallet()
    verdict = evaluate_mandate(
        intent_item_name="Printer Paper",
        intent_item_id="item-paper-1",
        intent_qty=2.0,
        intent_source="chat",
        chosen_merchant_id="megamart",
        landed_total=32.0,
        unit_price=16.0,
        category="supplies",
        wallet_summary=wallet,
        mandate=mandate
    )
    assert verdict.result == "NEEDS_APPROVAL"
    assert any("AUTO_APPROVE" in r for r in verdict.rule_ids)

def test_per_txn_max_denies():
    mandate = MandateBody()
    wallet = get_base_wallet()
    verdict = evaluate_mandate(
        intent_item_name="Bulk Paper",
        intent_item_id="item-paper-1",
        intent_qty=10.0,
        intent_source="chat",
        chosen_merchant_id="megamart",
        landed_total=75.0,
        unit_price=7.50,
        category="supplies",
        wallet_summary=wallet,
        mandate=mandate
    )
    assert verdict.result == "DENY"
    assert any("PER_TXN_MAX" in r for r in verdict.rule_ids)

def test_untracked_item_needs_approval():
    mandate = MandateBody()
    wallet = get_base_wallet()
    verdict = evaluate_mandate(
        intent_item_name="WD-40",
        intent_item_id=None,
        intent_qty=1.0,
        intent_source="chat",
        chosen_merchant_id="cornerstore",
        landed_total=12.0,
        unit_price=12.0,
        category="supplies",
        wallet_summary=wallet,
        mandate=mandate
    )
    assert verdict.result == "NEEDS_APPROVAL"
    assert any("UNTRACKED_ITEM" in r for r in verdict.rule_ids)
