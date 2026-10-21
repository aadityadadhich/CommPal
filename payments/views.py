import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Payment
from payments.serializers import PaymentCreateSerializer, PaymentSerializer, ProviderWebhookSerializer
from payments.services import (
    IdempotencyConflict,
    InvalidPaymentEvent,
    PaymentProviderError,
    cancel_payment,
    create_payment,
    process_provider_event,
    verify_webhook_signature,
)


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The requested payment state conflicts with its current state."
    default_code = "payment_conflict"


class PaymentListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        payments = Payment.objects.filter(user=request.user)
        return Response(PaymentSerializer(payments, many=True).data)

    def post(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key and len(idempotency_key) > 255:
            return Response(
                {"detail": "Idempotency-Key must be at most 255 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payment, created = create_payment(
                user=request.user,
                idempotency_key=idempotency_key,
                **serializer.validated_data,
            )
        except IdempotencyConflict:
            raise Conflict("Idempotency-Key was already used with different payment details.")
        except PaymentProviderError:
            return Response(
                {"detail": "The payment provider could not start checkout."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PaymentDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
        return Response(PaymentSerializer(payment).data)


class PaymentCancelView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, payment_id):
        payment = get_object_or_404(Payment, pk=payment_id, user=request.user)
        try:
            payment = cancel_payment(payment)
        except InvalidPaymentEvent as exc:
            raise Conflict(str(exc))
        return Response(PaymentSerializer(payment).data)


class ProviderWebhookView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        signature = request.headers.get("X-Payment-Signature", "")
        if not verify_webhook_signature(request.body, signature):
            return Response({"detail": "Invalid webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response({"detail": "Invalid JSON payload."}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(payload, dict):
            return Response({"detail": "Webhook payload must be a JSON object."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = ProviderWebhookSerializer(data=payload)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        provider_name = getattr(settings, "PAYMENTS_WEBHOOK_PROVIDER", "local")
        try:
            created = process_provider_event(
                provider_name=provider_name,
                payload=serializer.validated_data,
            )
        except InvalidPaymentEvent as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"received": True, "duplicate": not created})
