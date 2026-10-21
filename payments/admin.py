from django.contrib import admin

from payments.models import Payment, PaymentEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "currency", "status", "provider", "created_at")
    list_filter = ("status", "provider", "currency")
    search_fields = ("id", "provider_reference", "user__username")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "event_type", "payment", "received_at")
    list_filter = ("provider", "event_type")
    search_fields = ("event_id", "payment__id")
    readonly_fields = ("received_at",)
