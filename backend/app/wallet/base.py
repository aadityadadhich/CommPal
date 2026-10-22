from typing import Protocol, Optional, Dict, Any, runtime_checkable
from pydantic import BaseModel

class Authorization(BaseModel):
    auth_id: str
    status: str  # CREATED, VOIDED, COMPLETED
    amount: float
    currency: str = "USD"
    created_at: str

class Capture(BaseModel):
    capture_id: str
    auth_id: str
    status: str  # COMPLETED, FAILED
    amount: float
    currency: str = "USD"
    created_at: str

class Refund(BaseModel):
    refund_id: str
    capture_id: str
    status: str  # COMPLETED
    amount: float
    currency: str = "USD"
    created_at: str

@runtime_checkable
class PaymentProvider(Protocol):
    async def authorize(self, amount: float, currency: str, ref: str, idem_key: str) -> Authorization:
        ...

    async def capture(self, auth_id: str, idem_key: str) -> Capture:
        ...

    async def void(self, auth_id: str, idem_key: str) -> None:
        ...

    async def refund(self, capture_id: str, amount: float, idem_key: str) -> Refund:
        ...

    async def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        ...
