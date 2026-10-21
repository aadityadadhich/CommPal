import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("currency", models.CharField(max_length=3)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("canceled", "Canceled")], db_index=True, default="pending", max_length=16)),
                ("provider", models.CharField(max_length=64)),
                ("provider_reference", models.CharField(blank=True, max_length=255)),
                ("checkout_url", models.URLField(blank=True)),
                ("idempotency_key", models.CharField(blank=True, max_length=255, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-created_at",),
                "indexes": [models.Index(fields=["user", "-created_at"], name="payment_user_created_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="payment_amount_gt_zero"),
                    models.UniqueConstraint(condition=models.Q(("idempotency_key__isnull", False)), fields=("user", "idempotency_key"), name="payment_user_idempotency_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(max_length=64)),
                ("event_id", models.CharField(max_length=255)),
                ("event_type", models.CharField(max_length=64)),
                ("payload", models.JSONField(default=dict)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("payment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="events", to="payments.payment")),
            ],
            options={
                "ordering": ("received_at",),
                "constraints": [models.UniqueConstraint(fields=("provider", "event_id"), name="payment_event_provider_id_unique")],
            },
        ),
    ]
