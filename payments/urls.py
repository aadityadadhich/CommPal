from django.urls import path

from payments.views import (
    PaymentCancelView,
    PaymentDetailView,
    PaymentListCreateView,
    ProviderWebhookView,
)

app_name = "payments"

urlpatterns = [
    path("webhooks/", ProviderWebhookView.as_view(), name="webhook"),
    path("", PaymentListCreateView.as_view(), name="list-create"),
    path("<uuid:payment_id>/", PaymentDetailView.as_view(), name="detail"),
    path("<uuid:payment_id>/cancel/", PaymentCancelView.as_view(), name="cancel"),
]
