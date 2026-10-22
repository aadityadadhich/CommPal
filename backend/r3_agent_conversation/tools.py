import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.contracts.items import StockUpdateRequest, ItemCreate, ItemSpec
from backend.app.contracts.orders import OrderIntentCreate
from backend.app.contracts.chat import CardPayload
from backend.app.inventory.service import inventory_service
from backend.app.pipeline.orchestrator import purchase_pipeline
from backend.app.wallet.ledger import ledger_service
from backend.app.router.aggregator import router_aggregator
from backend.app.db.models import RuleModel, OrderModel, DecisionModel, ItemModel
from backend.app.scheduler.virtual_clock import clock
from backend.app.audit.hash_chain import append_audit_event

class AgentToolHandler:
    @staticmethod
    def list_items(db: Session) -> Dict[str, Any]:
        items = inventory_service.get_all_items(db)
        return {"items": [it.model_dump() for it in items]}

    @staticmethod
    def get_wallet_summary(db: Session) -> Dict[str, Any]:
        mandate, _ = purchase_pipeline.get_active_mandate(db)
        summary = ledger_service.get_wallet_summary(
            db=db,
            daily_cap=mandate.limits.daily_cap,
            monthly_cap=mandate.limits.monthly_cap,
            kill_switch=mandate.kill_switch
        )
        return summary.model_dump()

    @staticmethod
    def get_mandate_summary(db: Session) -> Dict[str, Any]:
        mandate, version = purchase_pipeline.get_active_mandate(db)
        return {"version": version, "body": mandate.model_dump()}

    @staticmethod
    def set_stock(db: Session, item_name: str, qty: float = 0.0, mode: str = "absolute", reason: str = "user_said") -> Dict[str, Any]:
        item = inventory_service.get_item_by_name(db, item_name)
        if not item:
            item = inventory_service.create_item(db=db, item_in=ItemCreate(name=item_name, stock_qty=qty))
        else:
            item = inventory_service.update_stock(db=db, item_id=item.id, update_req=StockUpdateRequest(mode=mode, qty=qty, reason=reason))

        cur_stock, doc, conf, _ = inventory_service.calculate_stock_and_cover(item, clock.now())
        return {
            "item_name": item.name,
            "current_stock": cur_stock,
            "days_of_cover": doc,
            "confidence": conf,
            "message": f"Updated stock for {item.name} to {cur_stock} {item.unit} ({doc} days of cover)."
        }

    @staticmethod
    def create_rule(db: Session, item_name: str, rule_type: str, qty: float = 1.0, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        item = inventory_service.get_item_by_name(db, item_name)
        if not item:
            item = inventory_service.create_item(db=db, item_in=ItemCreate(name=item_name, stock_qty=1.0))

        rule_id = f"rule-{rule_type}-{item.id}"
        existing = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
        if existing:
            existing.active = True
            existing.qty = qty
            existing.params_json = json.dumps(params or {})
        else:
            new_rule = RuleModel(
                id=rule_id,
                item_id=item.id,
                type=rule_type,
                qty=qty,
                params_json=json.dumps(params or {}),
                active=True,
                created_at=clock.now().isoformat()
            )
            db.add(new_rule)
        db.commit()

        append_audit_event(
            db=db,
            actor="agent",
            event_type="RULE_CREATED",
            entity_type="rule",
            entity_id=rule_id,
            payload={"item_name": item.name, "rule_type": rule_type, "qty": qty}
        )

        return {
            "success": True,
            "rule_id": rule_id,
            "item_name": item.name,
            "type": rule_type,
            "qty": qty,
            "card": CardPayload(
                card_type="rule_created",
                title=f"Autonomous Rule Created: {item.name}",
                subtitle=f"Schedule: {rule_type.capitalize()} (Qty: {qty})",
                data={"rule_type": rule_type, "qty": qty, "item": item.name}
            ).model_dump()
        }

    @staticmethod
    async def request_purchase(db: Session, item_name: str, qty: float = 1.0, urgency_hint: Optional[str] = None) -> Dict[str, Any]:
        intent_in = OrderIntentCreate(item_name=item_name, qty=qty, source="chat", urgency_hint=urgency_hint)
        result = await purchase_pipeline.request_purchase(db, intent_in, actor="agent")

        cards = []
        if result.get("status") == "ORDER_PLACED":
            cards.append(CardPayload(
                card_type="order_status",
                title=f"Order Dispatched: {item_name}",
                subtitle=f"Placed with {result.get('merchant')} - Arriving in {result.get('eta_minutes')} mins",
                data=result
            ).model_dump())
        elif result.get("status") == "PENDING_APPROVAL":
            cards.append(CardPayload(
                card_type="approval_needed",
                title=f"Approval Required: {item_name}",
                subtitle=result.get("message"),
                data=result
            ).model_dump())

        return {**result, "cards": cards}

    @staticmethod
    async def compare_offers(db: Session, item_name: str, qty: float = 1.0) -> Dict[str, Any]:
        item = inventory_service.get_item_by_name(db, item_name)
        spec = ItemSpec(**json.loads(item.spec_json)) if item else ItemSpec()
        all_offers, _ = await router_aggregator.query_all_merchants(item_name, spec, qty)
        offers_data = [o.model_dump() for o in all_offers]
        return {
            "item_name": item_name,
            "offers": offers_data,
            "card": CardPayload(
                card_type="order_preview",
                title=f"Marketplace Comparison: {item_name}",
                subtitle=f"Found {len(all_offers)} merchant quotes",
                data={"offers": offers_data}
            ).model_dump()
        }

    @staticmethod
    def explain_decision(db: Session, order_id: str) -> Dict[str, Any]:
        order = db.query(OrderModel).filter(OrderModel.id == order_id).first()
        if not order:
            return {"error": f"Order '{order_id}' not found."}
        decision = db.query(DecisionModel).filter(DecisionModel.intent_id == order.intent_id).first()
        if not decision:
            return {"error": "No stored decision found."}
        return {
            "order_id": order_id,
            "merchant": order.merchant_name,
            "amount": order.amount,
            "explanation": decision.explanation,
            "card": CardPayload(
                card_type="decision_explanation",
                title="Transparent Decision Breakdown",
                subtitle=f"Order #{order.id} with {order.merchant_name}",
                data={"explanation": decision.explanation}
            ).model_dump()
        }

agent_tool_handler = AgentToolHandler()
