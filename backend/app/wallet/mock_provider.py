import asyncio
import uuid
from typing import Dict, Any
from backend.app.wallet.base import Authorization, Capture, Refund
from backend.app.merchants.catalogs import chaos_flags
from backend.app.scheduler.virtual_clock import clock

class MockPaymentProvider:
    def __init__(self):
        self._authorizations: Dict[str, Authorization] = {}
        self._captures: Dict[str, Capture] = {}
        self._refunds: Dict[str, Refund] = {}

    async def authorize(self, amount: float, currency: str, ref: str, idem_key: str) -> Authorization:
        await asyncio.sleep(0.08)  # Realistic sandbox network latency
        
        if chaos_flags.get("payment_failure", False):
            raise RuntimeError("PayPal Sandbox simulated card/wallet authorization error: TRANSACTION_REFUSED.")

        auth_id = f"AUTH-{uuid.uuid4().hex[:12].upper()}"
        auth = Authorization(
            auth_id=auth_id,
            status="CREATED",
            amount=amount,
            currency=currency,
            created_at=clock.now().isoformat()
        )
        self._authorizations[auth_id] = auth
        return auth

    async def capture(self, auth_id: str, idem_key: str) -> Capture:
        await asyncio.sleep(0.08)
        
        if auth_id not in self._authorizations:
            raise KeyError(f"Authorization '{auth_id}' not found.")
            
        auth = self._authorizations[auth_id]
        if auth.status == "VOIDED":
            raise RuntimeError(f"Cannot capture voided authorization '{auth_id}'.")
            
        auth.status = "COMPLETED"
        capture_id = f"CAPT-{uuid.uuid4().hex[:12].upper()}"
        cap = Capture(
            capture_id=capture_id,
            auth_id=auth_id,
            status="COMPLETED",
            amount=auth.amount,
            currency=auth.currency,
            created_at=clock.now().isoformat()
        )
        self._captures[capture_id] = cap
        return cap

    async def void(self, auth_id: str, idem_key: str) -> None:
        await asyncio.sleep(0.05)
        if auth_id in self._authorizations:
            self._authorizations[auth_id].status = "VOIDED"

    async def refund(self, capture_id: str, amount: float, idem_key: str) -> Refund:
        await asyncio.sleep(0.08)
        if capture_id not in self._captures:
            raise KeyError(f"Capture '{capture_id}' not found.")
            
        ref_id = f"REF-{uuid.uuid4().hex[:12].upper()}"
        refund = Refund(
            refund_id=ref_id,
            capture_id=capture_id,
            status="COMPLETED",
            amount=amount,
            currency=self._captures[capture_id].currency,
            created_at=clock.now().isoformat()
        )
        self._refunds[ref_id] = refund
        return refund

    async def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        # Mock webhooks always verify
        return True

mock_payment_provider = MockPaymentProvider()
