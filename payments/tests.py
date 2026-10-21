import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from payments.models import Payment, PaymentEvent
from payments.providers.base import CheckoutSession
from payments.services import (
    IdempotencyConflict,
    InvalidPaymentEvent,
    create_payment,
    process_provider_event,
    verify_webhook_signature,
)


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="payer", password="test-password")

    def test_create_payment_persists_checkout_reference(self):
        payment, created = create_payment(
            user=self.user,
            amount=Decimal("12.50"),
            currency="USD",
            description="Example",
            idempotency_key="order-1",
        )
        self.assertTrue(created)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertTrue(payment.provider_reference.startswith("local_"))

    def test_idempotency_returns_same_record_and_rejects_changed_amount(self):
        first, _ = create_payment(
            user=self.user,
            amount=Decimal("12.50"),
            currency="USD",
            idempotency_key="order-2",
        )
        second, created = create_payment(
            user=self.user,
            amount=Decimal("12.50"),
            currency="USD",
            idempotency_key="order-2",
        )
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        with self.assertRaises(IdempotencyConflict):
            create_payment(
                user=self.user,
                amount=Decimal("13.50"),
                currency="USD",
                idempotency_key="order-2",
            )

    def test_provider_failure_marks_payment_failed(self):
        provider = type("FailingProvider", (), {"name": "failing", "create_checkout": lambda *_: (_ for _ in ()).throw(RuntimeError())})()
        with patch("payments.services.get_payment_provider", return_value=provider):
            with self.assertRaises(Exception):
                create_payment(user=self.user, amount=Decimal("3.00"), currency="USD")
        self.assertEqual(Payment.objects.get().status, Payment.Status.FAILED)

    def test_provider_webhook_is_applied_once(self):
        payment, _ = create_payment(
            user=self.user,
            amount=Decimal("5.00"),
            currency="USD",
            idempotency_key="order-3",
        )
        payload = {"id": "event-1", "type": "payment.succeeded", "payment_id": str(payment.pk)}
        self.assertTrue(process_provider_event(provider_name="local", payload=payload))
        self.assertFalse(process_provider_event(provider_name="local", payload=payload))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(PaymentEvent.objects.count(), 1)

    def test_webhook_cannot_reverse_final_payment(self):
        payment, _ = create_payment(user=self.user, amount=Decimal("5.00"), currency="USD")
        payment.status = Payment.Status.SUCCEEDED
        payment.save(update_fields=("status",))
        payload = {"id": "event-2", "type": "payment.failed", "payment_id": str(payment.pk)}
        with self.assertRaises(InvalidPaymentEvent):
            process_provider_event(provider_name="local", payload=payload)

    @override_settings(PAYMENTS_WEBHOOK_SECRET="test-secret")
    def test_signature_verification(self):
        body = b'{"event":"test"}'
        valid = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(body, f"sha256={valid}"))
        self.assertFalse(verify_webhook_signature(body, "invalid"))


class PaymentApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="api-payer", password="test-password")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_list_and_cancel_payment(self):
        response = self.client.post(
            "/api/payments/",
            {"amount": "25.00", "currency": "USD", "description": "Test"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="api-order-1",
        )
        self.assertEqual(response.status_code, 201)
        payment_id = response.data["id"]
        self.assertEqual(self.client.get("/api/payments/").status_code, 200)
        detail = self.client.get(f"/api/payments/{payment_id}/")
        self.assertEqual(detail.status_code, 200)
        canceled = self.client.post(f"/api/payments/{payment_id}/cancel/")
        self.assertEqual(canceled.status_code, 200)
        self.assertEqual(canceled.data["status"], Payment.Status.CANCELED)

    @override_settings(PAYMENTS_WEBHOOK_SECRET="test-secret", PAYMENTS_WEBHOOK_PROVIDER="local")
    def test_webhook_requires_valid_signature(self):
        body = json.dumps({"id": "evt", "type": "payment.succeeded", "payment_id": "00000000-0000-0000-0000-000000000001"}).encode()
        signature = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        response = self.client.post(
            "/api/payments/webhooks/",
            data=body,
            content_type="application/json",
            HTTP_X_PAYMENT_SIGNATURE=f"sha256={signature}",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/payments/webhooks/",
                data=body,
                content_type="application/json",
                HTTP_X_PAYMENT_SIGNATURE="bad",
            ).status_code,
            401,
        )
