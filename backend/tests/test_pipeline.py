import pytest
from backend.app.db.database import SessionLocal
from backend.app.db.seed import seed_week_with_asha, init_db
from backend.app.pipeline.orchestrator import purchase_pipeline
from backend.app.contracts.orders import OrderIntentCreate
from backend.app.contracts.items import StockUpdateRequest
from backend.app.inventory.service import inventory_service
from backend.app.wallet.ledger import ledger_service
from backend.app.audit.hash_chain import verify_audit_chain
from backend.app.merchants.catalogs import chaos_flags, reset_chaos

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    db = SessionLocal()
    seed_week_with_asha(db)
    db.close()
    yield
    reset_chaos()

@pytest.mark.asyncio
async def test_urgent_paper_purchase_e2e():
    db = SessionLocal()
    # 1. Deplete paper stock to 0
    paper = inventory_service.get_item_by_name(db, "paper")
    assert paper is not None
    inventory_service.update_stock(db, paper.id, StockUpdateRequest(mode="finished", qty=0.0, reason="user_said"))

    # 2. Request purchase for paper
    intent_req = OrderIntentCreate(
        item_id=paper.id,
        item_name=paper.name,
        qty=1.0,
        source="chat",
        urgency_hint="urgent"
    )
    result = await purchase_pipeline.request_purchase(db, intent_req, actor="test_user")

    assert result["success"] is True
    assert result["status"] == "ORDER_PLACED"
    assert "paypal_auth_id" in result
    assert "paypal_capture_id" in result
    assert result["merchant"] in ["Quick10", "ZipBasket"]

    # 3. Check wallet balances
    summary = ledger_service.get_wallet_summary(db)
    assert summary.spent_balance > 0.0
    assert summary.available_balance + summary.spent_balance == 200.00

    # 4. Check audit log integrity
    is_valid, msg, count = verify_audit_chain(db)
    assert is_valid is True
    assert count >= 3
    db.close()

@pytest.mark.asyncio
async def test_untracked_wd40_requires_approval():
    db = SessionLocal()
    intent_req = OrderIntentCreate(
        item_name="WD-40 Multi-Use",
        qty=1.0,
        source="chat"
    )
    result = await purchase_pipeline.request_purchase(db, intent_req, actor="test_user")

    assert result["success"] is True
    assert result["status"] == "PENDING_APPROVAL"
    assert "Order requires your approval" in result["message"]

    # Execute approval
    approval_result = await purchase_pipeline.execute_approved_order(db, result["intent_id"], actor="test_user")
    assert approval_result["success"] is True
    assert approval_result["status"] == "ORDER_PLACED"
    db.close()

@pytest.mark.asyncio
async def test_payment_failure_compensation():
    db = SessionLocal()
    chaos_flags["payment_failure"] = True
    
    intent_req = OrderIntentCreate(
        item_name="Whole Milk 1L",
        qty=1.0,
        source="chat"
    )
    result = await purchase_pipeline.request_purchase(db, intent_req, actor="test_user")

    assert result["success"] is False
    assert result["status"] == "PAYMENT_FAILED"

    # Funds must NOT be held or spent; full 200 available
    summary = ledger_service.get_wallet_summary(db)
    assert summary.available_balance == 200.00
    assert summary.held_balance == 0.0
    assert summary.spent_balance == 0.0
    db.close()
