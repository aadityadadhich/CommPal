import asyncio
import logging
import uuid
from typing import List, Literal, Dict, Optional
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.contracts.items import ItemSpec
from backend.app.contracts.orders import Offer
from backend.app.merchants.catalogs import MOCK_CATALOGS, chaos_flags
from backend.app.scheduler.virtual_clock import clock

logger = logging.getLogger(__name__)


class MerchantOrder(BaseModel):
    merchant_id: str
    merchant_order_ref: str
    offer_id: str
    sku: str
    qty: float
    total_amount: float
    currency: str = "USD"
    status: Literal["CONFIRMED", "PACKED", "IN_TRANSIT", "DELIVERED", "FAILED"] = "CONFIRMED"
    eta_minutes: int
    tracking_url: str


class MockMerchant:
    def __init__(
        self,
        id: str,
        name: str,
        kind: Literal["quick", "marketplace", "wholesale", "local"],
        reliability: float = 0.95,
    ):
        self.id = id
        self.name = name
        self.kind = kind
        self.reliability = reliability
        self._orders: Dict[str, MerchantOrder] = {}

    async def search(self, query: str, spec: ItemSpec, qty: float) -> List[Offer]:
        if self.id in chaos_flags["down_merchants"]:
            raise RuntimeError(f"Merchant '{self.name}' service is unavailable (503 Service Unavailable).")

        if self.id in chaos_flags["slow_merchants"]:
            await asyncio.sleep(2.5)
        else:
            await asyncio.sleep(0.003)

        catalog = MOCK_CATALOGS.get(self.id, [])
        query_clean = query.strip().lower()
        results: List[Offer] = []

        query_tokens = [w for w in query_clean.replace("-", "").split() if len(w) > 1]
        core_words = {"milk", "paper", "protein", "powder", "wd40", "eggs", "coffee", "bread", "detergent", "batteries"}

        for item in catalog:
            item_name = item["item_name"].lower()
            title = item["title"].lower()

            is_match = (
                query_clean in item_name
                or item_name in query_clean
                or query_clean in title
                or any(qt in item_name or qt in title for qt in query_tokens if qt in core_words)
            )

            if is_match:
                if item["item_name"] in chaos_flags["out_of_stock_items"]:
                    current_stock = 0
                else:
                    current_stock = item["stock_qty"]

                multiplier = chaos_flags["price_spikes"].get(item["item_name"], 1.0)
                unit_price = round(item["unit_price"] * multiplier, 2)
                delivery_fee = item["delivery_fee"]
                landed_price = round(unit_price * qty + delivery_fee, 2)

                offer = Offer(
                    id=f"off-{self.id}-{item['sku']}-{uuid.uuid4().hex[:6]}",
                    intent_id="",
                    merchant_id=self.id,
                    merchant_name=self.name,
                    sku=item["sku"],
                    title=item["title"],
                    brand=item["brand"],
                    size=item["size"],
                    unit_price=unit_price,
                    delivery_fee=delivery_fee,
                    landed_price=landed_price,
                    currency="USD",
                    stock_qty=current_stock,
                    eta_minutes=item["eta_minutes"],
                    rating=item["rating"],
                    reliability=self.reliability,
                    fetched_at=clock.now().isoformat(),
                )
                results.append(offer)

        # Dynamic Catalog Synthesizer for open-ended culinary ingredients & custom items
        if not results and query_clean and query_clean not in chaos_flags["out_of_stock_items"]:
            seed_val = sum(ord(c) for c in query_clean)
            base_price = round(2.99 + (seed_val % 650) / 100.0, 2)  # $2.99 - $9.49 realistic grocery/item price
            profiles = {
                "quick10": {"mult": 1.10, "fee": 1.49, "eta": 16, "rating": 4.8, "brand": "FreshExpress"},
                "zipbasket": {"mult": 1.04, "fee": 0.99, "eta": 26, "rating": 4.7, "brand": "ZipSelect"},
                "cornerstore": {"mult": 0.96, "fee": 0.79, "eta": 70, "rating": 4.5, "brand": "LocalMarket"},
                "megamart": {"mult": 0.85, "fee": 0.00, "eta": 1440, "rating": 4.7, "brand": "MegaValue"},
                "bulkbarn": {"mult": 0.82, "fee": 0.00, "eta": 2160, "rating": 4.6, "brand": "BulkChoice"},
            }
            prof = profiles.get(self.id, {"mult": 1.0, "fee": 0.99, "eta": 30, "rating": 4.6, "brand": "Standard"})
            multiplier = chaos_flags["price_spikes"].get(query_clean, 1.0)
            unit_price = round(base_price * prof["mult"] * multiplier, 2)
            delivery_fee = prof["fee"]
            landed_price = round(unit_price * qty + delivery_fee, 2)
            sku_code = "".join(ch for ch in query_clean.upper() if ch.isalnum())[:6] or "ITEM"

            results.append(
                Offer(
                    id=f"off-{self.id}-{sku_code}-{uuid.uuid4().hex[:6]}",
                    intent_id="",
                    merchant_id=self.id,
                    merchant_name=self.name,
                    sku=f"{self.id[:2].upper()}-{sku_code}-1",
                    title=f"{prof['brand']} {query.strip().title()}",
                    brand=prof["brand"],
                    size=spec.size or "standard",
                    unit_price=unit_price,
                    delivery_fee=delivery_fee,
                    landed_price=landed_price,
                    currency="USD",
                    stock_qty=20,
                    eta_minutes=prof["eta"],
                    rating=prof["rating"],
                    reliability=self.reliability,
                    fetched_at=clock.now().isoformat(),
                )
            )

        return results

    async def place_order(self, offer: Offer, qty: float, idem_key: str) -> MerchantOrder:
        if self.id in chaos_flags["down_merchants"]:
            raise RuntimeError(f"Order placement failed: '{self.name}' is unreachable.")

        order_ref = f"{self.id.upper()}-ORD-{uuid.uuid4().hex[:8].upper()}"
        merchant_order = MerchantOrder(
            merchant_id=self.id,
            merchant_order_ref=order_ref,
            offer_id=offer.id,
            sku=offer.sku,
            qty=qty,
            total_amount=offer.landed_price,
            currency="USD",
            status="CONFIRMED",
            eta_minutes=offer.eta_minutes,
            tracking_url=f"https://mock-track.{self.id}.com/{order_ref}",
        )
        self._orders[order_ref] = merchant_order
        return merchant_order

    async def get_order(self, ref: str) -> MerchantOrder:
        if ref in self._orders:
            return self._orders[ref]
        raise KeyError(f"Order ref '{ref}' not found in {self.name}.")

    async def cancel_order(self, ref: str) -> bool:
        if ref in self._orders:
            order = self._orders[ref]
            if order.status in ["CONFIRMED", "PACKED"]:
                order.status = "FAILED"
                return True
        return False


