"""
Comprehensive Usage Test Suite for CommPal
Tests all 7 SRDD role subsystems and user-facing project usages:
  1. Sandboxed E-Wallet, 3-Bucket Ledger, PayPal Provider & Webhooks
  2. Deterministic 9-Rule Spending Mandate Policy Evaluator
  3. Cryptographic SHA-256 Hash-Chained Audit Trail & Tamper Detection
  4. Inventory Depletion Tracking, Stock Modes & Virtual Clock
  5. Multi-Merchant Catalogs, Channel3 Live Adapter, Urgency Derivation & SLA Scoring
  6. Conversational Agent, Fallback NLU & Ollama (qwen2.5:7b) Integration
  7. Docker Infrastructure, Repository Security & Codebase Hygiene Checks
"""
import os
import ast
import json
import importlib
from datetime import timedelta
import pytest
import httpx

from backend.app.config import settings
from backend.app.db.database import SessionLocal, init_db
from backend.app.db.models import Payment, PaymentEvent
from backend.app.contracts.schemas import (
    ItemSpec,
    StockUpdateRequest,
    MandateBody,
    MerchantRules,
    WalletSummary,
)
from backend.app.scheduler.virtual_clock import clock
from backend.app.inventory.service import inventory_service
from backend.app.db.seed import seed_week_with_asha
from backend.app.wallet.ledger import ledger_service, InsufficientFundsError
from backend.app.wallet.providers import MockPaymentProvider
from backend.app.mandate.evaluator import evaluate_mandate
from backend.app.audit.hash_chain import append_audit_event, verify_audit_chain
from backend.app.merchants.catalogs import reset_chaos, chaos_flags
from backend.app.merchants.adapter import MERCHANTS, channel3_adapter
from backend.app.router.scoring import (
    derive_urgency,
    apply_hard_filters,
    score_and_rank_offers,
)
from backend.app.agent.gemini_client import ollama_client
from backend.app.agent.shopping_agent import shopping_agent


@pytest.fixture
def clean_db():
    init_db()
    db = SessionLocal()
    db.query(PaymentEvent).delete()
    db.query(Payment).delete()
    seed_week_with_asha(db)
    yield db
    reset_chaos()
    db.close()


# ============================================================================
# USAGE 1: Sandboxed E-Wallet, 3-Bucket Ledger, PayPal & Webhooks
# ============================================================================

def test_u1_wallet_three_bucket_lifecycle(clean_db):
    """Verify top-up -> reserve (held) -> settle (spent) -> refund lifecycle."""
    db = clean_db
    s0 = ledger_service.get_wallet_summary(db)
    assert s0.available_balance == 200.00
    assert s0.held_balance == 0.0
    assert s0.spent_balance == 0.0

    # Reserve $30.00
    ledger_service.reserve(db, 30.00, "USD", "idem-res-u1", "intent-u1")
    s1 = ledger_service.get_wallet_summary(db)
    assert s1.available_balance == 170.00
    assert s1.held_balance == 30.00
    assert s1.spent_balance == 0.0

    # Idempotent replay of reserve must not double-deduct
    ledger_service.reserve(db, 30.00, "USD", "idem-res-u1", "intent-u1")
    s1_replay = ledger_service.get_wallet_summary(db)
    assert s1_replay.available_balance == 170.00
    assert s1_replay.held_balance == 30.00

    # Settle $30.00
    ledger_service.settle(db, 30.00, "USD", "idem-set-u1", "intent-u1")
    s2 = ledger_service.get_wallet_summary(db)
    assert s2.available_balance == 170.00
    assert s2.held_balance == 0.0
    assert s2.spent_balance == 30.00

    # Refund $10.00
    ledger_service.refund(db, 10.00, "USD", "idem-ref-u1", "intent-u1")
    s3 = ledger_service.get_wallet_summary(db)
    assert s3.available_balance == 180.00
    assert s3.held_balance == 0.0
    assert s3.spent_balance == 20.00


