from typing import Protocol, runtime_checkable, Dict, Any, Optional
from pydantic import BaseModel
import asyncio
import uuid
import httpx
import base64

from backend.app.config import settings
from backend.app.merchants.catalogs import chaos_flags
from backend.app.scheduler.virtual_clock import clock

class CheckoutSession(BaseModel):
    provider_reference: str
    checkout_url: str = ""

class Authorization(BaseModel):
    auth_id: str
    status: str
    amount: float
    currency: str = "USD"
    created_at: str

class Capture(BaseModel):
    capture_id: str
    auth_id: str
    status: str
    amount: float
    currency: str = "USD"
    created_at: str

class Refund(BaseModel):
    refund_id: str
    capture_id: str
    status: str
    amount: float
    currency: str = "USD"
    created_at: str

AuthResult = Authorization
CaptureResult = Capture
RefundResult = Refund
VoidResult = Authorization

@runtime_checkable
class PaymentProvider(Protocol):
    name: str

    async def authorize(self, amount: float, currency: str, ref: str, idem_key: str) -> Authorization:
        ...

    async def capture(self, auth_id: str, idem_key: str) -> Capture:
        ...

    async def void(self, auth_id: str, idem_key: str) -> None:
        ...

    async def refund(self, capture_id: str, amount: float, idem_key: str) -> Refund:
        ...

class MockPaymentProvider:
    name: str = "mock_paypal"

    def __init__(self):
        self._authorizations: Dict[str, Authorization] = {}
        self._captures: Dict[str, Capture] = {}

    async def authorize(self, amount: float, currency: str, ref: str, idem_key: str) -> Authorization:
        await asyncio.sleep(0.05)
        if chaos_flags.get("payment_failure", False):
            raise RuntimeError("PayPal Sandbox mock card decline: TRANSACTION_REFUSED.")

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
        await asyncio.sleep(0.05)
        if auth_id not in self._authorizations:
            raise KeyError(f"Authorization '{auth_id}' not found.")
        auth = self._authorizations[auth_id]
        if auth.status == "VOIDED":
            raise RuntimeError(f"Cannot capture voided authorization '{auth_id}'.")
        auth.status = "COMPLETED"
        cap = Capture(
            capture_id=f"CAPT-{uuid.uuid4().hex[:12].upper()}",
            auth_id=auth_id,
            status="COMPLETED",
            amount=auth.amount,
            currency=auth.currency,
            created_at=clock.now().isoformat()
        )
        self._captures[cap.capture_id] = cap
        return cap

    async def void(self, auth_id: str, idem_key: str) -> None:
        await asyncio.sleep(0.02)
        if auth_id in self._authorizations:
            self._authorizations[auth_id].status = "VOIDED"

    async def refund(self, capture_id: str, amount: float, idem_key: str) -> Refund:
        await asyncio.sleep(0.05)
        return Refund(
            refund_id=f"REF-{uuid.uuid4().hex[:12].upper()}",
            capture_id=capture_id,
            status="COMPLETED",
            amount=amount,
            currency="USD",
            created_at=clock.now().isoformat()
        )

class PayPalSandboxProvider:
    name: str = "paypal_sandbox"

    def __init__(self):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.api_base = settings.PAYPAL_API_BASE.rstrip("/")
        self._access_token: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _get_access_token(self) -> str:
        if not self.is_configured():
            raise RuntimeError("PayPal credentials not set in environment.")
        auth_str = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.api_base}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {encoded_auth}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={"grant_type": "client_credentials"}
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
            return self._access_token

    async def authorize(self, amount: float, currency: str, ref: str, idem_key: str) -> Authorization:
        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idem_key
        }
        payload = {
            "intent": "AUTHORIZE",
            "purchase_units": [{
                "reference_id": ref,
                "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                "description": f"CommPal Autonomous Order: {ref}"
            }]
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{self.api_base}/v2/checkout/orders", headers=headers, json=payload)
            resp.raise_for_status()
            order_id = resp.json()["id"]

            auth_resp = await client.post(f"{self.api_base}/v2/checkout/orders/{order_id}/authorize", headers=headers)
            auth_resp.raise_for_status()
            auth_data = auth_resp.json()
            auth_obj = auth_data["purchase_units"][0]["payments"]["authorizations"][0]

            return Authorization(
                auth_id=auth_obj["id"],
                status=auth_obj["status"],
                amount=amount,
                currency=currency,
                created_at=clock.now().isoformat()
            )

    async def capture(self, auth_id: str, idem_key: str) -> Capture:
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "PayPal-Request-Id": idem_key}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{self.api_base}/v2/payments/authorizations/{auth_id}/capture", headers=headers, json={})
            resp.raise_for_status()
            data = resp.json()
            return Capture(
                capture_id=data["id"],
                auth_id=auth_id,
                status=data["status"],
                amount=float(data["amount"]["value"]),
                currency=data["amount"]["currency_code"],
                created_at=clock.now().isoformat()
            )

    async def void(self, auth_id: str, idem_key: str) -> None:
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{self.api_base}/v2/payments/authorizations/{auth_id}/void", headers=headers)
            resp.raise_for_status()

    async def refund(self, capture_id: str, amount: float, idem_key: str) -> Refund:
        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "PayPal-Request-Id": idem_key}
        payload = {"amount": {"value": f"{amount:.2f}", "currency_code": "USD"}}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{self.api_base}/v2/payments/captures/{capture_id}/refund", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return Refund(
                refund_id=data["id"],
                capture_id=capture_id,
                status=data["status"],
                amount=amount,
                currency="USD",
                created_at=clock.now().isoformat()
            )

mock_payment_provider = MockPaymentProvider()
paypal_provider = PayPalSandboxProvider()

def get_active_provider() -> PaymentProvider:
    if settings.PAYPAL_MODE == "sandbox" and paypal_provider.is_configured():
        return paypal_provider
    return mock_payment_provider

get_active_payment_provider = get_active_provider
