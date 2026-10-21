import uuid

from payments.models import Payment
from payments.providers.base import CheckoutSession


class LocalDevelopmentProvider:
    """Non-collecting provider adapter for local development and tests.

    It deliberately does not accept card details or simulate a successful charge.
    A real integration should implement the PaymentProvider protocol.
    """

    name = "local"

    def create_checkout(self, payment: Payment) -> CheckoutSession:
        return CheckoutSession(provider_reference=f"local_{uuid.uuid4().hex}")
