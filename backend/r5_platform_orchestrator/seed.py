import uuid
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from backend.r5_platform_orchestrator.database import Base, engine, SessionLocal
from backend.r5_platform_orchestrator.models import (
    ItemModel, RuleModel, MandateModel, WalletLedgerModel, 
    OrderIntentModel, OfferModel, DecisionModel, VerdictModel, 
    ApprovalModel, OrderModel, AuditLogModel, StockEventModel
)
from backend.r5_platform_orchestrator.contracts import MandateBody, MandateLimits, MerchantRules, ItemRules, AnomalyRules, ItemSpec
from backend.r1_payments_wallet.ledger import ledger_service
from backend.r5_platform_orchestrator.clock import clock
from backend.r2_policy_security_audit.hash_chain import append_audit_event
from backend.r4_aggregation_router.catalogs import reset_chaos

def init_db():
    Base.metadata.create_all(bind=engine)

def seed_week_with_asha(db: Session):
    # 1. Reset all existing tables
    db.query(AuditLogModel).delete()
    db.query(WalletLedgerModel).delete()
    db.query(OrderModel).delete()
    db.query(ApprovalModel).delete()
    db.query(VerdictModel).delete()
    db.query(DecisionModel).delete()
    db.query(OfferModel).delete()
    db.query(OrderIntentModel).delete()
    db.query(RuleModel).delete()
    db.query(StockEventModel).delete()
    db.query(ItemModel).delete()
    db.query(MandateModel).delete()
    db.commit()

    reset_chaos()
    clock.reset()
    now = clock.now()
    now_str = now.isoformat()

    # 2. Seed Mandate v1
    mandate_body = MandateBody(
        version=1,
        currency="USD",
        kill_switch=False,
        limits=MandateLimits(
            per_txn_max=60.0,
            auto_approve_under=25.0,
            daily_cap=80.0,
            monthly_cap=400.0
        ),
        category_budgets={
            "grocery": 250.0,
            "supplies": 80.0,
            "fitness": 100.0
        },
        merchants=MerchantRules(
            allow=["quick10", "zipbasket", "megamart", "bulkbarn", "cornerstore"],
            block=[]
        ),
        items=ItemRules(allow_untracked=False),
        anomaly=AnomalyRules(
            price_spike_pct=30.0,
            max_qty_multiple=2.0,
            duplicate_window_hours=12
        ),
        approval_expiry_minutes=30
    )

    mandate_row = MandateModel(
        id=str(uuid.uuid4()),
        version=1,
        body_json=mandate_body.model_dump_json(),
        created_by="Asha (User)",
        created_at=now_str,
        active=True
    )
    db.add(mandate_row)
    db.commit()

    # 3. Fund Wallet with $200
    ledger_service.top_up(
        db=db,
        amount=200.00,
        currency="USD",
        idem_key=f"seed-topup-{uuid.uuid4().hex[:6]}",
        ref_id="initial_funding"
    )

    # 4. Seed Tracked Items
    # Item 1: Milk (Daily perishable)
    milk_spec = ItemSpec(brand_pref="Organic Valley", min_rating=4.0, required_brand=False)
    milk = ItemModel(
        id="item-milk",
        name="Whole Milk 1L",
        unit="bottle",
        category="grocery",
        perishable=True,
        fulfilment_class="quick",
        spec_json=milk_spec.model_dump_json(),
        reorder_qty=1.0,
        threshold_days=1.0,
        safety_days=0.5,
        rate_per_day=1.0,  # 1 bottle per day
        rate_source="user",
        stock_qty=1.0,     # 1 day of cover left
        stock_confidence=1.0,
        last_confirmed_at=now_str,
        created_at=now_str
    )

    # Item 2: Protein Powder (Monthly)
    protein_spec = ItemSpec(brand_pref="Optimum Nutrition", size="1kg", min_rating=4.5)
    protein = ItemModel(
        id="item-protein",
        name="Whey Protein Powder 1kg",
        unit="tub",
        category="fitness",
        perishable=False,
        fulfilment_class="any",
        spec_json=protein_spec.model_dump_json(),
        reorder_qty=1.0,
        threshold_days=5.0,
        safety_days=2.0,
        rate_per_day=0.033,  # ~1 tub per 30 days
        rate_source="user",
        stock_qty=0.4,       # ~12 days of cover left
        stock_confidence=0.9,
        last_confirmed_at=now_str,
        created_at=now_str
    )

    # Item 3: A4 Paper (Depletion rule, 14 days of cover)
    paper_spec = ItemSpec(brand_pref="HP", size="500 sheets", min_rating=4.2)
    paper = ItemModel(
        id="item-paper",
        name="A4 Copy Paper 500ct",
        unit="ream",
        category="supplies",
        perishable=False,
        fulfilment_class="any",
        spec_json=paper_spec.model_dump_json(),
        reorder_qty=1.0,
        threshold_days=3.0,
        safety_days=1.0,
        rate_per_day=0.071,  # 1 ream per 14 days
        rate_source="user",
        stock_qty=1.0,       # 14 days of cover
        stock_confidence=1.0,
        last_confirmed_at=now_str,
        created_at=now_str
    )

    db.add_all([milk, protein, paper])
    db.commit()

    # 5. Seed Rules
    # Rule 1: Daily Milk
    rule_milk = RuleModel(
        id="rule-daily-milk",
        item_id=milk.id,
        type="daily",
        params_json=json.dumps({"delivery_slot": "morning", "target_hour": 7}),
        qty=1.0,
        active=True,
        created_at=now_str
    )

    # Rule 2: Monthly Protein Powder
    rule_protein = RuleModel(
        id="rule-monthly-protein",
        item_id=protein.id,
        type="monthly",
        params_json=json.dumps({"day_of_month": 1}),
        qty=1.0,
        active=True,
        created_at=now_str
    )

    # Rule 3: Depletion Trigger on A4 Paper
    rule_paper = RuleModel(
        id="rule-depletion-paper",
        item_id=paper.id,
        type="depletion",
        params_json=json.dumps({"threshold_days": 3.0}),
        qty=1.0,
        active=True,
        created_at=now_str
    )

    db.add_all([rule_milk, rule_protein, rule_paper])
    db.commit()

    # 6. Audit Trail Initialization
    append_audit_event(
        db=db,
        actor="system",
        event_type="SCENARIO_SEEDED",
        entity_type="scenario",
        entity_id="week_with_asha",
        payload={
            "scenario": "Week with Asha",
            "wallet_funded": 200.00,
            "items_count": 3,
            "rules_count": 3
        },
        mandate_version=1
    )

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    seed_week_with_asha(db)
    db.close()
    print("Database seeded with 'Week with Asha' scenario successfully.")
