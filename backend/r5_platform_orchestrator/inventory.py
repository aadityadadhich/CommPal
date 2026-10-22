import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

from backend.r5_platform_orchestrator.models import ItemModel, StockEventModel, RuleModel
from backend.r5_platform_orchestrator.contracts import ItemCreate, ItemUpdate, StockUpdateRequest, ItemResponse, ItemSpec
from backend.r5_platform_orchestrator.clock import clock
from backend.r2_policy_security_audit.hash_chain import append_audit_event

class InventoryService:
    @staticmethod
    def calculate_stock_and_cover(item: ItemModel, current_time: Optional[datetime] = None) -> Tuple[float, float, float, datetime]:
        if not current_time:
            current_time = clock.now()

        try:
            last_dt = datetime.fromisoformat(item.last_confirmed_at)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
        except Exception:
            last_dt = current_time

        days_passed = max(0.0, (current_time - last_dt).total_seconds() / 86400.0)
        stock_now = max(0.0, round(item.stock_qty - (item.rate_per_day * days_passed), 2))
        
        rate = max(0.001, item.rate_per_day)
        days_of_cover = round(stock_now / rate, 1)

        # Confidence decay: decays from 1.0 to 0.3 over 2 * (initial cover days)
        initial_cover = max(1.0, item.stock_qty / rate)
        decay_window = 2.0 * initial_cover
        decay_factor = min(1.0, days_passed / decay_window)
        confidence = max(0.3, round(1.0 - (0.7 * decay_factor), 2))

        # needed_by calculation
        if stock_now <= 0:
            needed_by = current_time + timedelta(hours=1)
        else:
            runout_days = max(0.1, days_of_cover - item.safety_days)
            needed_by = current_time + timedelta(days=runout_days)

        return stock_now, days_of_cover, confidence, needed_by

    @staticmethod
    def get_all_items(db: Session) -> List[ItemResponse]:
        items = db.query(ItemModel).all()
        now = clock.now()
        results = []
        for it in items:
            cur_stock, doc, conf, needed_by = InventoryService.calculate_stock_and_cover(it, now)
            spec_dict = json.loads(it.spec_json or "{}")
            rules_count = db.query(RuleModel).filter(RuleModel.item_id == it.id, RuleModel.active == True).count()
            
            results.append(ItemResponse(
                id=it.id,
                name=it.name,
                unit=it.unit,
                category=it.category,
                perishable=it.perishable,
                fulfilment_class=it.fulfilment_class,
                spec=ItemSpec(**spec_dict),
                reorder_qty=it.reorder_qty,
                threshold_days=it.threshold_days,
                safety_days=it.safety_days,
                rate_per_day=it.rate_per_day,
                rate_source=it.rate_source,
                stock_qty=cur_stock,
                stock_confidence=conf,
                days_of_cover=doc,
                needed_by=needed_by.isoformat(),
                last_confirmed_at=it.last_confirmed_at,
                created_at=it.created_at,
                active_rules_count=rules_count
            ))
        return results

    @staticmethod
    def get_item_by_name(db: Session, name: str) -> Optional[ItemModel]:
        return db.query(ItemModel).filter(ItemModel.name.ilike(f"%{name.strip()}%")).first()

    @staticmethod
    def get_item_by_id(db: Session, item_id: str) -> Optional[ItemModel]:
        return db.query(ItemModel).filter(ItemModel.id == item_id).first()

    @staticmethod
    def create_item(db: Session, item_in: ItemCreate, actor: str = "user") -> ItemModel:
        now_str = clock.now().isoformat()
        item_id = f"item-{uuid.uuid4().hex[:8]}"
        item = ItemModel(
            id=item_id,
            name=item_in.name,
            unit=item_in.unit,
            category=item_in.category,
            perishable=item_in.perishable,
            fulfilment_class=item_in.fulfilment_class,
            spec_json=item_in.spec.model_dump_json(),
            reorder_qty=item_in.reorder_qty,
            threshold_days=item_in.threshold_days,
            safety_days=item_in.safety_days,
            rate_per_day=item_in.rate_per_day,
            rate_source=item_in.rate_source,
            stock_qty=item_in.stock_qty,
            stock_confidence=item_in.stock_confidence,
            last_confirmed_at=now_str,
            created_at=now_str
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        append_audit_event(
            db=db,
            actor=actor,
            event_type="ITEM_CREATED",
            entity_type="item",
            entity_id=item.id,
            payload={"name": item.name, "stock_qty": item.stock_qty, "category": item.category}
        )
        return item

    @staticmethod
    def update_stock(
        db: Session,
        item_id: str,
        update_req: StockUpdateRequest,
        actor: str = "user"
    ) -> ItemModel:
        item = db.query(ItemModel).filter(ItemModel.id == item_id).first()
        if not item:
            raise KeyError(f"Item id '{item_id}' not found.")

        now = clock.now()
        cur_stock, _, _, _ = InventoryService.calculate_stock_and_cover(item, now)

        if update_req.mode == "finished":
            new_stock = 0.0
            delta = -cur_stock
        elif update_req.mode == "delta":
            delta = update_req.qty or 0.0
            new_stock = max(0.0, cur_stock + delta)
        else: # absolute
            new_stock = max(0.0, update_req.qty or 0.0)
            delta = new_stock - cur_stock

        item.stock_qty = new_stock
        item.stock_confidence = 1.0  # Confirmed by user or delivery
        item.last_confirmed_at = now.isoformat()

        stock_event = StockEventModel(
            id=str(uuid.uuid4()),
            item_id=item.id,
            delta=delta,
            reason=update_req.reason,
            source=actor,
            created_at=now.isoformat()
        )
        db.add(stock_event)
        db.commit()
        db.refresh(item)

        append_audit_event(
            db=db,
            actor=actor,
            event_type="STOCK_UPDATED",
            entity_type="item",
            entity_id=item.id,
            payload={
                "item_name": item.name,
                "delta": delta,
                "new_stock": new_stock,
                "reason": update_req.reason
            }
        )
        return item

inventory_service = InventoryService()
