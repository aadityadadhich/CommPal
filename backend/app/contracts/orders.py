from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

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
    filtered_out: Dict[str, str]  # merchant_id -> reason
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
