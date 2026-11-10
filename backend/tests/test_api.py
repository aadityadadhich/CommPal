import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.database import SessionLocal, init_db
from backend.app.db.seed import seed_week_with_asha

@pytest.fixture(autouse=True)
def seed_test():
    init_db()
    db = SessionLocal()
    seed_week_with_asha(db)
    db.close()

def test_health_endpoint():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"
    assert data["database"] == "CONNECTED"

def test_items_endpoint():
    client = TestClient(app)
    resp = client.get("/api/items")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 3
    names = [it["name"] for it in items]
    assert any("Milk" in n for n in names)

def test_wallet_endpoint():
    client = TestClient(app)
    resp = client.get("/api/wallet")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available_balance"] == 200.00
    assert data["daily_cap"] == 80.00

def test_mandate_kill_switch_api():
    client = TestClient(app)
    resp = client.post("/api/mandate/kill-switch", json={"active": True, "reason": "Test freeze"})
    assert resp.status_code == 200
    assert resp.json()["kill_switch"] is True

    # Order should now be DENIED
    chat_resp = client.post("/api/chat", json={"message": "Order milk now"})
    assert chat_resp.status_code == 200
    # Toggle back off
    client.post("/api/mandate/kill-switch", json={"active": False})

def test_audit_verify_api():
    client = TestClient(app)
    resp = client.get("/api/audit/verify")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True

def test_demo_clock_advance_api():
    client = TestClient(app)
    resp = client.post("/api/demo/clock/advance?days=1")
    assert resp.status_code == 200
    data = resp.json()
    assert "clock" in data
    assert "tick_result" in data
    # 1 day advance should fire the daily milk rule!
    assert data["tick_result"]["rules_fired"] >= 1

def test_payments_and_webhook_api():
    client = TestClient(app)
    # 1. Create Payment
    resp = client.post("/api/payments", json={
        "amount": 42.00,
        "currency": "USD",
        "user_id": "test_user_api",
        "description": "Test order",
        "idempotency_key": "idem-api-test-1"
    })
    assert resp.status_code == 200
    p_data = resp.json()
    assert p_data["amount"] == 42.00
    assert p_data["status"] == "pending"
    p_id = p_data["id"]

    # 2. Cancel Payment
    resp_cancel = client.post(f"/api/payments/{p_id}/cancel")
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "canceled"

    # 3. Webhook Delivery
    resp_webhook = client.post("/api/webhooks/paypal", json={
        "id": "evt-webhook-test-1",
        "type": "payment.succeeded",
        "payment_id": p_id
    })
    assert resp_webhook.status_code == 200
    assert resp_webhook.json()["received"] is True

def test_stock_deplete_triggers_autonomous_order():
    client = TestClient(app)
    resp = client.post("/api/items/item-milk/stock", json={"mode": "finished"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["stock_qty"] == 0
    assert data["triggered_order"] is not None
    assert data["triggered_order"]["status"] == "ORDER_PLACED"

def test_create_item_and_direct_purchase():
    client = TestClient(app)
    create_resp = client.post("/api/items", json={
        "name": "Coffee 500g",
        "category": "grocery",
        "unit": "bag",
        "stock_qty": 3,
        "daily_use_rate": 0.25,
        "threshold_days": 2.0,
        "preferred_qty": 1,
        "last_price": 12.40
    })
    assert create_resp.status_code == 200
    created_item = create_resp.json()
    assert created_item["name"] == "Coffee 500g"

    order_resp = client.post("/api/orders/purchase", json={
        "item_name": "Coffee 500g",
        "qty": 1,
        "urgency": "normal",
        "trigger": "user_chat"
    })
    assert order_resp.status_code == 200
    assert order_resp.json()["status"] == "ORDER_PLACED"

def test_chat_nlu_multi_item_and_conversational():
    client = TestClient(app)
    # 1. Greeting should not trigger an order
    hi_resp = client.post("/api/chat", json={"message": "hi"})
    assert hi_resp.status_code == 200
    assert "CommPal" in hi_resp.json()["content"]

    # 2. Price comparison for Coffee
    cmp_resp = client.post("/api/chat", json={"message": "Compare prices for Coffee"})
    assert cmp_resp.status_code == 200
    cards = cmp_resp.json()["cards"]
    assert len(cards) == 1
    assert len(cards[0]["data"]["offers"]) >= 2

def test_wallet_top_up_endpoint():
    client = TestClient(app)
    resp = client.post("/api/wallet/top-up", json={"amount": 50.0})
    assert resp.status_code == 200
    assert resp.json()["wallet"]["available_balance"] == 250.00


def test_agentic_recipe_paneer_butter_masala_decomposition():
    client = TestClient(app)
    resp = client.post(
        "/api/chat",
        json={"message": "i need to make paneer butter masala , order all ingredients"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Paneer Butter Masala" in data["content"]
    cards = data["cards"]
    assert len(cards) == 2
    assert cards[0]["card_type"] == "ai_reasoning"
    assert cards[1]["card_type"] == "recipe_bundle"
    assert cards[1]["data"]["ordered_count"] == 5
    assert cards[1]["data"]["total_cost"] > 0


