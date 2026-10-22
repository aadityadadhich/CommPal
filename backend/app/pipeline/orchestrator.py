import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.app.contracts.items import ItemSpec
from backend.app.contracts.orders import OrderIntentCreate, Order, Decision, Offer, OrderState
from backend.app.contracts.mandate import MandateBody, Verdict
from backend.app.db.models import (
    OrderIntentModel, OfferModel, DecisionModel, VerdictModel, 
    ApprovalModel, OrderModel, MandateModel, ItemModel
)
from backend.app.router.aggregator import router_aggregator
from backend.app.mandate.evaluator import evaluate_mandate
from backend.app.wallet.ledger import ledger_service, InsufficientFundsError
from backend.app.wallet.paypal_provider import get_active_payment_provider
from backend.app.merchants.adapter import MERCHANTS
from backend.app.inventory.service import inventory_service
from backend.app.scheduler.virtual_clock import clock
from backend.app.audit.hash_chain import append_audit_event

class PurchasePipeline:
    @staticmethod
    def get_active_mandate(db: Session) -> Tuple[MandateBody, int]:
        m_row = db.query(MandateModel).filter(MandateModel.active == True).order_by(MandateModel.version.desc()).first()
        if m_row:
            body = MandateBody(**json.loads(m_row.body_json))
            return body, m_row.version
        # Default mandate
        default_mandate = MandateBody()
        return default_mandate, 1

    @staticmethod
    async def request_purchase(
        db: Session,
        intent_in: OrderIntentCreate,
        actor: str = "user"
    ) -> Dict[str, Any]:
        now = clock.now()
        mandate, mandate_version = PurchasePipeline.get_active_mandate(db)

        # 1. Resolve item and specifications
        item: Optional[ItemModel] = None
        if intent_in.item_id:
            item = inventory_service.get_item_by_id(db, intent_in.item_id)
        if not item:
            item = inventory_service.get_item_by_name(db, intent_in.item_name)

        if item:
            item_id = item.id
            item_name = item.name
            category = item.category
            perishable = item.perishable
            fulfilment_class = item.fulfilment_class
            spec_dict = json.loads(item.spec_json or "{}")
            spec = ItemSpec(**spec_dict)
            cur_stock, _, _, default_needed = inventory_service.calculate_stock_and_cover(item, now)
        else:
            item_id = None
            item_name = intent_in.item_name
            category = "general"
            perishable = False
            fulfilment_class = "any"
            spec = ItemSpec()
            cur_stock = 0.0
            default_needed = now + timedelta(hours=2)

        # Urgency override if hinted
        user_urgent = False
        if intent_in.urgency_hint and intent_in.urgency_hint.lower() in ["urgent", "high", "asap", "now", "empty", "zero"]:
            user_urgent = True
            needed_by = now + timedelta(hours=1)
        else:
            needed_by = default_needed

        # 2. Check in-flight orders for the same item (SCH-6 suppression)
        in_flight = db.query(OrderIntentModel).filter(
            OrderIntentModel.item_name == item_name,
            OrderIntentModel.state.in_(["PENDING_APPROVAL", "APPROVED", "AUTHORIZED", "PLACED", "CAPTURED", "IN_TRANSIT"])
        ).first()
        if in_flight and intent_in.source in ["rule", "depletion"]:
            return {
                "success": False,
                "status": "SUPPRESSED",
                "message": f"Order for '{item_name}' already in flight (intent {in_flight.id}, state: {in_flight.state})."
            }

        # 3. Create Intent row
        intent_id = f"int-{uuid.uuid4().hex[:8]}"
        idem_key = intent_in.idempotency_key or f"idem-{intent_id}"
        
        intent_row = OrderIntentModel(
            id=intent_id,
            item_id=item_id,
            item_name=item_name,
            qty=intent_in.qty,
            source=intent_in.source,
            rule_id=intent_in.rule_id,
            idempotency_key=idem_key,
            urgency_class="ROUTINE", # Will be updated by router
            needed_by=needed_by.isoformat(),
            state="QUOTED",
            created_at=now.isoformat()
        )
        db.add(intent_row)
        db.commit()

        # 4. Aggregator & Router: Query merchants & rank offers
        decision, all_offers, filtered_out = await router_aggregator.find_and_decide(
            intent_id=intent_id,
            query=item_name,
            qty=intent_in.qty,
            needed_by=needed_by,
            spec=spec,
            stock_qty=cur_stock,
            perishable=perishable,
            fulfilment_class=fulfilment_class,
            mandate=mandate,
            user_said_urgent=user_urgent
        )

        # Persist fetched offers
        for off in all_offers:
            off_row = OfferModel(
                id=off.id,
                intent_id=intent_id,
                merchant_id=off.merchant_id,
                merchant_name=off.merchant_name,
                sku=off.sku,
                title=off.title,
                brand=off.brand,
                size=off.size,
                unit_price=off.unit_price,
                delivery_fee=off.delivery_fee,
                landed_price=off.landed_price,
                currency=off.currency,
                stock_qty=off.stock_qty,
                eta_minutes=off.eta_minutes,
                rating=off.rating,
                reliability=off.reliability,
                fetched_at=off.fetched_at
            )
            db.add(off_row)
        db.commit()

        if not decision or not decision.chosen_offer:
            intent_row.state = "MERCHANT_FAILED"
            db.commit()
            append_audit_event(
                db=db,
                actor=actor,
                event_type="ORDER_NO_MERCHANT",
                entity_type="intent",
                entity_id=intent_id,
                payload={"item_name": item_name, "filtered_out": filtered_out},
                mandate_version=mandate_version
            )
            return {
                "success": False,
                "status": "MERCHANT_FAILED",
                "message": f"No merchant could fulfill '{item_name}' within delivery constraints.",
                "filtered_out": filtered_out
            }

        # Update intent urgency
        intent_row.urgency_class = decision.urgency_class
        intent_row.state = "DECIDED"
        db.commit()

        # Persist Decision
        dec_row = DecisionModel(
            id=decision.id,
            intent_id=intent_id,
            chosen_offer_id=decision.chosen_offer.id,
            runner_up_offer_id=decision.runner_up_offer.id if decision.runner_up_offer else None,
            weights_json=json.dumps(decision.weights),
            score_breakdown_json=json.dumps([b.model_dump() for b in decision.score_breakdown]),
            filtered_out_json=json.dumps(decision.filtered_out),
            explanation=decision.explanation,
            created_at=now.isoformat()
        )
        db.add(dec_row)
        db.commit()

        # 5. Evaluate Mandate
        wallet_summary = ledger_service.get_wallet_summary(
            db=db,
            daily_cap=mandate.limits.daily_cap,
            monthly_cap=mandate.limits.monthly_cap,
            kill_switch=mandate.kill_switch
        )

        chosen = decision.chosen_offer
        verdict = evaluate_mandate(
            intent_item_name=item_name,
            intent_item_id=item_id,
            intent_qty=intent_in.qty,
            intent_source=intent_in.source,
            chosen_merchant_id=chosen.merchant_id,
            landed_total=chosen.landed_price,
            unit_price=chosen.unit_price,
            category=category,
            wallet_summary=wallet_summary,
            mandate=mandate
        )

        # Persist Verdict
        verd_row = VerdictModel(
            id=str(uuid.uuid4()),
            intent_id=intent_id,
            mandate_version=mandate_version,
            result=verdict.result,
            reasons_json=json.dumps(verdict.reasons),
            rule_ids_json=json.dumps(verdict.rule_ids),
            created_at=now.isoformat()
        )
        db.add(verd_row)
        db.commit()

        append_audit_event(
            db=db,
            actor=actor,
            event_type=f"VERDICT_{verdict.result}",
            entity_type="intent",
            entity_id=intent_id,
            payload={
                "result": verdict.result,
                "reasons": verdict.reasons,
                "merchant": chosen.merchant_name,
                "amount": chosen.landed_price
            },
            mandate_version=mandate_version
        )

        # 6. Act on Verdict
        if verdict.result == "DENY":
            intent_row.state = "DENIED"
            db.commit()
            return {
                "success": False,
                "status": "DENIED",
                "verdict": verdict.model_dump(),
                "decision": decision.model_dump(),
                "message": f"Order denied by mandate: {'; '.join(verdict.reasons)}"
            }

        elif verdict.result == "NEEDS_APPROVAL":
            intent_row.state = "PENDING_APPROVAL"
            expiry_dt = now + timedelta(minutes=mandate.approval_expiry_minutes)
            app_row = ApprovalModel(
                id=str(uuid.uuid4()),
                intent_id=intent_id,
                status="PENDING",
                requested_at=now.isoformat(),
                expires_at=expiry_dt.isoformat()
            )
            db.add(app_row)
            db.commit()
            return {
                "success": True,
                "status": "PENDING_APPROVAL",
                "intent_id": intent_id,
                "verdict": verdict.model_dump(),
                "decision": decision.model_dump(),
                "expires_at": expiry_dt.isoformat(),
                "message": f"Order requires your approval: {'; '.join(verdict.reasons)}"
            }

        else: # ALLOW
            # Proceed directly to execution
            return await PurchasePipeline.execute_approved_order(
                db=db,
                intent_id=intent_id,
                actor=actor
            )

    @staticmethod
    async def execute_approved_order(
        db: Session,
        intent_id: str,
        actor: str = "user"
    ) -> Dict[str, Any]:
        now = clock.now()
        intent = db.query(OrderIntentModel).filter(OrderIntentModel.id == intent_id).first()
        if not intent:
            raise KeyError(f"Intent '{intent_id}' not found.")

        decision_row = db.query(DecisionModel).filter(DecisionModel.intent_id == intent_id).first()
        if not decision_row:
            raise RuntimeError(f"No decision found for intent '{intent_id}'.")

        chosen_offer = db.query(OfferModel).filter(OfferModel.id == decision_row.chosen_offer_id).first()
        if not chosen_offer:
            raise RuntimeError("Chosen offer not found in database.")

        mandate, mandate_version = PurchasePipeline.get_active_mandate(db)
        payment_provider = get_active_payment_provider()

        # Step A: TOCTOU Re-evaluation
        wallet_summary = ledger_service.get_wallet_summary(db)
        if mandate.kill_switch or wallet_summary.available_balance < chosen_offer.landed_price:
            intent.state = "DENIED"
            db.commit()
            return {"success": False, "status": "DENIED", "message": "Failed final balance or kill-switch check."}

        # Step B: Ledger Reserve
        intent.state = "APPROVED"
        db.commit()
        try:
            ledger_service.reserve(
                db=db,
                amount=chosen_offer.landed_price,
                currency=chosen_offer.currency,
                idem_key=f"res-{intent_id}",
                ref_id=intent_id
            )
        except InsufficientFundsError as e:
            intent.state = "DENIED"
            db.commit()
            return {"success": False, "status": "DENIED", "message": str(e)}

        # Step C: PayPal Authorize
        try:
            auth_result = await payment_provider.authorize(
                amount=chosen_offer.landed_price,
                currency=chosen_offer.currency,
                ref=intent_id,
                idem_key=f"auth-{intent_id}"
            )
        except Exception as e:
            # Void / release hold on payment failure
            ledger_service.release(
                db=db,
                amount=chosen_offer.landed_price,
                currency=chosen_offer.currency,
                idem_key=f"rel-authfail-{intent_id}",
                ref_id=intent_id
            )
            intent.state = "PAYMENT_FAILED"
            db.commit()
            append_audit_event(
                db=db,
                actor=actor,
                event_type="PAYMENT_AUTH_FAILED",
                entity_type="intent",
                entity_id=intent_id,
                payload={"error": str(e), "amount": chosen_offer.landed_price},
                mandate_version=mandate_version
            )
            return {"success": False, "status": "PAYMENT_FAILED", "message": f"PayPal authorization failed: {str(e)}"}

        intent.state = "AUTHORIZED"
        db.commit()

        # Step D: Place Merchant Order
        adapter = MERCHANTS.get(chosen_offer.merchant_id)
        if not adapter:
            # Compensation: void PayPal auth and release ledger hold
            await payment_provider.void(auth_result.auth_id, f"void-{intent_id}")
            ledger_service.release(db, chosen_offer.landed_price, chosen_offer.currency, f"rel-noadapter-{intent_id}", intent_id)
            intent.state = "MERCHANT_FAILED"
            db.commit()
            return {"success": False, "status": "MERCHANT_FAILED", "message": "Merchant adapter unavailable."}

        try:
            merchant_offer_obj = Offer(
                id=chosen_offer.id,
                intent_id=intent_id,
                merchant_id=chosen_offer.merchant_id,
                merchant_name=chosen_offer.merchant_name,
                sku=chosen_offer.sku,
                title=chosen_offer.title,
                brand=chosen_offer.brand,
                size=chosen_offer.size,
                unit_price=chosen_offer.unit_price,
                delivery_fee=chosen_offer.delivery_fee,
                landed_price=chosen_offer.landed_price,
                currency=chosen_offer.currency,
                stock_qty=chosen_offer.stock_qty,
                eta_minutes=chosen_offer.eta_minutes,
                rating=chosen_offer.rating,
                reliability=chosen_offer.reliability,
                fetched_at=chosen_offer.fetched_at
            )
            merchant_order = await adapter.place_order(
                offer=merchant_offer_obj,
                qty=intent.qty,
                idem_key=f"mord-{intent_id}"
            )
        except Exception as e:
            # Compensation: void PayPal auth and release ledger hold
            await payment_provider.void(auth_result.auth_id, f"void-{intent_id}")
            ledger_service.release(db, chosen_offer.landed_price, chosen_offer.currency, f"rel-mfail-{intent_id}", intent_id)
            intent.state = "MERCHANT_FAILED"
            db.commit()
            append_audit_event(
                db=db,
                actor=actor,
                event_type="MERCHANT_ORDER_FAILED",
                entity_type="intent",
                entity_id=intent_id,
                payload={"error": str(e), "merchant": chosen_offer.merchant_name},
                mandate_version=mandate_version
            )
            return {"success": False, "status": "MERCHANT_FAILED", "message": f"Merchant order failed: {str(e)}"}

        intent.state = "PLACED"
        db.commit()

        # Step E: PayPal Capture
        try:
            capture_result = await payment_provider.capture(
                auth_id=auth_result.auth_id,
                idem_key=f"cap-{intent_id}"
            )
        except Exception as e:
            # Void / compensate
            intent.state = "PAYMENT_FAILED"
            db.commit()
            return {"success": False, "status": "PAYMENT_FAILED", "message": f"Capture failed: {str(e)}"}

        # Step F: Settle Ledger
        ledger_service.settle(
            db=db,
            amount=chosen_offer.landed_price,
            currency=chosen_offer.currency,
            idem_key=f"set-{intent_id}",
            ref_id=intent_id
        )

        # Step G: Create Order Record
        order_id = f"ord-{uuid.uuid4().hex[:8]}"
        order_row = OrderModel(
            id=order_id,
            intent_id=intent_id,
            merchant_id=chosen_offer.merchant_id,
            merchant_name=chosen_offer.merchant_name,
            item_name=intent.item_name,
            qty=intent.qty,
            merchant_order_ref=merchant_order.merchant_order_ref,
            amount=chosen_offer.landed_price,
            currency=chosen_offer.currency,
            paypal_auth_id=auth_result.auth_id,
            paypal_capture_id=capture_result.capture_id,
            state="IN_TRANSIT",
            eta_minutes=chosen_offer.eta_minutes,
            created_at=now.isoformat()
        )
        db.add(order_row)
        intent.state = "IN_TRANSIT"
        db.commit()

        # Step H: Audit Log Event
        append_audit_event(
            db=db,
            actor=actor,
            event_type="ORDER_FULFILLED",
            entity_type="order",
            entity_id=order_id,
            payload={
                "merchant": chosen_offer.merchant_name,
                "amount": chosen_offer.landed_price,
                "paypal_auth_id": auth_result.auth_id,
                "paypal_capture_id": capture_result.capture_id,
                "eta_minutes": chosen_offer.eta_minutes
            },
            mandate_version=mandate_version
        )

        return {
            "success": True,
            "status": "ORDER_PLACED",
            "order_id": order_id,
            "merchant": chosen_offer.merchant_name,
            "amount": chosen_offer.landed_price,
            "eta_minutes": chosen_offer.eta_minutes,
            "paypal_auth_id": auth_result.auth_id,
            "paypal_capture_id": capture_result.capture_id,
            "explanation": decision_row.explanation
        }

purchase_pipeline = PurchasePipeline()
