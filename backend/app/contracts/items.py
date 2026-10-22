from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict, Any
from datetime import datetime

FulfilmentClass = Literal["quick", "standard", "any"]

class ItemSpec(BaseModel):
    brand_pref: Optional[str] = None
    size: Optional[str] = None
    min_rating: float = 3.5
    required_brand: bool = False

class ItemBase(BaseModel):
    name: str
    unit: str = "unit"
    category: str = "grocery"
    perishable: bool = False
    fulfilment_class: FulfilmentClass = "any"
    spec: ItemSpec = Field(default_factory=ItemSpec)
    reorder_qty: float = 1.0
    threshold_days: float = 3.0
    safety_days: float = 1.0
    rate_per_day: float = 0.5
    rate_source: Literal["user", "learned"] = "user"
    stock_qty: float = 5.0
    stock_confidence: float = 1.0

class ItemCreate(ItemBase):
    pass

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    perishable: Optional[bool] = None
    fulfilment_class: Optional[FulfilmentClass] = None
    spec: Optional[ItemSpec] = None
    reorder_qty: Optional[float] = None
    threshold_days: Optional[float] = None
    safety_days: Optional[float] = None
    rate_per_day: Optional[float] = None
    stock_qty: Optional[float] = None
    stock_confidence: Optional[float] = None

class StockUpdateRequest(BaseModel):
    mode: Literal["absolute", "delta", "finished"] = "absolute"
    qty: Optional[float] = 0.0
    reason: Literal["user_said", "auto_consumption", "delivery", "correction"] = "user_said"

class ItemResponse(ItemBase):
    id: str
    days_of_cover: float = 0.0
    needed_by: Optional[str] = None
    last_confirmed_at: str
    created_at: str
    active_rules_count: int = 0
