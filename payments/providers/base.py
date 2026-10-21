from dataclasses import dataclass
from typing import Protocol

from payments.models import Payment


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    provider_reference: str
    checkout_url: str = ""


class PaymentProvider(Protocol):
    name: str

    def create_checkout(self, payment: Payment) -> CheckoutSession:
        """Create a provider-side checkout session for a pending payment."""
