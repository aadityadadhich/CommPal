from typing import Protocol, List, Optional, Literal, runtime_checkable
from pydantic import BaseModel
from backend.app.contracts.items import ItemSpec
from backend.app.contracts.orders import Offer

class MerchantOrder(BaseModel):
    merchant_id: str
    merchant_order_ref: str
    offer_id: str
    sku: str
    qty: float
    total_amount: float
    currency: str = "USD"
    status: Literal["CONFIRMED", "PACKED", "IN_TRANSIT", "DELIVERED", "FAILED"]
    eta_minutes: int
    tracking_url: Optional[str] = None

@runtime_checkable
class MerchantAdapter(Protocol):
    id: str
    name: str
    kind: Literal["quick", "marketplace", "wholesale", "local"]
    reliability: float
    
    async def search(self, query: str, spec: ItemSpec, qty: float) -> List[Offer]:
        ...

    async def place_order(self, offer: Offer, qty: float, idem_key: str) -> MerchantOrder:
        ...

    async def get_order(self, ref: str) -> MerchantOrder:
        ...

    async def cancel_order(self, ref: str) -> bool:
        ...
