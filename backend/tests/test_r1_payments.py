import pytest
from decimal import Decimal
from backend.app.db.database import SessionLocal, init_db
from backend.r1_payments_wallet.models import Payment, PaymentEvent
from backend.r1_payments_wallet.services import (
    create_payment, cancel_payment, process_provider_event, 
    verify_webhook_signature, IdempotencyConflict, InvalidPaymentEvent
)
from backend.app.config import settings

@pytest.fixture(autouse=True)
def db_session():
    init_db()
    db = SessionLocal()
    db.query(PaymentEvent).delete()
    db.query(Payment).delete()
    db.commit()
    yield db
    db.close()

def test_milind_create_payment_and_idempotency(db_session):
    # 1. Create payment
    pay, created = create_payment(
        db=db_session,
        amount=25.50,
        currency="USD",
        user_id="user_123",
        description="Weekly grocery",
        idempotency_key="idem-key-milind-001"
    )
    assert created is True
    assert pay.status == "pending"
    assert pay.amount == 25.50

    # 2. Idempotency replay with exact same data
    pay_replayed, created_replayed = create_payment(
        db=db_session,
        amount=25.50,
        currency="USD",
        user_id="user_123",
        description="Weekly grocery",
        idempotency_key="idem-key-milind-001"
    )
    assert created_replayed is False
    assert pay_replayed.id == pay.id

    # 3. Idempotency conflict with mismatched amount
    with pytest.raises(IdempotencyConflict):
        create_payment(
            db=db_session,
            amount=99.99,  # Mismatched amount
            currency="USD",
            user_id="user_123",
            description="Weekly grocery",
            idempotency_key="idem-key-milind-001"
        )

def test_milind_cancel_payment(db_session):
    pay, _ = create_payment(
        db=db_session,
        amount=15.00,
        currency="USD",
        idempotency_key="idem-cancel-001"
    )
    canceled = cancel_payment(db_session, pay.id)
    assert canceled.status == "canceled"

def test_milind_webhook_signature_and_deduplication(db_session):
    raw_body = b'{"id":"evt-123","type":"payment.succeeded","amount":15.0}'
    import hmac, hashlib
    secret = settings.SECRET_KEY
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    # Valid signature check
    assert verify_webhook_signature(raw_body, f"sha256={sig}") is True
    # Invalid signature check
    assert verify_webhook_signature(raw_body, "sha256=invalidhex") is False

    # Create payment to receive webhook
    pay, _ = create_payment(
        db=db_session,
        amount=50.00,
        currency="USD",
        idempotency_key="idem-webhook-001"
    )

    # Process webhook event once
    success = process_provider_event(
        db=db_session,
        provider_name="paypal_sandbox",
        payload={
            "id": "evt-paypal-unique-001",
            "type": "payment.succeeded",
            "payment_id": pay.id
        }
    )
    assert success is True

    # Check payment updated to succeeded
    db_session.refresh(pay)
    assert pay.status == "succeeded"

    # Deduplication test: re-sending the same event returns False
    duplicate = process_provider_event(
        db=db_session,
        provider_name="paypal_sandbox",
        payload={
            "id": "evt-paypal-unique-001",
            "type": "payment.succeeded",
            "payment_id": pay.id
        }
    )
    assert duplicate is False
