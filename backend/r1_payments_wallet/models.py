import uuid
from sqlalchemy import Column, String, Float, Text, Integer, ForeignKey, UniqueConstraint, Index, DateTime
from sqlalchemy.orm import relationship
from backend.app.db.database import Base

class Payment(Base):
    """
    Incorporated from Milind's payment framework (origin/milind_dev: payments/models.py).
    Tracks payment lifecycle, user, provider references, and idempotency constraints.
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

    def __repr__(self) -> str:
        return f"<Payment {self.id} status={self.status} amount={self.amount}>"


class PaymentEvent(Base):
    """
    Incorporated from Milind's payment framework (origin/milind_dev: payments/models.py).
    Deduplicated, immutable record of verified webhook events.
    """
    __tablename__ = "payment_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String, ForeignKey("payments.id"), nullable=True, index=True)
    provider = Column(String, nullable=False)
    event_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    payload_json = Column(Text, default="{}")
    received_at = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_provider_event_id"),
    )

    payment = relationship("Payment", back_populates="events")

    def __repr__(self) -> str:
        return f"<PaymentEvent {self.provider}:{self.event_id}>"


class WalletLedger(Base):
    """
    CommPal double-entry style append-only ledger.
    Accounts: available, held, spent.
    """
    __tablename__ = "wallet_ledger_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    account = Column(String, nullable=False)  # available, held, spent
    delta = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    ref_type = Column(String, nullable=False)  # top_up, reserve, settle, release, refund
    ref_id = Column(String, nullable=False)
    idempotency_key = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<WalletLedger account={self.account} delta={self.delta} ref={self.ref_id}>"
