import uuid
import hmac
import hashlib
import json
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from backend.r1_payments_wallet.models import Payment, PaymentEvent
from backend.app.config import settings
from backend.app.scheduler.virtual_clock import clock

class IdempotencyConflict(Exception):
    """Reused idempotency key for different payment details (Milind's design)."""

class PaymentProviderError(Exception):
    """Payment provider checkout failure (Milind's design)."""

class InvalidPaymentEvent(Exception):
    """Invalid or unverified payment event (Milind's design)."""

def create_payment(
    db: Session,
    amount: float,
    currency: str,
    user_id: str = "default_user",
    description: str = "",
    idempotency_key: Optional[str] = None,
    provider: str = "paypal_sandbox"
) -> Tuple[Payment, bool]:
    """
    Persist a payment with idempotency protection.
    Returns (payment, created). A reused idempotency key returns the existing payment
    only when the submitted payment details match exactly.
    """
    now_str = clock.now().isoformat()
    existing = None
    if idempotency_key:
        existing = db.query(Payment).filter(
            Payment.user_id == user_id,
            Payment.idempotency_key == idempotency_key
        ).first()

    if existing:
        if (round(existing.amount, 2), existing.currency, existing.description) != (
            round(amount, 2),
            currency,
            description
        ):
            raise IdempotencyConflict("Idempotency key reused with mismatched payment data.")
        return existing, False

    payment = Payment(
        id=str(uuid.uuid4()),
        user_id=user_id,
        amount=round(amount, 2),
        currency=currency,
        description=description,
        status="pending",
        provider=provider,
        idempotency_key=idempotency_key,
        created_at=now_str,
        updated_at=now_str
    )

    try:
        db.add(payment)
        db.commit()
        db.refresh(payment)
    except IntegrityError:
        db.rollback()
        if not idempotency_key:
            raise
        existing = db.query(Payment).filter(
            Payment.user_id == user_id,
            Payment.idempotency_key == idempotency_key
        ).first()
        if not existing:
            raise
        if (round(existing.amount, 2), existing.currency, existing.description) != (
            round(amount, 2),
            currency,
            description
        ):
            raise IdempotencyConflict("Idempotency key reused with mismatched payment data.")
        return existing, False

    return payment, True

def cancel_payment(db: Session, payment_id: str) -> Payment:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise KeyError(f"Payment '{payment_id}' not found.")
    if payment.status != "pending":
        raise InvalidPaymentEvent("Only pending payments can be canceled.")

    payment.status = "canceled"
    payment.updated_at = clock.now().isoformat()
    db.commit()
    db.refresh(payment)
    return payment

def process_provider_event(
    db: Session,
    provider_name: str,
    payload: Dict[str, Any]
) -> bool:
    """
    Apply a normalized, signature-verified webhook exactly once with deduplication.
    Incorporated from Milind's services.py.
    """
    event_id = payload.get("id") or payload.get("event_id")
    event_type = payload.get("type") or payload.get("event_type")
    payment_id = payload.get("payment_id")

    status_by_event = {
        "payment.succeeded": "succeeded",
        "payment.failed": "failed",
        "PAYMENT.CAPTURE.COMPLETED": "succeeded",
        "PAYMENT.CAPTURE.DENIED": "failed",
    }

    if not isinstance(event_id, str) or not event_id:
        raise InvalidPaymentEvent("A valid event id is required.")
    if event_type not in status_by_event:
        raise InvalidPaymentEvent(f"Unsupported payment event type: {event_type}")

    # Deduplication check
    existing_event = db.query(PaymentEvent).filter(
        PaymentEvent.provider == provider_name,
        PaymentEvent.event_id == event_id
    ).first()

    if existing_event:
        return False  # Already processed idempotently

    payment = None
    if payment_id:
        payment = db.query(Payment).filter(Payment.id == str(payment_id)).first()

    event = PaymentEvent(
        id=str(uuid.uuid4()),
        payment_id=payment.id if payment else None,
        provider=provider_name,
        event_id=event_id,
        event_type=event_type,
        payload_json=json.dumps(payload),
        received_at=clock.now().isoformat()
    )
    db.add(event)

    if payment and payment.status == "pending":
        payment.status = status_by_event[event_type]
        payment.updated_at = clock.now().isoformat()

    db.commit()
    return True

def verify_webhook_signature(raw_body: bytes, signature: str, secret: Optional[str] = None) -> bool:
    """HMAC SHA-256 signature verification incorporated from Milind's services.py."""
    if not secret:
        secret = settings.SECRET_KEY
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)