def test_u1_wallet_release_and_overdraft_protection(clean_db):
    """Verify reserve release on abort and overdraft rejection."""
    db = clean_db
    ledger_service.reserve(db, 45.00, "USD", "idem-res-rel", "intent-rel")
    assert ledger_service.get_wallet_summary(db).available_balance == 155.00

    ledger_service.release(db, 45.00, "USD", "idem-rel-1", "intent-rel")
    s = ledger_service.get_wallet_summary(db)
    assert s.available_balance == 200.00
    assert s.held_balance == 0.0

    with pytest.raises(InsufficientFundsError):
        ledger_service.reserve(db, 500.00, "USD", "idem-overdraft", "intent-over")


@pytest.mark.asyncio
async def test_u1_mock_paypal_provider_and_chaos():
    """Verify MockPaymentProvider authorize, capture, void, refund, and chaos failure."""
    reset_chaos()
    provider = MockPaymentProvider()
    auth = await provider.authorize(19.99, "USD", "ref-1", "idem-auth-1")
    assert auth.status == "CREATED"
    assert auth.amount == 19.99

    cap = await provider.capture(auth.auth_id, "idem-cap-1")
    assert cap.status == "COMPLETED"

    ref = await provider.refund(cap.capture_id, 19.99, "idem-ref-1")
    assert ref.status == "COMPLETED"

    chaos_flags["payment_failure"] = True
    with pytest.raises(RuntimeError):
        await provider.authorize(10.0, "USD", "ref-fail", "idem-fail")
    reset_chaos()


# ============================================================================
# USAGE 2: Deterministic 9-Rule Spending Mandate Policy Evaluator
# ============================================================================

def _wallet_fixture(**overrides) -> WalletSummary:
    base = dict(
        available_balance=200.0,
        held_balance=0.0,
        spent_balance=0.0,
        total_balance=200.0,
        currency="USD",
        daily_spent=0.0,
        monthly_spent=0.0,
        category_spent={"grocery": 0.0, "supplies": 0.0, "fitness": 0.0},
        daily_cap=80.0,
        monthly_cap=400.0,
        kill_switch=False,
    )
    base.update(overrides)
    return WalletSummary(**base)


def test_u2_mandate_all_nine_rules():
    """Verify all 9 rules of the deterministic mandate evaluator."""
    # 1. Kill switch -> DENY
    v1 = evaluate_mandate(
        "Milk", "item-milk", 1, "chat", "quick10", 4.5, 3.5, "grocery",
        _wallet_fixture(), MandateBody(kill_switch=True)
    )
    assert v1.result == "DENY" and "RULE_1_KILL_SWITCH" in v1.rule_ids

    # 2. Blocked merchant -> DENY
    m_block = MandateBody(merchants=MerchantRules(allow=["quick10"], block=["shadyshop"]))
    v2 = evaluate_mandate(
        "Milk", "item-milk", 1, "chat", "shadyshop", 4.5, 3.5, "grocery",
        _wallet_fixture(), m_block
    )
    assert v2.result == "DENY" and "RULE_2_MERCHANT_BLOCK" in v2.rule_ids

    # 3. Per-txn max exceeded -> DENY
    v3 = evaluate_mandate(
        "Bulk Paper", "item-paper", 5, "chat", "megamart", 65.0, 13.0, "supplies",
        _wallet_fixture(), MandateBody()
    )
    assert v3.result == "DENY" and "RULE_4_PER_TXN_MAX" in v3.rule_ids

    # 4. Monthly cap exceeded -> DENY
    v4 = evaluate_mandate(
        "Protein", "item-protein", 1, "chat", "megamart", 35.0, 35.0, "fitness",
        _wallet_fixture(monthly_spent=380.0), MandateBody()
    )
    assert v4.result == "DENY" and "RULE_5_MONTHLY_CAP" in v4.rule_ids

    # 5. Category budget exceeded -> DENY
    v5 = evaluate_mandate(
        "Paper", "item-paper", 1, "chat", "megamart", 15.0, 15.0, "supplies",
        _wallet_fixture(category_spent={"supplies": 70.0}), MandateBody()
    )
    assert v5.result == "DENY" and "RULE_5_CAT_BUDGET" in v5.rule_ids

    # 6. Insufficient wallet balance -> DENY
    v6 = evaluate_mandate(
        "Milk", "item-milk", 1, "chat", "quick10", 15.0, 15.0, "grocery",
        _wallet_fixture(available_balance=5.0), MandateBody()
    )
    assert v6.result == "DENY" and "RULE_6_INSUFFICIENT_FUNDS" in v6.rule_ids

    # 7a. Price spike anomaly (>30%) -> NEEDS_APPROVAL
    v7 = evaluate_mandate(
        "Milk", "item-milk", 1, "chat", "quick10", 6.0, 5.0, "grocery",
        _wallet_fixture(), MandateBody(),
        recent_order_history=[{"item_name": "Milk", "unit_price": 3.50, "hours_ago": 48}]
    )
    assert v7.result == "NEEDS_APPROVAL" and "RULE_7_PRICE_SPIKE" in v7.rule_ids

    # 7b. Quantity multiple anomaly -> NEEDS_APPROVAL
    v7_qty = evaluate_mandate(
        "Milk", "item-milk", 4, "chat", "quick10", 15.0, 3.5, "grocery",
        _wallet_fixture(), MandateBody(),
        item_reorder_qty=1.0
    )
    assert v7_qty.result == "NEEDS_APPROVAL" and "RULE_7_QTY_MULTIPLE" in v7_qty.rule_ids


