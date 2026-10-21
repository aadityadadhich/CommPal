import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    provider = models.CharField(max_length=64)
    provider_reference = models.CharField(max_length=255, blank=True)
    checkout_url = models.URLField(blank=True)
    idempotency_key = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_gt_zero"),
            models.UniqueConstraint(
                fields=("user", "idempotency_key"),
                condition=Q(idempotency_key__isnull=False),
                name="payment_user_idempotency_unique",
            ),
        ]
        indexes = [models.Index(fields=("user", "-created_at"), name="payment_user_created_idx")]

    def __str__(self) -> str:
        return f"{self.id} ({self.status})"


class PaymentEvent(models.Model):
    """A durable, deduplicated record of a verified provider webhook."""

    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        related_name="events",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=64)
    event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("received_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "event_id"),
                name="payment_event_provider_id_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id}"
