from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

# --- Fulfilment & Inventory Types ---
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


# --- Mandate & Security Types ---
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


# --- Orders & Offers Types ---
UrgencyClass = Literal["URGENT", "ROUTINE", "PLANNED"]
OrderState = Literal[
    "DRAFT", "QUOTED", "DECIDED", 
    "PENDING_APPROVAL", "APPROVED", "REJECTED", "EXPIRED", 
    "AUTHORIZED", "PLACED", "CAPTURED", 
    "IN_TRANSIT", "DELIVERED", "CLOSED", 
    "PAYMENT_FAILED", "MERCHANT_FAILED", "VOIDED", "REFUNDED"
]

class Offer(BaseModel):
    id: str
    intent_id: str
    merchant_id: str
    merchant_name: str
    sku: str
    title: str
    brand: str
    size: str
    unit_price: float
    delivery_fee: float
    landed_price: float
    currency: str = "USD"
    stock_qty: int
    eta_minutes: int
    rating: float
    reliability: float = 0.95
    fetched_at: str

class DecisionScoreBreakdown(BaseModel):
    offer_id: str
    merchant_id: str
    price_score: float
    eta_score: float
    rating_score: float
    fit_score: float
    total_score: float

class Decision(BaseModel):
    id: str
    intent_id: str
    chosen_offer: Offer
    runner_up_offer: Optional[Offer] = None
    urgency_class: UrgencyClass
    weights: Dict[str, float]
    score_breakdown: List[DecisionScoreBreakdown]
    filtered_out: Dict[str, str]
    explanation: str
    created_at: str

class OrderIntentCreate(BaseModel):
    item_id: Optional[str] = None
    item_name: str
    qty: float = 1.0
    source: Literal["chat", "rule", "depletion"] = "chat"
    urgency_hint: Optional[str] = None
    rule_id: Optional[str] = None
    idempotency_key: Optional[str] = None

class OrderIntentResponse(BaseModel):
    id: str
    item_id: Optional[str]
    item_name: str
    qty: float
    source: str
    rule_id: Optional[str]
    period_key: Optional[str]
    idempotency_key: str
    urgency_class: UrgencyClass
    needed_by: str
    state: OrderState
    created_at: str

class Order(BaseModel):
    id: str
    intent_id: str
    merchant_id: str
    merchant_name: str
    item_name: str
    qty: float
    amount: float
    currency: str
    paypal_auth_id: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    state: OrderState
    eta_minutes: int
    decision: Optional[Decision] = None
    created_at: str
    delivered_at: Optional[str] = None

class OrderApprovalAction(BaseModel):
    action: Literal["approve", "reject"]
    reason: Optional[str] = None


# --- Wallet & Ledger Types ---
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


# --- Conversational Agent Types ---
class CardPayload(BaseModel):
    card_type: Literal["order_preview", "rule_created", "approval_needed", "order_status", "decision_explanation"]
    title: str
    subtitle: Optional[str] = None
    data: Dict[str, Any]

class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    cards: Optional[List[CardPayload]] = None
    timestamp: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = "default"