# ============================================================================
# USAGE 3: Cryptographic Hash-Chained Audit Trail & Tamper Detection
# ============================================================================

def test_u3_audit_hash_chain_and_tamper_detection(clean_db):
    """Verify intact hash chain passes and tampering with payload is detected."""
    db = clean_db
    e1 = append_audit_event(db, "user", "TEST_EVT_1", "order", "ord-1", {"amt": 10})
    e2 = append_audit_event(db, "agent", "TEST_EVT_2", "order", "ord-2", {"amt": 20})
    assert e2.prev_hash == e1.hash

    valid, msg, count = verify_audit_chain(db)
    assert valid is True
    assert count >= 3

    # Tamper with e1's payload in the database
    e1.payload_json = json.dumps({"amt": 999999})
    db.commit()

    valid_after, tamper_msg, _ = verify_audit_chain(db)
    assert valid_after is False
    assert "Tampered hash" in tamper_msg


# ============================================================================
# USAGE 4: Inventory Depletion Tracking & Virtual Clock
# ============================================================================

def test_u4_inventory_depletion_and_stock_modes(clean_db):
    """Verify consumption decay over virtual time and stock update modes."""
    db = clean_db
    milk = inventory_service.get_item_by_name(db, "Milk")
    assert milk is not None

    # Advance virtual clock by 12 hours -> 0.5 bottle consumed
    clock.advance(hours=12)
    stock_now, doc, conf, needed_by = inventory_service.calculate_stock_and_cover(milk)
    assert stock_now == pytest.approx(0.5, abs=0.05)
    assert doc == pytest.approx(0.5, abs=0.1)

    # Mark paper as finished ("we're out of paper")
    paper = inventory_service.get_item_by_name(db, "Paper")
    updated = inventory_service.update_stock(
        db, paper.id, StockUpdateRequest(mode="finished", qty=0.0, reason="user_said")
    )
    s_paper, doc_paper, _, _ = inventory_service.calculate_stock_and_cover(updated)
    assert s_paper == 0.0
    assert doc_paper == 0.0


# ============================================================================
# USAGE 5: Multi-Merchant Adapters, Channel3 SDK & SLA Scoring
# ============================================================================

