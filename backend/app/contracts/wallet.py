from pydantic import BaseModel
from typing import Optional, Literal, Dict
from datetime import datetime

AccountType = Literal["available", "held", "spent"]
LedgerRefType = Literal["top_up", "reserve", "settle", "release", "refund"]

class LedgerEntry(BaseModel):
    id: str
    account: AccountType
    delta: float
    currency: str = "USD"
    ref_type: LedgerRefType
    ref_id: str
    idempotency_key: str
    created_at: str

class WalletSummary(BaseModel):
    available_balance: float
    held_balance: float
    spent_balance: float
    total_balance: float
    currency: str = "USD"
    daily_spent: float
    monthly_spent: float
    category_spent: Dict[str, float]
    daily_cap: float
    monthly_cap: float
    kill_switch: bool

class TopUpRequest(BaseModel):
    amount: float
    currency: str = "USD"
    payment_method: str = "paypal_sandbox"
