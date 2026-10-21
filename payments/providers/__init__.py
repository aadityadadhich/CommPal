from django.conf import settings
from django.utils.module_loading import import_string


def get_payment_provider():
    """Build the configured adapter; integrations can be swapped via settings."""
    provider_class = import_string(settings.PAYMENTS_PROVIDER)
    return provider_class()