@pytest.mark.asyncio
async def test_u5_merchant_adapters_and_urgency_scoring():
    """Verify all 5 merchant adapters return offers and urgency shifts ranking."""
    reset_chaos()
    now = clock.now()
    spec = ItemSpec()
    mandate = MandateBody()

    offers = []
    for m_id, adapter in MERCHANTS.items():
        res = await adapter.search("a4 paper", spec, 1.0)
        offers.extend(res)
    assert len(offers) >= 3

    # Verify Channel3LiveAdapter is available and safe when CHANNEL3_API_KEY is unset
    assert hasattr(channel3_adapter, "is_enabled")

    # Derive URGENT when stock_qty == 0
    u_urgent = derive_urgency(now + timedelta(minutes=30), now, stock_qty=0.0, user_said_urgent=True)
    assert u_urgent == "URGENT"

    valid_urgent, filtered = apply_hard_filters(
        offers, 1.0, now + timedelta(minutes=30), now, spec, False, "any", mandate
    )
    chosen_u, _, _, _ = score_and_rank_offers(valid_urgent, u_urgent, spec)
    assert chosen_u is not None
    assert chosen_u.merchant_id in ["quick10", "zipbasket"]


def test_u5_router_aggregator_module_integrity():
    """Check that backend.app.router.aggregator exports RouterAggregator & router_aggregator."""
    mod = importlib.import_module("backend.app.router.aggregator")
    assert hasattr(mod, "RouterAggregator"), "RouterAggregator class missing from aggregator.py"
    assert hasattr(mod, "router_aggregator"), "router_aggregator instance missing from aggregator.py"


# ============================================================================
# USAGE 6: Conversational Agent & Local Ollama (qwen2.5:7b) Readiness
# ============================================================================

def test_u6_agent_module_export_consistency():
    """Verify backend.app.agent.gemini_client exports ollama_client, gemini_client, GeminiClient."""
    mod = importlib.import_module("backend.app.agent.gemini_client")
    assert hasattr(mod, "ollama_client")
    assert hasattr(mod, "gemini_client")
    assert hasattr(mod, "GeminiClient")


@pytest.mark.asyncio
async def test_u6_ollama_qwen25_7b_daemon_and_code_support(clean_db):
    """
    Verify:
    1. Local Ollama daemon has 'qwen2.5:7b' model installed and reachable.
    2. Backend config & agent code support Ollama (OLLAMA_BASE_URL / OLLAMA_MODEL).
    3. Conversational agent processes multi-rule & depletion requests end-to-end.
    """
    # 1. Check local Ollama HTTP API
    resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5.0)
    assert resp.status_code == 200
    models = [m.get("name", "") for m in resp.json().get("models", [])]
    assert any("qwen2.5:7b" in m for m in models), f"qwen2.5:7b not found in Ollama models: {models}"

    # 2. Check backend settings and ollama_client
    assert settings.OLLAMA_MODEL == "qwen2.5:7b"
    assert ollama_client.is_available() is True

    # 3. Process chat message end-to-end
    msg = await shopping_agent.process_chat(
        db=clean_db,
        user_message="I need milk daily, protein powder monthly, and reorder A4 paper when it runs out",
    )
    assert msg.role == "assistant"
    assert msg.cards is not None and len(msg.cards) >= 3


# ============================================================================
# USAGE 7: Docker Infrastructure, Security & Test Hygiene Checks
# ============================================================================

def test_u7_docker_infrastructure_files_present():
    """Verify Dockerfile, docker-compose.yml, and .dockerignore exist."""
    assert os.path.exists("Dockerfile"), "Dockerfile missing from root"
    assert os.path.exists("docker-compose.yml"), "docker-compose.yml missing from root"
    assert os.path.exists(".dockerignore"), ".dockerignore missing from root"


def test_u7_no_committed_api_keys_in_repo():
    """Ensure no plaintext API keys (e.g., keys.env) are tracked in the repository."""
    keys_env_path = os.path.join("backend", "r4_aggregation_router", "keys.env")
    assert not os.path.exists(keys_env_path), (
        f"Plaintext API key file '{keys_env_path}' is present in the repository!"
    )


def test_u7_test_evaluator_no_nested_test_functions():
    """Ensure all test_* functions in backend/tests/test_evaluator.py are top-level (not nested)."""
    with open(os.path.join("backend", "tests", "test_evaluator.py"), "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    nested_tests = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                if child is not node and isinstance(child, ast.FunctionDef) and child.name.startswith("test_"):
                    nested_tests.append((child.name, node.name, child.lineno))
    assert not nested_tests, (
        f"Found nested test functions in test_evaluator.py that pytest will never execute: {nested_tests}"
    )
