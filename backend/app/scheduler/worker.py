import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.app.db.database import SessionLocal
from backend.app.db.models import RuleModel, ItemModel, OrderIntentModel, OrderModel, ApprovalModel
from backend.app.contracts.orders import OrderIntentCreate
from backend.app.pipeline.orchestrator import purchase_pipeline
from backend.app.inventory.service import inventory_service
from backend.app.scheduler.virtual_clock import clock
from backend.app.audit.hash_chain import append_audit_event

class TickWorker:
    @staticmethod
    async def run_tick(db: Session) -> Dict[str, Any]:
        now = clock.now()
        now_str = now.isoformat()
        results = {
            "timestamp": now_str,
            "rules_fired": 0,
            "depletions_fired": 0,
            "approvals_expired": 0,
            "orders_delivered": 0
        }

        # 1. Expire stale approvals
        pending_approvals = db.query(ApprovalModel).filter(ApprovalModel.status == "PENDING").all()
        for app in pending_approvals:
            try:
                exp_dt = datetime.fromisoformat(app.expires_at)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if now > exp_dt:
                    app.status = "EXPIRED"
                    intent = db.query(OrderIntentModel).filter(OrderIntentModel.id == app.intent_id).first()
                    if intent:
                        intent.state = "EXPIRED"
                    results["approvals_expired"] += 1
            except Exception:
                pass
        db.commit()

        # 2. Advance simulated deliveries (orders in transit -> delivered)
        transit_orders = db.query(OrderModel).filter(OrderModel.state == "IN_TRANSIT").all()
        for ord_row in transit_orders:
            try:
                created_dt = datetime.fromisoformat(ord_row.created_at)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                # If virtual time passed eta_minutes, mark delivered
                if now >= created_dt + timedelta(minutes=ord_row.eta_minutes):
                    ord_row.state = "DELIVERED"
                    ord_row.delivered_at = now_str
                    results["orders_delivered"] += 1
                    
                    # Restock inventory
                    item = inventory_service.get_item_by_name(db, ord_row.item_name)
                    if item:
                        item.stock_qty += ord_row.qty
                        item.stock_confidence = 1.0
                        item.last_confirmed_at = now_str
                        
                    append_audit_event(
                        db=db,
                        actor="scheduler",
                        event_type="ORDER_DELIVERED",
                        entity_type="order",
                        entity_id=ord_row.id,
                        payload={"item_name": ord_row.item_name, "merchant": ord_row.merchant_name}
                    )
            except Exception:
                pass
        db.commit()

        # 3. Fire due recurring rules
        # Period key: daily: YYYY-MM-DD, monthly: YYYY-MM
        active_rules = db.query(RuleModel).filter(RuleModel.active == True).all()
        for rule in active_rules:
            item = db.query(ItemModel).filter(ItemModel.id == rule.item_id).first()
            if not item:
                continue

            if rule.type == "daily":
                period_key = now.strftime("%Y-%m-%d")
            elif rule.type == "weekly":
                period_key = now.strftime("%Y-W%W")
            elif rule.type == "monthly":
                period_key = now.strftime("%Y-%m")
            elif rule.type == "depletion":
                continue # handled below
            else:
                period_key = f"unknown-{now.strftime('%Y-%m-%d')}"

            # Idempotency check: did this rule fire in this period?
            already_fired = db.query(OrderIntentModel).filter(
                OrderIntentModel.rule_id == rule.id,
                OrderIntentModel.period_key == period_key
            ).first()

            if not already_fired:
                # Fire recurring intent
                intent_in = OrderIntentCreate(
                    item_id=item.id,
                    item_name=item.name,
                    qty=rule.qty,
                    source="rule",
                    rule_id=rule.id,
                    idempotency_key=f"rule-{rule.id}-{period_key}"
                )
                res = await purchase_pipeline.request_purchase(db, intent_in, actor="scheduler")
                
                # Tag period_key on intent
                created_intent = db.query(OrderIntentModel).filter(OrderIntentModel.idempotency_key == f"rule-{rule.id}-{period_key}").first()
                if created_intent:
                    created_intent.period_key = period_key
                    db.commit()
                results["rules_fired"] += 1

        # 4. Check depletion triggers
        items = db.query(ItemModel).all()
        for it in items:
            cur_stock, days_of_cover, conf, _ = inventory_service.calculate_stock_and_cover(it, now)
            # If cover <= threshold, check for depletion rule
            if days_of_cover <= it.threshold_days:
                depletion_rule = db.query(RuleModel).filter(
                    RuleModel.item_id == it.id,
                    RuleModel.type == "depletion",
                    RuleModel.active == True
                ).first()
                if depletion_rule:
                    depletion_key = f"deplete-{it.id}-{now.strftime('%Y-%m-%d-%H')}"
                    already_depleted = db.query(OrderIntentModel).filter(
                        OrderIntentModel.idempotency_key == depletion_key
                    ).first()

                    if not already_depleted:
                        intent_in = OrderIntentCreate(
                            item_id=it.id,
                            item_name=it.name,
                            qty=it.reorder_qty,
                            source="depletion",
                            rule_id=depletion_rule.id,
                            idempotency_key=depletion_key,
                            urgency_hint="urgent" if cur_stock <= 0 else "routine"
                        )
                        await purchase_pipeline.request_purchase(db, intent_in, actor="scheduler")
                        results["depletions_fired"] += 1

        return results

tick_worker = TickWorker()
