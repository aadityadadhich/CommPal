import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.db.models import WalletLedgerModel, OrderModel, ItemModel
from backend.app.contracts.wallet import WalletSummary
from backend.app.scheduler.virtual_clock import clock

class InsufficientFundsError(Exception):
    pass

class LedgerService:
    @staticmethod
    def get_balances(db: Session) -> Dict[str, float]:
        rows = db.query(
            WalletLedgerModel.account,
            func.coalesce(func.sum(WalletLedgerModel.delta), 0.0).label("total")
        ).group_by(WalletLedgerModel.account).all()
        
        totals = {"available": 0.0, "held": 0.0, "spent": 0.0}
        for account, total in rows:
            totals[account] = round(float(total), 2)
            
        return totals

    @staticmethod
    def get_wallet_summary(
        db: Session,
        daily_cap: float = 80.0,
        monthly_cap: float = 400.0,
        kill_switch: bool = False
    ) -> WalletSummary:
        balances = LedgerService.get_balances(db)
        now = clock.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

        # Spent today
        daily_spent_row = db.query(
            func.coalesce(func.sum(WalletLedgerModel.delta), 0.0)
        ).filter(
            WalletLedgerModel.account == "spent",
            WalletLedgerModel.created_at >= start_of_day
        ).scalar()
        daily_spent = round(float(daily_spent_row or 0.0), 2)

        # Spent this month
        monthly_spent_row = db.query(
            func.coalesce(func.sum(WalletLedgerModel.delta), 0.0)
        ).filter(
            WalletLedgerModel.account == "spent",
            WalletLedgerModel.created_at >= start_of_month
        ).scalar()
        monthly_spent = round(float(monthly_spent_row or 0.0), 2)

        # Category spending by joining orders and items
        category_spent: Dict[str, float] = {}
        orders = db.query(OrderModel).filter(OrderModel.state.in_(["CAPTURED", "IN_TRANSIT", "DELIVERED", "CLOSED"])).all()
        for o in orders:
            # Query item category
            item = db.query(ItemModel).filter(ItemModel.name.ilike(f"%{o.item_name}%")).first()
            cat = item.category.lower() if item else "general"
            category_spent[cat] = round(category_spent.get(cat, 0.0) + o.amount, 2)

        available = balances["available"]
        held = balances["held"]
        spent = balances["spent"]
        total = round(available + held, 2)  # total active funds in wallet

        return WalletSummary(
            available_balance=available,
            held_balance=held,
            spent_balance=spent,
            total_balance=total,
            currency="USD",
            daily_spent=daily_spent,
            monthly_spent=monthly_spent,
            category_spent=category_spent,
            daily_cap=daily_cap,
            monthly_cap=monthly_cap,
            kill_switch=kill_switch
        )

    @staticmethod
    def top_up(db: Session, amount: float, currency: str = "USD", idem_key: str = "", ref_id: str = "user_topup") -> WalletLedgerModel:
        if not idem_key:
            idem_key = f"topup-{uuid.uuid4().hex[:12]}"

        existing = db.query(WalletLedgerModel).filter(WalletLedgerModel.idempotency_key == idem_key).first()
        if existing:
            return existing

        entry = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="available",
            delta=round(amount, 2),
            currency=currency,
            ref_type="top_up",
            ref_id=ref_id,
            idempotency_key=idem_key,
            created_at=clock.now().isoformat()
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def reserve(db: Session, amount: float, currency: str, idem_key: str, ref_id: str) -> List[WalletLedgerModel]:
        # Idempotency check
        existing = db.query(WalletLedgerModel).filter(WalletLedgerModel.idempotency_key.like(f"{idem_key}%")).all()
        if existing:
            return existing

        balances = LedgerService.get_balances(db)
        if balances["available"] < amount:
            raise InsufficientFundsError(f"Insufficient funds: available ${balances['available']:.2f} < requested ${amount:.2f}")

        now_str = clock.now().isoformat()
        # Move available -> held
        entry_avail = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="available",
            delta=-round(amount, 2),
            currency=currency,
            ref_type="reserve",
            ref_id=ref_id,
            idempotency_key=f"{idem_key}-avail",
            created_at=now_str
        )
        entry_held = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="held",
            delta=round(amount, 2),
            currency=currency,
            ref_type="reserve",
            ref_id=ref_id,
            idempotency_key=f"{idem_key}-held",
            created_at=now_str
        )
        db.add_all([entry_avail, entry_held])
        db.commit()
        return [entry_avail, entry_held]

    @staticmethod
    def settle(db: Session, amount: float, currency: str, idem_key: str, ref_id: str) -> List[WalletLedgerModel]:
        existing = db.query(WalletLedgerModel).filter(WalletLedgerModel.idempotency_key.like(f"{idem_key}%")).all()
        if existing:
            return existing

        now_str = clock.now().isoformat()
        # Move held -> spent
        entry_held = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="held",
            delta=-round(amount, 2),
            currency=currency,
            ref_type="settle",
            ref_id=ref_id,
            idempotency_key=f"{idem_key}-held",
            created_at=now_str
        )
        entry_spent = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="spent",
            delta=round(amount, 2),
            currency=currency,
            ref_type="settle",
            ref_id=ref_id,
            idempotency_key=f"{idem_key}-spent",
            created_at=now_str
        )
        db.add_all([entry_held, entry_spent])
        db.commit()
        return [entry_held, entry_spent]

    @staticmethod
    def release(db: Session, amount: float, currency: str, idem_key: str, ref_id: str) -> List[WalletLedgerModel]:
        existing = db.query(WalletLedgerModel).filter(WalletLedgerModel.idempotency_key.like(f"{idem_key}%")).all()
        if existing:
            return existing

        now_str = clock.now().isoformat()
        # Move held -> available (releasing reserved hold)
        entry_held = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="held",
            delta=-round(amount, 2),
            currency=currency,
            ref_type="release",
            ref_id=ref_id,
            idempotency_key=f"{idem_key}-held",
            created_at=now_str
        )
        entry_avail = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="available",
            delta=round(amount, 2),
            currency=currency,
            ref_type="release",
            ref_id=ref_id,
            idempotency_key=f"{idem_key}-avail",
            created_at=now_str
        )
        db.add_all([entry_held, entry_avail])
        db.commit()
        return [entry_held, entry_avail]

    @staticmethod
    def refund(db: Session, amount: float, currency: str, idem_key: str, ref_id: str) -> List[WalletLedgerModel]:
        existing = db.query(WalletLedgerModel).filter(WalletLedgerModel.idempotency_key.like(f"{idem_key}%")).all()
        if existing:
            return existing

        now_str = clock.now().isoformat()
        # Move spent -> available
        entry_spent = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="spent",
            delta=-round(amount, 2),
            currency=currency,
            ref_type="refund",
            ref_id=ref_id,
            idempotency_key=f"{idem_key}-spent",
            created_at=now_str
        )
        entry_avail = WalletLedgerModel(
            id=str(uuid.uuid4()),
            account="available",
            delta=round(amount, 2),
            currency=currency,
            ref_type="refund",
            ref_id=ref_id,
            idempotency_key=f"{idem_key}-avail",
            created_at=now_str
        )
        db.add_all([entry_spent, entry_avail])
        db.commit()
        return [entry_spent, entry_avail]

ledger_service = LedgerService()
