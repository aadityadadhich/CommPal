import os
import json
import uuid
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Query, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.database import get_db, SessionLocal, init_db
from backend.app.db.seed import seed_week_with_asha
from backend.app.db.models import (
    RuleModel,
    OrderModel,
    OrderIntentModel,
    DecisionModel,
    ApprovalModel,
    MandateModel,
    AuditLogModel,
)
from backend.app.contracts.schemas import (
    ItemCreate,
    StockUpdateRequest,
    ItemResponse,
    OrderIntentCreate,
    OrderApprovalAction,
    MandateBody,
    KillSwitchRequest,
    TopUpRequest,
    WalletSummary,
    ChatRequest,
    ChatMessage,
)
from backend.app.inventory.service import inventory_service
from backend.app.pipeline.orchestrator import purchase_pipeline
from backend.app.scheduler.virtual_clock import clock
from backend.app.scheduler.worker import tick_worker

from backend.app.wallet.ledger import ledger_service
from backend.app.wallet.services import (
    create_payment,
    cancel_payment,
    process_provider_event,
    verify_webhook_signature,
    IdempotencyConflict,
)
from backend.app.audit.hash_chain import verify_audit_chain, append_audit_event
from backend.app.agent.shopping_agent import shopping_agent
from backend.app.agent.gemini_client import ollama_client, gemini_client
from backend.app.merchants.catalogs import chaos_flags


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        has_mandate = db.query(MandateModel).first()
        if not has_mandate:
            seed_week_with_asha(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="CommPal API",
    description="Autonomous Agentic Commerce & Aggregation platform for PayPal AI Hackathon",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 1. Chat & Conversational Agent
@app.post("/api/chat", response_model=ChatMessage)
async def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    msg = await shopping_agent.process_chat(
        db=db,
        user_message=req.message,
        conversation_id=req.conversation_id or "default",
    )
    return msg


# 2. Inventory Endpoints
@app.get("/api/items", response_model=List[ItemResponse])
def get_items(db: Session = Depends(get_db)):
    return inventory_service.get_all_items(db)


@app.post("/api/items", response_model=Dict[str, Any])
def create_item(item_in: ItemCreate, db: Session = Depends(get_db)):
    item = inventory_service.create_item(db, item_in)
    # Create an optional depletion rule if threshold_days > 0
    rule_id = f"rule-depletion-{item.id}"
    existing_rule = db.query(RuleModel).filter(RuleModel.id == rule_id).first()
    if not existing_rule:
        db.add(
            RuleModel(
                id=rule_id,
                item_id=item.id,
                type="depletion",
                params_json=json.dumps({"threshold_days": item.threshold_days}),
                qty=item.reorder_qty,
                active=True,
                created_at=clock.now().isoformat(),
            )
        )
        db.commit()
    return {"success": True, "item_id": item.id, "name": item.name}


@app.post("/api/items/{item_id}/stock", response_model=Dict[str, Any])
async def update_item_stock(item_id: str, req: StockUpdateRequest, db: Session = Depends(get_db)):
    try:
        item = inventory_service.update_stock(db, item_id, req)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    cur_stock, doc, conf, _ = inventory_service.calculate_stock_and_cover(item, clock.now())
    triggered_order: Optional[Dict[str, Any]] = None

    # If stock dropped below or equal to threshold (or marked finished), automatically evaluate depletion purchase
    if req.mode == "finished" or cur_stock <= 0 or doc <= item.threshold_days:
        depletion_rule = (
            db.query(RuleModel)
            .filter(RuleModel.item_id == item.id, RuleModel.active == True)
            .first()
        )
        if depletion_rule or req.mode == "finished":
            intent_in = OrderIntentCreate(
                item_id=item.id,
                item_name=item.name,
                qty=item.reorder_qty,
                source="depletion",
                rule_id=depletion_rule.id if depletion_rule else None,
                urgency_hint="urgent" if cur_stock <= 0 else "routine",
            )
            triggered_order = await purchase_pipeline.request_purchase(db, intent_in, actor="depletion_monitor")

    return {
        "success": True,
        "item_id": item.id,
        "item_name": item.name,
        "stock_qty": cur_stock,
        "days_of_cover": doc,
        "stock_confidence": conf,
        "triggered_order": triggered_order,
    }


@app.post("/api/orders/purchase", response_model=Dict[str, Any])
async def direct_purchase_endpoint(intent_in: OrderIntentCreate, db: Session = Depends(get_db)):
    """Direct 1-click purchase proposal from the UI Inventory or Dashboard."""
    res = await purchase_pipeline.request_purchase(db, intent_in, actor="user")
    return res


# 3. Orders & Decisions (N+1 Query Eliminated)
@app.get("/api/orders", response_model=List[Dict[str, Any]])
def get_orders(db: Session = Depends(get_db)):
    orders = db.query(OrderModel).order_by(OrderModel.created_at.desc()).all()
    if not orders:
        return []

    intent_ids = [o.intent_id for o in orders]
    decisions = db.query(DecisionModel).filter(DecisionModel.intent_id.in_(intent_ids)).all()
    dec_map = {d.intent_id: d for d in decisions}

    results = []
    for ord_row in orders:
        dec_row = dec_map.get(ord_row.intent_id)
        results.append(
            {
                "id": ord_row.id,
                "intent_id": ord_row.intent_id,
                "merchant_id": ord_row.merchant_id,
                "merchant_name": ord_row.merchant_name,
                "item_name": ord_row.item_name,
                "qty": ord_row.qty,
                "merchant_order_ref": ord_row.merchant_order_ref,
                "amount": ord_row.amount,
                "currency": ord_row.currency,
                "paypal_auth_id": ord_row.paypal_auth_id,
                "paypal_capture_id": ord_row.paypal_capture_id,
                "state": ord_row.state,
                "eta_minutes": ord_row.eta_minutes,
                "created_at": ord_row.created_at,
                "delivered_at": ord_row.delivered_at,
                "explanation": dec_row.explanation if dec_row else "Automated rule fulfillment.",
            }
        )
    return results


@app.get("/api/orders/{order_id}")
def get_order_detail(order_id: str, db: Session = Depends(get_db)):
    ord_row = db.query(OrderModel).filter(OrderModel.id == order_id).first()
    if not ord_row:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found.")
    dec_row = db.query(DecisionModel).filter(DecisionModel.intent_id == ord_row.intent_id).first()
    return {
        "order": {
            "id": ord_row.id,
            "merchant_name": ord_row.merchant_name,
            "item_name": ord_row.item_name,
            "qty": ord_row.qty,
            "merchant_order_ref": ord_row.merchant_order_ref,
            "amount": ord_row.amount,
            "currency": ord_row.currency,
            "state": ord_row.state,
            "eta_minutes": ord_row.eta_minutes,
            "paypal_auth_id": ord_row.paypal_auth_id,
            "paypal_capture_id": ord_row.paypal_capture_id,
            "created_at": ord_row.created_at,
            "delivered_at": ord_row.delivered_at,
        },
        "decision": {
            "explanation": dec_row.explanation if dec_row else None,
            "weights": json.loads(dec_row.weights_json) if dec_row and dec_row.weights_json else {},
            "score_breakdown": json.loads(dec_row.score_breakdown_json) if dec_row else [],
            "filtered_out": json.loads(dec_row.filtered_out_json) if dec_row else {},
        },
    }


# 4. Approvals (N+1 Query Eliminated)
@app.get("/api/approvals")
def get_pending_approvals(db: Session = Depends(get_db)):
    apps = db.query(ApprovalModel).filter(ApprovalModel.status == "PENDING").all()
    if not apps:
        return []

    intent_ids = [a.intent_id for a in apps]
    intents = db.query(OrderIntentModel).filter(OrderIntentModel.id.in_(intent_ids)).all()
    decisions = db.query(DecisionModel).filter(DecisionModel.intent_id.in_(intent_ids)).all()
    intent_map = {i.id: i for i in intents}
    dec_map = {d.intent_id: d for d in decisions}

    results = []
    for a in apps:
        intent = intent_map.get(a.intent_id)
        dec = dec_map.get(a.intent_id)
        results.append(
            {
                "approval_id": a.id,
                "intent_id": a.intent_id,
                "item_name": intent.item_name if intent else "Unknown",
                "qty": intent.qty if intent else 1.0,
                "requested_at": a.requested_at,
                "expires_at": a.expires_at,
                "explanation": dec.explanation if dec else "",
            }
        )
    return results


@app.post("/api/orders/{intent_id}/action")
async def handle_order_approval(intent_id: str, act: OrderApprovalAction, db: Session = Depends(get_db)):
    approval = db.query(ApprovalModel).filter(ApprovalModel.intent_id == intent_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="No approval found for intent.")

    if act.action == "approve":
        approval.status = "APPROVED"
        approval.decided_by = "User (UI Authenticated)"
        approval.decided_at = clock.now().isoformat()
        db.commit()

        res = await purchase_pipeline.execute_approved_order(db, intent_id, actor="user")
        return res
    else:
        approval.status = "REJECTED"
        approval.decided_by = "User (UI Authenticated)"
        approval.decided_at = clock.now().isoformat()
        intent = db.query(OrderIntentModel).filter(OrderIntentModel.id == intent_id).first()
        if intent:
            intent.state = "REJECTED"
        db.commit()
        append_audit_event(
            db=db,
            actor="user",
            event_type="ORDER_REJECTED",
            entity_type="intent",
            entity_id=intent_id,
            payload={"reason": act.reason or "User rejected approval request"},
        )
        return {"success": True, "status": "REJECTED"}


# 5. Wallet & Payments
@app.get("/api/wallet", response_model=WalletSummary)
def get_wallet(db: Session = Depends(get_db)):
    mandate, _ = purchase_pipeline.get_active_mandate(db)
    return ledger_service.get_wallet_summary(
        db=db,
        daily_cap=mandate.limits.daily_cap,
        monthly_cap=mandate.limits.monthly_cap,
        kill_switch=mandate.kill_switch,
    )


@app.post("/api/wallet/top-up")
def wallet_top_up(req: TopUpRequest, db: Session = Depends(get_db)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Top-up amount must be positive.")
    entry = ledger_service.top_up(db, req.amount, req.currency)
    append_audit_event(
        db=db,
        actor="user",
        event_type="WALLET_TOP_UP",
        entity_type="wallet",
        entity_id=entry.id,
        payload={"amount": req.amount, "currency": req.currency, "method": req.payment_method},
    )
    mandate, _ = purchase_pipeline.get_active_mandate(db)
    summary = ledger_service.get_wallet_summary(
        db=db,
        daily_cap=mandate.limits.daily_cap,
        monthly_cap=mandate.limits.monthly_cap,
        kill_switch=mandate.kill_switch,
    )
    return {"success": True, "top_up_amount": req.amount, "wallet": summary}


@app.post("/api/payments")
def create_payment_endpoint(payload: Dict[str, Any], db: Session = Depends(get_db)):
    amount = float(payload.get("amount", 0.0))
    currency = payload.get("currency", "USD")
    user_id = payload.get("user_id", "default_user")
    desc = payload.get("description", "")
    idem_key = payload.get("idempotency_key")
    try:
        payment, created = create_payment(db, amount, currency, user_id, desc, idem_key)
        return {
            "id": payment.id,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
            "is_new": created,
        }
    except IdempotencyConflict as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/payments/{payment_id}/cancel")
def cancel_payment_endpoint(payment_id: str, db: Session = Depends(get_db)):
    try:
        payment = cancel_payment(db, payment_id)
        return {"id": payment.id, "status": payment.status}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/webhooks/paypal")
async def paypal_webhook_endpoint(
    request: Request,
    paypal_transmission_sig: Optional[str] = Header(None, alias="PayPal-Transmission-Sig"),
    db: Session = Depends(get_db),
):
    body_bytes = await request.body()
    if paypal_transmission_sig:
        valid = verify_webhook_signature(body_bytes, paypal_transmission_sig)
        if not valid:
            raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    processed = process_provider_event(db, "paypal_sandbox", data)
    return {"received": True, "processed": processed}


# 6. Mandate & Security Policy
@app.get("/api/mandate")
def get_mandate(db: Session = Depends(get_db)):
    mandate, version = purchase_pipeline.get_active_mandate(db)
    return {
        "version": version,
        "mandate": mandate.model_dump(),
    }


@app.put("/api/mandate")
def update_mandate(new_body: MandateBody, db: Session = Depends(get_db)):
    _, version = purchase_pipeline.get_active_mandate(db)
    new_version = version + 1
    new_body.version = new_version

    db.query(MandateModel).update({"active": False})

    m_row = MandateModel(
        id=str(uuid.uuid4()),
        version=new_version,
        body_json=new_body.model_dump_json(),
        created_by="User (Authenticated UI)",
        created_at=clock.now().isoformat(),
        active=True,
    )
    db.add(m_row)
    db.commit()

    append_audit_event(
        db=db,
        actor="user",
        event_type="MANDATE_UPDATED",
        entity_type="mandate",
        entity_id=str(new_version),
        payload={"version": new_version, "limits": new_body.limits.model_dump()},
        mandate_version=new_version,
    )
    return {"success": True, "version": new_version, "mandate": new_body.model_dump()}


@app.post("/api/mandate/kill-switch")
def toggle_kill_switch(req: KillSwitchRequest, db: Session = Depends(get_db)):
    mandate, version = purchase_pipeline.get_active_mandate(db)
    mandate.kill_switch = req.active

    db.query(MandateModel).filter(MandateModel.active == True).update(
        {"body_json": mandate.model_dump_json()}
    )
    db.commit()

    append_audit_event(
        db=db,
        actor="user",
        event_type="KILL_SWITCH_TOGGLED",
        entity_type="mandate",
        entity_id=str(version),
        payload={"active": req.active, "reason": req.reason},
        mandate_version=version,
    )
    return {"success": True, "kill_switch": req.active}


# 7. Audit Trail & Hash Chain Verification
@app.get("/api/audit")
def get_audit_trail(limit: int = 100, db: Session = Depends(get_db)):
    entries = db.query(AuditLogModel).order_by(AuditLogModel.seq.desc()).limit(limit).all()
    return [
        {
            "seq": e.seq,
            "id": e.id,
            "ts": e.ts,
            "actor": e.actor,
            "event_type": e.event_type,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "payload": json.loads(e.payload_json),
            "mandate_version": e.mandate_version,
            "prev_hash": e.prev_hash,
            "hash": e.hash,
        }
        for e in entries
    ]


@app.get("/api/audit/verify")
def verify_audit(db: Session = Depends(get_db)):
    is_valid, msg, count = verify_audit_chain(db)
    return {
        "is_valid": is_valid,
        "message": msg,
        "events_count": count,
    }


# 8. Demo Studio & Virtual Time-Travel
@app.get("/api/demo/clock")
def get_clock():
    return clock.to_dict()


@app.post("/api/demo/clock/advance")
async def advance_clock(
    hours: int = Query(0),
    days: int = Query(0),
    minutes: int = Query(0),
    db: Session = Depends(get_db),
):
    clock.advance(hours=hours, days=days, minutes=minutes)
    tick_res = await tick_worker.run_tick(db)
    return {
        "clock": clock.to_dict(),
        "tick_result": tick_res,
    }


@app.post("/api/demo/reset")
def reset_demo_scenario(db: Session = Depends(get_db)):
    seed_week_with_asha(db)
    return {"success": True, "scenario": "Week with Asha", "clock": clock.to_dict()}


@app.get("/api/demo/chaos")
def get_chaos():
    return {
        "out_of_stock_items": list(chaos_flags["out_of_stock_items"]),
        "price_spikes": chaos_flags["price_spikes"],
        "down_merchants": list(chaos_flags["down_merchants"]),
        "slow_merchants": list(chaos_flags["slow_merchants"]),
        "payment_failure": chaos_flags["payment_failure"],
    }


@app.post("/api/demo/chaos")
def toggle_chaos(body: Dict[str, Any]):
    if "out_of_stock_item" in body:
        item = body["out_of_stock_item"]
        if item in chaos_flags["out_of_stock_items"]:
            chaos_flags["out_of_stock_items"].remove(item)
        else:
            chaos_flags["out_of_stock_items"].add(item)

    if "down_merchant" in body:
        m = body["down_merchant"]
        if m in chaos_flags["down_merchants"]:
            chaos_flags["down_merchants"].remove(m)
        else:
            chaos_flags["down_merchants"].add(m)

    if "payment_failure" in body:
        chaos_flags["payment_failure"] = bool(body["payment_failure"])

    return {"success": True, "chaos": get_chaos()}


# 9. Health Check
@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.query(MandateModel).first()
    except Exception:
        db_ok = False

    ollama_ok = ollama_client.is_available()
    gemini_ok = gemini_client.is_available()

    return {
        "status": "HEALTHY" if db_ok else "UNHEALTHY",
        "database": "CONNECTED" if db_ok else "ERROR",
        "paypal_mode": settings.PAYPAL_MODE,
        "paypal_configured": bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET),
        "llm_provider": settings.LLM_PROVIDER,
        "ollama_active": ollama_ok,
        "ollama_model": settings.OLLAMA_MODEL,
        "llm_gemini_active": gemini_ok or ollama_ok,
        "virtual_time": clock.now().isoformat(),
    }


# 10. Internal Tick Endpoint
@app.post("/internal/tick")
async def internal_tick(db: Session = Depends(get_db)):
    res = await tick_worker.run_tick(db)
    return res


# 11. Live .env Configuration Endpoints
@app.get("/api/config/env")
def get_env_config():
    return {
        "PAYPAL_MODE": settings.PAYPAL_MODE,
        "PAYPAL_CLIENT_ID": settings.PAYPAL_CLIENT_ID or "",
        "PAYPAL_CLIENT_SECRET": settings.PAYPAL_CLIENT_SECRET or "",
        "PAYPAL_WEBHOOK_ID": settings.PAYPAL_WEBHOOK_ID or "",
        "LLM_PROVIDER": settings.LLM_PROVIDER,
        "OLLAMA_BASE_URL": settings.OLLAMA_BASE_URL,
        "OLLAMA_MODEL": settings.OLLAMA_MODEL,
        "GEMINI_API_KEY": settings.GEMINI_API_KEY or "",
        "CHANNEL3_API_KEY": settings.CHANNEL3_API_KEY or "",
    }


@app.post("/api/config/env")
def update_env_config(body: Dict[str, Any]):
    allowed_keys = [
        "PAYPAL_MODE",
        "PAYPAL_CLIENT_ID",
        "PAYPAL_CLIENT_SECRET",
        "PAYPAL_WEBHOOK_ID",
        "LLM_PROVIDER",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "GEMINI_API_KEY",
        "CHANNEL3_API_KEY",
    ]
    for key in allowed_keys:
        if key in body and body[key] is not None:
            val = str(body[key]).strip()
            setattr(settings, key, val if val != "" else None)

    env_lines = [
        "# ============================================================================",
        "# CommPal — Root Environment & API Keys Configuration (.env)",
        "# ============================================================================",
        f"PROJECT_NAME={settings.PROJECT_NAME}",
        f"DATABASE_URL={settings.DATABASE_URL}",
        "",
        "# 1. PayPal REST API v2 Credentials",
        f"PAYPAL_MODE={settings.PAYPAL_MODE or 'mock'}",
        f"PAYPAL_CLIENT_ID={settings.PAYPAL_CLIENT_ID or ''}",
        f"PAYPAL_CLIENT_SECRET={settings.PAYPAL_CLIENT_SECRET or ''}",
        f"PAYPAL_WEBHOOK_ID={settings.PAYPAL_WEBHOOK_ID or ''}",
        f"PAYPAL_API_BASE={settings.PAYPAL_API_BASE}",
        "",
        "# 2. Conversational AI / LLM Configuration",
        f"LLM_PROVIDER={settings.LLM_PROVIDER or 'ollama'}",
        f"OLLAMA_BASE_URL={settings.OLLAMA_BASE_URL or 'http://127.0.0.1:11434'}",
        f"OLLAMA_MODEL={settings.OLLAMA_MODEL or 'qwen2.5:7b'}",
        f"GEMINI_API_KEY={settings.GEMINI_API_KEY or ''}",
        f"GEMINI_MODEL={settings.GEMINI_MODEL or 'gemini-2.5-flash'}",
        "",
        "# 3. Optional: Channel3 Live Product Search SDK",
        f"CHANNEL3_API_KEY={settings.CHANNEL3_API_KEY or ''}",
        "",
        "# 4. Security & Internal Signing",
        f"SECRET_KEY={settings.SECRET_KEY}",
        f"INTERNAL_TICK_TOKEN={settings.INTERNAL_TICK_TOKEN}",
        "",
    ]
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(env_lines))

    return {"success": True, "config": get_env_config()}


# 12. Serve Pure HTML/CSS/JS Frontend on Root (http://127.0.0.1:8000/)
WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "web"))
if os.path.isdir(WEB_DIR):
    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

