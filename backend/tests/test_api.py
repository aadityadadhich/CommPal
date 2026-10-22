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
