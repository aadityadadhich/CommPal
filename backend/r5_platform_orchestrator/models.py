from sqlalchemy import Column, String, Float, Boolean, Integer, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from backend.r5_platform_orchestrator.database import Base

# Also import and re-export Milind's Payment models from R1
from backend.r1_payments_wallet.models import Payment, PaymentEvent, WalletLedger

class ItemModel(Base):
    __tablename__ = "items"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    unit = Column(String, default="unit")
    category = Column(String, default="grocery")
    perishable = Column(Boolean, default=False)
    fulfilment_class = Column(String, default="any")  # quick, standard, any
    spec_json = Column(Text, default="{}")  # brand_pref, size, min_rating, required_brand
    reorder_qty = Column(Float, default=1.0)
    threshold_days = Column(Float, default=3.0)
    safety_days = Column(Float, default=1.0)
    rate_per_day = Column(Float, default=0.5)
    rate_source = Column(String, default="user")  # user, learned
    stock_qty = Column(Float, default=0.0)
    stock_confidence = Column(Float, default=1.0)
    last_confirmed_at = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

    rules = relationship("RuleModel", back_populates="item", cascade="all, delete-orphan")
    stock_events = relationship("StockEventModel", back_populates="item", cascade="all, delete-orphan")

class StockEventModel(Base):
    __tablename__ = "stock_events"
    
    id = Column(String, primary_key=True, index=True)
    item_id = Column(String, ForeignKey("items.id"), index=True, nullable=False)
    delta = Column(Float, nullable=False)
    reason = Column(String, nullable=False)  # user_said, auto_consumption, delivery, correction
    source = Column(String, default="system")
    created_at = Column(String, nullable=False)

    item = relationship("ItemModel", back_populates="stock_events")

class RuleModel(Base):
    __tablename__ = "rules"
    
    id = Column(String, primary_key=True, index=True)
    item_id = Column(String, ForeignKey("items.id"), index=True, nullable=False)
    type = Column(String, nullable=False)  # daily, weekly, monthly, depletion
    params_json = Column(Text, default="{}")
    qty = Column(Float, default=1.0)
    paused_until = Column(String, nullable=True)
    skip_next = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    created_at = Column(String, nullable=False)

    item = relationship("ItemModel", back_populates="rules")

class OrderIntentModel(Base):
    __tablename__ = "order_intents"
    
    id = Column(String, primary_key=True, index=True)
    item_id = Column(String, nullable=True, index=True)
    item_name = Column(String, nullable=False)
    qty = Column(Float, default=1.0)
    source = Column(String, default="chat")  # chat, rule, depletion
    rule_id = Column(String, nullable=True)
    period_key = Column(String, nullable=True)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    urgency_class = Column(String, default="ROUTINE")  # URGENT, ROUTINE, PLANNED
    needed_by = Column(String, nullable=False)
    state = Column(String, default="DRAFT", index=True)
    created_at = Column(String, nullable=False)

    __table_args__ = (
        Index("ix_rule_period", "rule_id", "period_key", unique=False),
    )

class OfferModel(Base):
    __tablename__ = "offers"
    
    id = Column(String, primary_key=True, index=True)
    intent_id = Column(String, ForeignKey("order_intents.id"), index=True, nullable=False)
    merchant_id = Column(String, nullable=False)
    merchant_name = Column(String, nullable=False)
    sku = Column(String, nullable=False)
    title = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    size = Column(String, nullable=False)
    unit_price = Column(Float, nullable=False)
    delivery_fee = Column(Float, default=0.0)
    landed_price = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    stock_qty = Column(Integer, default=10)
    eta_minutes = Column(Integer, nullable=False)
    rating = Column(Float, default=4.5)
    reliability = Column(Float, default=0.95)
    fetched_at = Column(String, nullable=False)

class DecisionModel(Base):
    __tablename__ = "decisions"
    
    id = Column(String, primary_key=True, index=True)
    intent_id = Column(String, ForeignKey("order_intents.id"), unique=True, index=True, nullable=False)
    chosen_offer_id = Column(String, nullable=False)
    runner_up_offer_id = Column(String, nullable=True)
    weights_json = Column(Text, nullable=False)
    score_breakdown_json = Column(Text, nullable=False)
    filtered_out_json = Column(Text, default="{}")
    explanation = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)

class VerdictModel(Base):
    __tablename__ = "verdicts"
    
    id = Column(String, primary_key=True, index=True)
    intent_id = Column(String, ForeignKey("order_intents.id"), index=True, nullable=False)
    mandate_version = Column(Integer, nullable=False)
    result = Column(String, nullable=False)  # ALLOW, NEEDS_APPROVAL, DENY
    reasons_json = Column(Text, default="[]")
    rule_ids_json = Column(Text, default="[]")
    created_at = Column(String, nullable=False)

class ApprovalModel(Base):
    __tablename__ = "approvals"
    
    id = Column(String, primary_key=True, index=True)
    intent_id = Column(String, ForeignKey("order_intents.id"), unique=True, index=True, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED, EXPIRED
    requested_at = Column(String, nullable=False)
    expires_at = Column(String, nullable=False)
    decided_by = Column(String, nullable=True)  # user
    decided_at = Column(String, nullable=True)

class OrderModel(Base):
    __tablename__ = "orders"
    
    id = Column(String, primary_key=True, index=True)
    intent_id = Column(String, ForeignKey("order_intents.id"), unique=True, index=True, nullable=False)
    merchant_id = Column(String, nullable=False)
    merchant_name = Column(String, nullable=False)
    item_name = Column(String, nullable=False)
    qty = Column(Float, default=1.0)
    merchant_order_ref = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    paypal_auth_id = Column(String, nullable=True)
    paypal_capture_id = Column(String, nullable=True)
    state = Column(String, default="DRAFT", index=True)
    eta_minutes = Column(Integer, default=30)
    created_at = Column(String, nullable=False)
    delivered_at = Column(String, nullable=True)

class WalletLedgerModel(Base):
    __tablename__ = "wallet_ledger"
    
    id = Column(String, primary_key=True, index=True)
    account = Column(String, nullable=False)  # available, held, spent
    delta = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    ref_type = Column(String, nullable=False)  # top_up, reserve, settle, release, refund
    ref_id = Column(String, nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(String, nullable=False)

class MandateModel(Base):
    __tablename__ = "mandates"
    
    id = Column(String, primary_key=True, index=True)
    version = Column(Integer, nullable=False, index=True)
    body_json = Column(Text, nullable=False)
    created_by = Column(String, default="user")
    created_at = Column(String, nullable=False)
    active = Column(Boolean, default=True)

class AuditLogModel(Base):
    __tablename__ = "audit_log"
    
    seq = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String, unique=True, index=True)
    ts = Column(String, nullable=False, index=True)
    actor = Column(String, nullable=False)  # user, agent, scheduler, system
    event_type = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    payload_json = Column(Text, default="{}")
    mandate_version = Column(Integer, default=1)
    prev_hash = Column(String, nullable=False)
    hash = Column(String, nullable=False)
