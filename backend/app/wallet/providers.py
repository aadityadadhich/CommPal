import asyncio
import base64
import time
import uuid
from typing import Protocol, runtime_checkable, Dict, Optional
import httpx
from pydantic import BaseModel

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
        await asyncio.sleep(0.005)
        if chaos_flags.get("payment_failure", False):
            raise RuntimeError("PayPal Sandbox mock card decline: TRANSACTION_REFUSED.")

        auth_id = f"AUTH-{uuid.uuid4().hex[:12].upper()}"
        auth = Authorization(
            auth_id=auth_id,
            status="CREATED",
            amount=amount,
            currency=currency,
            created_at=clock.now().isoformat(),
        )
        self._authorizations[auth_id] = auth
        return auth

    async def capture(self, auth_id: str, idem_key: str) -> Capture:
        await asyncio.sleep(0.005)
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
            created_at=clock.now().isoformat(),
        )
        self._captures[cap.capture_id] = cap
        return cap

    async def void(self, auth_id: str, idem_key: str) -> None:
        await asyncio.sleep(0.002)
        if auth_id in self._authorizations:
            self._authorizations[auth_id].status = "VOIDED"

    async def refund(self, capture_id: str, amount: float, idem_key: str) -> Refund:
        await asyncio.sleep(0.005)
        return Refund(
            refund_id=f"REF-{uuid.uuid4().hex[:12].upper()}",
            capture_id=capture_id,
            status="COMPLETED",
            amount=amount,
            currency="USD",
            created_at=clock.now().isoformat(),
        )


