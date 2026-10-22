import asyncio
import uuid
from typing import List, Optional, Literal, Dict, Any
from backend.app.contracts.items import ItemSpec
from backend.app.contracts.orders import Offer
from backend.app.merchants.base import MerchantOrder
from backend.app.merchants.catalogs import MOCK_CATALOGS, chaos_flags
from backend.app.scheduler.virtual_clock import clock

class MockMerchant:
    def __init__(
        self,
        id: str,
        name: str,
        kind: Literal["quick", "marketplace", "wholesale", "local"],
        reliability: float = 0.95
    ):
        self.id = id
        self.name = name
        self.kind = kind
        self.reliability = reliability
        self._orders: Dict[str, MerchantOrder] = {}

    async def search(self, query: str, spec: ItemSpec, qty: float) -> List[Offer]:
        # Chaos check: merchant down
        if self.id in chaos_flags["down_merchants"]:
            raise RuntimeError(f"Merchant '{self.name}' service is unavailable (503 Service Unavailable).")

        # Chaos check: merchant slow
        if self.id in chaos_flags["slow_merchants"]:
            await asyncio.sleep(2.5)  # Will trigger timeout if caller timeout is 2.0s
        else:
            await asyncio.sleep(0.05)  # Tiny realistic latency

        catalog = MOCK_CATALOGS.get(self.id, [])
        query_clean = query.strip().lower()
        results: List[Offer] = []
        
        for item in catalog:
            item_name = item["item_name"].lower()
            title = item["title"].lower()
            
            # Match if query appears in item_name/title or if significant query token matches item
            query_tokens = [w for w in query_clean.replace("-", "").split() if len(w) > 1]
            core_words = {"milk", "paper", "protein", "powder", "wd40", "eggs", "coffee", "bread", "detergent", "batteries"}
            
            is_match = (
                query_clean in item_name or 
                item_name in query_clean or 
                query_clean in title or
                any(qt in item_name or qt in title for qt in query_tokens if qt in core_words)
            )
            if is_match:
                # Chaos check: out of stock item
                if item["item_name"] in chaos_flags["out_of_stock_items"]:
                    current_stock = 0
                else:
                    current_stock = item["stock_qty"]

                # Chaos check: price spike
                multiplier = chaos_flags["price_spikes"].get(item["item_name"], 1.0)
                unit_price = round(item["unit_price"] * multiplier, 2)
                delivery_fee = item["delivery_fee"]
                landed_price = round(unit_price * qty + delivery_fee, 2)

                offer = Offer(
                    id=f"off-{self.id}-{item['sku']}-{uuid.uuid4().hex[:6]}",
                    intent_id="",  # will be set by caller
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
                    fetched_at=clock.now().isoformat()
                )
                results.append(offer)
                
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
            tracking_url=f"https://mock-track.{self.id}.com/{order_ref}"
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

# Registry of 5 mock merchants
MERCHANTS = {
    "quick10": MockMerchant("quick10", "Quick10", "quick", reliability=0.98),
    "zipbasket": MockMerchant("zipbasket", "ZipBasket", "quick", reliability=0.96),
    "cornerstore": MockMerchant("cornerstore", "CornerStore", "local", reliability=0.92),
    "megamart": MockMerchant("megamart", "MegaMart", "marketplace", reliability=0.95),
    "bulkbarn": MockMerchant("bulkbarn", "BulkBarn", "wholesale", reliability=0.94),
}
