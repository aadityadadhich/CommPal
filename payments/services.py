import uuid
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from payments.models import Payment, PaymentEvent
from payments.providers import get_payment_provider


class IdempotencyConflict(Exception):
    """The same idempotency key was reused for different payment data."""


class PaymentProviderError(Exception):
    """A configured provider could not create a checkout session."""


class InvalidPaymentEvent(Exception):
    """A verified webhook does not represent a valid payment state change."""


def create_payment(
    *,
    user,
    amount: Decimal,
    currency: str,
    description: str = "",
    idempotency_key: str | None = None,
) -> tuple[Payment, bool]:
    """Persist a payment then ask its adapter to create checkout.

    Returns (payment, created). A reused idempotency key returns the existing
    payment only when the submitted payment details match exactly.
    """
    existing = None
    if idempotency_key:
        existing = Payment.objects.filter(user=user, idempotency_key=idempotency_key).first()
    if existing:
        if (existing.amount, existing.currency, existing.description) != (
            amount,
            currency,
            description,
        ):
            raise IdempotencyConflict
        return existing, False

    provider = get_payment_provider()
    try:
        with transaction.atomic():
            payment = Payment.objects.create(
                user=user,
                amount=amount,
                currency=currency,
                description=description,
                provider=provider.name,
                idempotency_key=idempotency_key or None,
            )
    except IntegrityError:
        # Handles simultaneous requests that race on the database uniqueness constraint.
        if not idempotency_key:
            raise
        existing = Payment.objects.filter(user=user, idempotency_key=idempotency_key).first()
        if existing is None:
            raise
        if (existing.amount, existing.currency, existing.description) != (
            amount,
            currency,
            description,
        ):
            raise IdempotencyConflict
        return existing, False

    try:
        checkout = provider.create_checkout(payment)
    except Exception as exc:
        Payment.objects.filter(pk=payment.pk).update(
            status=Payment.Status.FAILED,
            updated_at=timezone.now(),
        )
        raise PaymentProviderError from exc

    payment.provider_reference = checkout.provider_reference
    payment.checkout_url = checkout.checkout_url
    payment.save(update_fields=("provider_reference", "checkout_url", "updated_at"))
    return payment, True


def cancel_payment(payment: Payment) -> Payment:
    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.status != Payment.Status.PENDING:
            raise InvalidPaymentEvent("Only pending payments can be canceled.")
        locked.status = Payment.Status.CANCELED
        locked.save(update_fields=("status", "updated_at"))
        return locked


def process_provider_event(*, provider_name: str, payload: dict[str, Any]) -> bool:
    """Apply a normalized, signature-verified webhook exactly once.

    Expected event types are payment.succeeded and payment.failed. Provider
    adapters may normalize their provider-specific payload before this call.
    """
    event_id = payload.get("id")
    event_type = payload.get("type")
    payment_id = payload.get("payment_id")
    status_by_event = {
        "payment.succeeded": Payment.Status.SUCCEEDED,
        "payment.failed": Payment.Status.FAILED,
    }
    if not isinstance(event_id, str) or not event_id or len(event_id) > 255:
        raise InvalidPaymentEvent("A valid event id is required.")
    if event_type not in status_by_event:
        raise InvalidPaymentEvent("Unsupported payment event type.")
    try:
        payment_uuid = uuid.UUID(str(payment_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidPaymentEvent("A valid payment_id is required.") from exc

    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(pk=payment_uuid).first()
        if payment is None or payment.provider != provider_name:
            raise InvalidPaymentEvent("Payment was not found for this provider.")
        if payment.status != Payment.Status.PENDING:
            if payment.status == status_by_event[event_type]:
                # A different event id can legitimately report the same final state.
                pass
            else:
                raise InvalidPaymentEvent("This payment is already in a final state.")

        _, created = PaymentEvent.objects.get_or_create(
            provider=provider_name,
            event_id=event_id,
            defaults={
                "payment": payment,
                "event_type": event_type,
                "payload": payload,
            },
        )
        if not created:
            return False

        desired_status = status_by_event[event_type]
        if payment.status == Payment.Status.PENDING:
            payment.status = desired_status
            payment.save(update_fields=("status", "updated_at"))
    return True


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    import hashlib
    import hmac

    secret = settings.PAYMENTS_WEBHOOK_SECRET.encode("utf-8")
    expected = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)