class Channel3LiveAdapter(MockMerchant):
    """
    Live Channel3 Product Search SDK Adapter (Ekansh Tiwari — Channel3 integration).
    Activates automatically when CHANNEL3_API_KEY is configured and channel3-sdk is installed;
    gracefully returns empty list if unconfigured or offline.
    """
    def __init__(self):
        super().__init__("channel3", "Channel3 Live", "marketplace", reliability=0.96)
        self.api_key: Optional[str] = settings.CHANNEL3_API_KEY

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str, spec: ItemSpec, qty: float) -> List[Offer]:
        if not self.is_enabled() or self.id in chaos_flags["down_merchants"]:
            return []
        try:
            from channel3_sdk import Channel3  # type: ignore

            def _sync_search():
                client = Channel3(api_key=self.api_key)
                res = client.products.search(query=query, limit=5)
                return [p for _, p in zip(range(5), res)]

            products = await asyncio.to_thread(_sync_search)
            offers: List[Offer] = []
            for idx, prod in enumerate(products):
                title = getattr(prod, "title", None) or str(prod)
                brand = getattr(prod, "brand", None) or (spec.brand_pref or "Channel3")
                price_raw = getattr(prod, "price", None) or 14.99
                try:
                    unit_price = round(float(price_raw), 2)
                except (TypeError, ValueError):
                    unit_price = 14.99
                delivery_fee = 0.0
                landed = round(unit_price * qty + delivery_fee, 2)
                offers.append(
                    Offer(
                        id=f"off-ch3-{idx}-{uuid.uuid4().hex[:6]}",
                        intent_id="",
                        merchant_id=self.id,
                        merchant_name=self.name,
                        sku=f"CH3-{idx+1}",
                        title=title[:120],
                        brand=str(brand),
                        size=spec.size or "standard",
                        unit_price=unit_price,
                        delivery_fee=delivery_fee,
                        landed_price=landed,
                        currency="USD",
                        stock_qty=20,
                        eta_minutes=1440,
                        rating=4.6,
                        reliability=self.reliability,
                        fetched_at=clock.now().isoformat(),
                    )
                )
            return offers
        except Exception as e:
            logger.debug(f"Channel3 adapter skipped ({e})")
            return []


MerchantAdapter = MockMerchant
MockMerchantAdapter = MockMerchant
channel3_adapter = Channel3LiveAdapter()

MERCHANTS: Dict[str, MockMerchant] = {
    "quick10": MockMerchant("quick10", "Quick10", "quick", reliability=0.98),
    "zipbasket": MockMerchant("zipbasket", "ZipBasket", "quick", reliability=0.96),
    "cornerstore": MockMerchant("cornerstore", "CornerStore", "local", reliability=0.92),
    "megamart": MockMerchant("megamart", "MegaMart", "marketplace", reliability=0.95),
    "bulkbarn": MockMerchant("bulkbarn", "BulkBarn", "wholesale", reliability=0.94),
}
