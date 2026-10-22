import httpx
import base64
import json
from typing import Dict, Any, Optional
from backend.app.config import settings
from backend.app.wallet.base import Authorization, Capture, Refund, PaymentProvider
from backend.app.wallet.mock_provider import mock_payment_provider
from backend.app.scheduler.virtual_clock import clock

class PayPalSandboxProvider:
    def __init__(self):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.api_base = settings.PAYPAL_API_BASE.rstrip("/")
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _get_access_token(self) -> str:
        if not self.is_configured():
            raise RuntimeError("PayPal credentials not configured in environment.")

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
            data = resp.json()
            self._access_token = data["access_token"]
            return self._access_token

    async def authorize(self, amount: float, currency: str, ref: str, idem_key: str) -> Authorization:
        if not self.is_configured() or settings.PAYPAL_MODE == "mock":
            return await mock_payment_provider.authorize(amount, currency, ref, idem_key)

        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idem_key
        }
        
        # Create an Order with intent = AUTHORIZE
        payload = {
            "intent": "AUTHORIZE",
            "purchase_units": [{
                "reference_id": ref,
                "amount": {
                    "currency_code": currency,
                    "value": f"{amount:.2f}"
                },
                "description": f"CommPal Autonomous restock: {ref}"
            }]
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{self.api_base}/v2/checkout/orders", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            order_id = data["id"]

            # Authorize order payment
            auth_resp = await client.post(
                f"{self.api_base}/v2/checkout/orders/{order_id}/authorize",
                headers=headers
            )
            auth_resp.raise_for_status()
            auth_data = auth_resp.json()
            
            # Extract authorization id from purchase_units
            pu = auth_data["purchase_units"][0]
            payments = pu["payments"]
            auth_obj = payments["authorizations"][0]
            auth_id = auth_obj["id"]

            return Authorization(
                auth_id=auth_id,
                status=auth_obj["status"],
                amount=amount,
                currency=currency,
                created_at=clock.now().isoformat()
            )

    async def capture(self, auth_id: str, idem_key: str) -> Capture:
        if not self.is_configured() or settings.PAYPAL_MODE == "mock":
            return await mock_payment_provider.capture(auth_id, idem_key)

        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idem_key
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.api_base}/v2/payments/authorizations/{auth_id}/capture",
                headers=headers,
                json={}
            )
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
        if not self.is_configured() or settings.PAYPAL_MODE == "mock":
            return await mock_payment_provider.void(auth_id, idem_key)

        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{self.api_base}/v2/payments/authorizations/{auth_id}/void", headers=headers)
            resp.raise_for_status()

    async def refund(self, capture_id: str, amount: float, idem_key: str) -> Refund:
        if not self.is_configured() or settings.PAYPAL_MODE == "mock":
            return await mock_payment_provider.refund(capture_id, amount, idem_key)

        token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": idem_key
        }
        payload = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency_code": "USD"
            }
        }
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

    async def verify_webhook(self, headers: Dict[str, str], body: bytes) -> bool:
        if not self.is_configured() or settings.PAYPAL_MODE == "mock":
            return await mock_payment_provider.verify_webhook(headers, body)
        return True

paypal_provider = PayPalSandboxProvider()

def get_active_payment_provider() -> PaymentProvider:
    if settings.PAYPAL_MODE == "sandbox" and paypal_provider.is_configured():
        return paypal_provider
    return mock_payment_provider
