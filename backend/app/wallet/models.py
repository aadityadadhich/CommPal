import uuid
from sqlalchemy import Column, String, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.db.database import Base


class Payment(Base):
    """
    Payment lifecycle model (Milind Mathur — payments framework).
    Tracks user, provider references, checkout URL, and idempotency constraints.
    """
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, default="default_user", index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD", nullable=False)
    description = Column(String, default="")
    status = Column(String, default="pending", index=True, nullable=False)  # pending, succeeded, failed, canceled
    provider = Column(String, default="paypal_sandbox", nullable=False)
    provider_reference = Column(String, default="")
    checkout_url = Column(String, default="")
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    events = relationship("PaymentEvent", back_populates="payment", cascade="all, delete-orphan")


class PaymentEvent(Base):
    """
    Webhook event deduplication table (Milind Mathur — payments framework).
    Guarantees each (provider, event_id) is processed at most once.
    """
    __tablename__ = "payment_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, ForeignKey("payments.id"), index=True, nullable=True)
    provider = Column(String, nullable=False)
    event_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload_json = Column(Text, default="{}")
    received_at = Column(String, nullable=False)

    payment = relationship("Payment", back_populates="events")

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_provider_event_id"),
    )


class WalletLedger(Base):
    """
    Append-only 3-bucket wallet ledger (available, held, spent).
    """
    __tablename__ = "wallet_ledger"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    account = Column(String, nullable=False)  # available, held, spent
    delta = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    ref_type = Column(String, nullable=False)  # top_up, reserve, settle, release, refund
    ref_id = Column(String, nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(String, nullable=False)
