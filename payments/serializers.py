from rest_framework import serializers
from decimal import Decimal

from payments.models import Payment


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    currency = serializers.RegexField(regex=r"^[A-Z]{3}$", max_length=3)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "id",
            "amount",
            "currency",
            "description",
            "status",
            "provider",
            "provider_reference",
            "checkout_url",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ProviderWebhookSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=255)
    type = serializers.ChoiceField(choices=("payment.succeeded", "payment.failed"))
    payment_id = serializers.UUIDField()
