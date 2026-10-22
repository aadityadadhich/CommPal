from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal

VerdictResult = Literal["ALLOW", "NEEDS_APPROVAL", "DENY"]

class MandateLimits(BaseModel):
    per_txn_max: float = 60.0
    auto_approve_under: float = 25.0
    daily_cap: float = 80.0
    monthly_cap: float = 400.0

class MerchantRules(BaseModel):
    allow: List[str] = Field(default_factory=lambda: ["quick10", "zipbasket", "megamart", "bulkbarn", "cornerstore"])
    block: List[str] = Field(default_factory=list)

class ItemRules(BaseModel):
    allow_untracked: bool = False

class AnomalyRules(BaseModel):
    price_spike_pct: float = 30.0
    max_qty_multiple: float = 2.0
    duplicate_window_hours: int = 12

class MandateBody(BaseModel):
    version: int = 1
    currency: str = "USD"
    kill_switch: bool = False
    limits: MandateLimits = Field(default_factory=MandateLimits)
    category_budgets: Dict[str, float] = Field(default_factory=lambda: {
        "grocery": 250.0,
        "supplies": 80.0,
        "fitness": 100.0
    })
    merchants: MerchantRules = Field(default_factory=MerchantRules)
    items: ItemRules = Field(default_factory=ItemRules)
    anomaly: AnomalyRules = Field(default_factory=AnomalyRules)
    approval_expiry_minutes: int = 30

class Verdict(BaseModel):
    result: VerdictResult
    reasons: List[str]
    rule_ids: List[str]
    mandate_version: int

class KillSwitchRequest(BaseModel):
    active: bool
    reason: Optional[str] = "User manual trigger"