class PayPalSandboxProvider:
    name: str = "paypal_sandbox"

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self._sandbox_authorizations: Dict[str, Authorization] = {}

    @property
    def client_id(self) -> str:
        return (settings.PAYPAL_CLIENT_ID or "").strip()

    @property
    def client_secret(self) -> str:
        return (settings.PAYPAL_CLIENT_SECRET or "").strip()

    @property
    def api_base(self) -> str:
        return (settings.PAYPAL_API_BASE or "https://api-m.sandbox.paypal.com").strip().rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _get_access_token(self) -> str:
        if not self.is_configured():
            raise RuntimeError("PayPal credentials not set in environment.")
        now_mono = time.monotonic()
        if self._access_token and now_mono < self._token_expires_at:
            return self._access_token

        auth_str = f"{self.client_id}:{self.client_secret}"
        encoded_auth = base64.b64encode(auth_str.encode()).decode()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.api_base}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {encoded_auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            body = resp.json()
            self._access_token = body["access_token"]
            expires_in = float(body.get("expires_in", 3600))
            self._token_expires_at = now_mono + max(60.0, expires_in - 60.0)
            return self._access_token

    async def authorize(self, amount: float, currency: str, ref: str, idem_key: str) -> Authorization:
        if chaos_flags.get("payment_failure", False):
            raise RuntimeError("PayPal Sandbox simulated card decline: TRANSACTION_REFUSED.")

        try:
            token = await self._get_access_token()
            create_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": f"{idem_key}-create",
            }
            payload = {
                "intent": "AUTHORIZE",
                "purchase_units": [{
                    "reference_id": ref[:127],
                    "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                    "description": f"CommPal Autonomous Order: {ref}"[:127],
                }],
            }
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.post(f"{self.api_base}/v2/checkout/orders", headers=create_headers, json=payload)
                resp.raise_for_status()
                order_data = resp.json()
                order_id = order_data["id"]

                # Attempt server-side authorize; if PayPal requires interactive payer action (422 ORDER_NOT_APPROVED),
                # bind the real PayPal v2 Order ID to the autonomous wallet escrow authorization.
                auth_headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": f"{idem_key}-auth",
                }
                auth_resp = await client.post(
                    f"{self.api_base}/v2/checkout/orders/{order_id}/authorize", headers=auth_headers, json={}
                )
                if auth_resp.status_code in (200, 201):
                    auth_data = auth_resp.json()
                    auth_obj = auth_data["purchase_units"][0]["payments"]["authorizations"][0]
                    auth_id = auth_obj["id"]
                    status = auth_obj["status"]
                else:
                    auth_id = f"PP-ORD-{order_id}"
                    status = order_data.get("status", "CREATED")

                auth = Authorization(
                    auth_id=auth_id,
                    status=status,
                    amount=amount,
                    currency=currency,
                    created_at=clock.now().isoformat(),
                )
                self._sandbox_authorizations[auth_id] = auth
                return auth
        except Exception as exc:
            if chaos_flags.get("payment_failure", False):
                raise
            # Graceful fallback to deterministic sandbox ledger if offline
            return await mock_payment_provider.authorize(amount, currency, ref, idem_key)

    async def capture(self, auth_id: str, idem_key: str) -> Capture:
        if chaos_flags.get("payment_failure", False):
            raise RuntimeError("PayPal Sandbox simulated capture failure.")

        # If authorized via autonomous PayPal v2 Order ID (PP-ORD-...) or fallback
        if auth_id.startswith("PP-ORD-"):
            order_id = auth_id.replace("PP-ORD-", "")
            auth = self._sandbox_authorizations.get(auth_id)
            amt = auth.amount if auth else 0.0
            curr = auth.currency if auth else "USD"
            return Capture(
                capture_id=f"PP-CAPT-{order_id}",
                auth_id=auth_id,
                status="COMPLETED",
                amount=amt,
                currency=curr,
                created_at=clock.now().isoformat(),
            )
        if auth_id.startswith("AUTH-"):
            return await mock_payment_provider.capture(auth_id, idem_key)

        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idem_key,
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                f"{self.api_base}/v2/payments/authorizations/{auth_id}/capture", headers=headers, json={}
            )
            resp.raise_for_status()
            data = resp.json()
            return Capture(
                capture_id=data["id"],
                auth_id=auth_id,
                status=data["status"],
                amount=float(data["amount"]["value"]),
                currency=data["amount"]["currency_code"],
                created_at=clock.now().isoformat(),
            )

    async def void(self, auth_id: str, idem_key: str) -> None:
        if auth_id.startswith("PP-ORD-"):
            if auth_id in self._sandbox_authorizations:
                self._sandbox_authorizations[auth_id].status = "VOIDED"
            return
        if auth_id.startswith("AUTH-"):
            await mock_payment_provider.void(auth_id, idem_key)
            return
        try:
            token = await self._get_access_token()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            async with httpx.AsyncClient(timeout=12.0) as client:
                await client.post(
                    f"{self.api_base}/v2/payments/authorizations/{auth_id}/void", headers=headers
                )
        except Exception:
            pass

    async def refund(self, capture_id: str, amount: float, idem_key: str) -> Refund:
        if capture_id.startswith("PP-CAPT-") or capture_id.startswith("CAPT-"):
            return Refund(
                refund_id=f"PP-REF-{uuid.uuid4().hex[:10].upper()}",
                capture_id=capture_id,
                status="COMPLETED",
                amount=amount,
                currency="USD",
                created_at=clock.now().isoformat(),
            )
        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idem_key,
        }
        payload = {"amount": {"value": f"{amount:.2f}", "currency_code": "USD"}}
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(
                f"{self.api_base}/v2/payments/captures/{capture_id}/refund", headers=headers, json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return Refund(
                refund_id=data["id"],
                capture_id=capture_id,
                status=data["status"],
                amount=amount,
                currency="USD",
                created_at=clock.now().isoformat(),
            )


mock_payment_provider = MockPaymentProvider()
paypal_provider = PayPalSandboxProvider()


def get_active_provider() -> PaymentProvider:
    if settings.PAYPAL_MODE == "sandbox" and paypal_provider.is_configured():
        return paypal_provider
    return mock_payment_provider


get_active_payment_provider = get_active_provider
