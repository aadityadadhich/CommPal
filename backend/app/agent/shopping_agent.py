import re
import uuid
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.agent.gemini_client import gemini_client
from backend.app.agent.tools import agent_tool_handler
from backend.app.contracts.chat import ChatMessage, CardPayload
from backend.app.db.models import ItemModel, OrderModel
from backend.app.scheduler.virtual_clock import clock

KNOWN_CATALOG_ITEMS: List[Tuple[List[str], str]] = [
    (["milk", "whole milk", "dairy"], "Whole Milk 1L"),
    (["protein", "whey", "protein powder"], "Whey Protein Powder 1kg"),
    (["a4 paper", "copy paper", "printer paper", "paper", "ream"], "A4 Copy Paper 500ct"),
    (["wd-40", "wd40", "lubricant", "spray"], "WD-40 Multi-Use 300ml"),
    (["eggs", "egg", "brown eggs"], "Eggs 12ct"),
    (["coffee", "ground coffee", "espresso"], "Coffee 500g"),
    (["bread", "sourdough", "loaf"], "Bread 500g"),
    (["batteries", "battery", "aa batteries"], "AA Batteries 8-Pack"),
    (["detergent", "laundry", "tide"], "Laundry Detergent 2L"),
]


def _extract_qty(text: str, default: float = 1.0) -> float:
    m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:x|bottles?|tubs?|reams?|packs?|cans?|units?|boxes?|loaves|ct)?\b", text)
    if m:
        val = float(m.group(1))
        if 0 < val <= 100 and str(int(val)) not in ["40", "10", "1", "4"]:  # avoid matching A4, WD-40, 1L
            return val
    m_explicit = re.search(r"(?:order|buy|get|need|add)\s+(\d+(?:\.\d+)?)\b", text)
    if m_explicit:
        return max(1.0, float(m_explicit.group(1)))
    return default


def _resolve_item_from_text(db: Session, text_lower: str) -> Optional[str]:
    # 1. Check tracked items in DB first
    db_items = db.query(ItemModel).all()
    for it in db_items:
        it_low = it.name.lower()
        if it_low in text_lower or any(tok in text_lower for tok in it_low.split() if len(tok) > 3):
            return it.name

    # 2. Check known merchant catalog items
    for keywords, canonical_name in KNOWN_CATALOG_ITEMS:
        if any(k in text_lower for k in keywords):
            return canonical_name

    return None


class ShoppingAgent:
    @staticmethod
    async def process_chat(
        db: Session,
        user_message: str,
        conversation_id: str = "default",
        history: Optional[List[Dict[str, str]]] = None,
    ) -> ChatMessage:
        user_lower = user_message.strip().lower()
        cards: List[CardPayload] = []
        assistant_reply = ""

        # 0. Greetings / Help / Capabilities
        if user_lower in ["hi", "hello", "hey", "help", "start", "what can you do", "what can you do?"]:
            summary = agent_tool_handler.get_wallet_summary(db)
            items_res = agent_tool_handler.list_items(db)["items"]
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=(
                    f"Hello! I'm **CommPal**, your autonomous purchasing & inventory agent.\n\n"
                    f"**Current Status:**\n"
                    f"• **Sandboxed Wallet:** `${summary['available_balance']:.2f}` available (`${summary['daily_spent']:.2f} / ${summary['daily_cap']:.2f}` daily cap used)\n"
                    f"• **Tracked Inventory:** {len(items_res)} items ({', '.join(i['name'] for i in items_res[:4])})\n\n"
                    f"**Commands you can run right now:**\n"
                    f"• *\"I need milk daily, protein powder monthly, and reorder A4 paper when it runs out\"*\n"
                    f"• *\"We're out of A4 paper\"* (triggers urgent quick-commerce fulfillment)\n"
                    f"• *\"Order WD-40\"* or *\"Order coffee\"* (demonstrates mandate approval & multi-merchant routing)\n"
                    f"• *\"Compare prices for whole milk\"* or *\"Show my inventory\"*"
                ),
                cards=[],
                timestamp=clock.now().isoformat(),
            )

        # S1: Multi-rule or single-rule setup
        if any(w in user_lower for w in ["daily", "weekly", "monthly", "every day", "every month", "when it runs out", "depletion", "schedule"]):
            rules_created = []
            if "milk" in user_lower and any(w in user_lower for w in ["daily", "every day"]):
                r1 = agent_tool_handler.create_rule(db, "Whole Milk 1L", "daily", 1.0)
                cards.append(CardPayload(**r1["card"]))
                rules_created.append("Daily Whole Milk 1L")

            if "protein" in user_lower and any(w in user_lower for w in ["monthly", "every month", "month"]):
                r2 = agent_tool_handler.create_rule(db, "Whey Protein Powder 1kg", "monthly", 1.0)
                cards.append(CardPayload(**r2["card"]))
                rules_created.append("Monthly Whey Protein Powder 1kg")

            if "paper" in user_lower and any(p in user_lower for p in ["finished", "runs out", "depletion", "empty", "low"]):
                r3 = agent_tool_handler.create_rule(db, "A4 Copy Paper 500ct", "depletion", 1.0)
                cards.append(CardPayload(**r3["card"]))
                rules_created.append("Depletion-triggered A4 Copy Paper 500ct")

            # Generic single-item rule if not matched above
            if not rules_created:
                target_item = _resolve_item_from_text(db, user_lower)
                if target_item:
                    r_type = (
                        "daily"
                        if "daily" in user_lower or "every day" in user_lower
                        else "weekly"
                        if "weekly" in user_lower
                        else "monthly"
                        if "monthly" in user_lower or "every month" in user_lower
                        else "depletion"
                    )
                    qty = _extract_qty(user_lower, 1.0)
                    r_gen = agent_tool_handler.create_rule(db, target_item, r_type, qty)
                    cards.append(CardPayload(**r_gen["card"]))
                    rules_created.append(f"{r_type.capitalize()} {target_item}")

            if rules_created:
                assistant_reply = (
                    f"Configured autonomous purchasing rules: **{', '.join(rules_created)}**. "
                    "Every scheduled execution is verified against your active spending mandate before settlement."
                )
                return ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=assistant_reply,
                    cards=cards,
                    timestamp=clock.now().isoformat(),
                )

        # S2: Price comparison across merchants
        if any(w in user_lower for w in ["compare", "prices", "cheapest", "quotes", "offers for"]):
            target_item = _resolve_item_from_text(db, user_lower) or "Whole Milk 1L"
            qty = _extract_qty(user_lower, 1.0)
            res = await agent_tool_handler.compare_offers(db, target_item, qty=qty)
            if "card" in res:
                cards.append(CardPayload(**res["card"]))
            offers = res.get("offers", [])
            if offers:
                fastest = min(offers, key=lambda x: x["eta_minutes"])
                cheapest = min(offers, key=lambda x: x["landed_price"])
                assistant_reply = (
                    f"Compared **{len(offers)} live merchant offers** for **{target_item}** (Qty: {qty:g}):\n"
                    f"• **Lowest Landed Cost:** {cheapest['merchant_name']} at `${cheapest['landed_price']:.2f}` (ETA: {cheapest['eta_minutes']}m)\n"
                    f"• **Fastest Delivery:** {fastest['merchant_name']} at `${fastest['landed_price']:.2f}` (ETA: {fastest['eta_minutes']}m)"
                )
            else:
                assistant_reply = f"No current offers found for '{target_item}'."
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=cards,
                timestamp=clock.now().isoformat(),
            )

        # S3: Inventory / Stock inspection
        if any(w in user_lower for w in ["inventory", "what do we have", "stock level", "show items", "list items", "days of cover"]):
            items_res = agent_tool_handler.list_items(db)["items"]
            lines = [
                f"• **{it['name']}**: `{it['stock_qty']} {it['unit']}` ({it['days_of_cover']}d cover, {int(it['stock_confidence']*100)}% confidence)"
                for it in items_res
            ]
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Current Tracked Inventory:\n" + "\n".join(lines),
                cards=[],
                timestamp=clock.now().isoformat(),
            )

        # S4: Wallet / Budget / Mandate inspection
        if any(w in user_lower for w in ["wallet", "balance", "money", "budget", "cap", "spent", "mandate"]):
            summary = agent_tool_handler.get_wallet_summary(db)
            assistant_reply = (
                f"**Sandboxed PayPal E-Wallet Summary:**\n"
                f"• **Available Balance:** `${summary['available_balance']:.2f}`\n"
                f"• **Held in Escrow:** `${summary['held_balance']:.2f}`\n"
                f"• **Total Settled Spend:** `${summary['spent_balance']:.2f}`\n"
                f"• **Daily Mandate Cap:** `${summary['daily_spent']:.2f} / ${summary['daily_cap']:.2f}`\n"
                f"• **Monthly Mandate Cap:** `${summary['monthly_spent']:.2f} / ${summary['monthly_cap']:.2f}`\n"
                f"• **Kill Switch:** `{'FROZEN' if summary['kill_switch'] else 'ACTIVE ( Armed )'}`"
            )
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=[],
                timestamp=clock.now().isoformat(),
            )

        # S5: Order history / Explanation query
        if any(w in user_lower for w in ["recent orders", "my orders", "order status", "why did you choose", "why did you pick"]):
            orders = db.query(OrderModel).order_by(OrderModel.created_at.desc()).limit(3).all()
            if not orders:
                return ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content="No orders have been placed yet. Try saying *\"We're out of A4 paper\"* or *\"Order milk now\"*.",
                    cards=[],
                    timestamp=clock.now().isoformat(),
                )
            latest = orders[0]
            exp = agent_tool_handler.explain_decision(db, latest.id)
            if "card" in exp:
                cards.append(CardPayload(**exp["card"]))
            lines = [
                f"• **#{o.id[-8:]}** — {o.item_name} via **{o.merchant_name}** (`${o.amount:.2f}`, {o.state}, PayPal Capture `{o.paypal_capture_id}`)"
                for o in orders
            ]
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Recent Autonomous Orders:\n" + "\n".join(lines),
                cards=cards,
                timestamp=clock.now().isoformat(),
            )

        # S6: Stockout / Depletion trigger ("we're out of X", "ran out of X", "X is empty/finished")
        if any(phrase in user_lower for phrase in ["out of", "ran out", "finished", "empty", "zero stock", "no more"]):
            target_item = _resolve_item_from_text(db, user_lower)
            if target_item:
                agent_tool_handler.set_stock(db, target_item, qty=0.0, mode="finished")
                res = await agent_tool_handler.request_purchase(
                    db, item_name=target_item, qty=1.0, urgency_hint="urgent"
                )
                for c in res.get("cards", []):
                    cards.append(CardPayload(**c))

                if res.get("status") == "ORDER_PLACED":
                    assistant_reply = (
                        f"Marked **{target_item}** as depleted (`0` stock → `URGENT` SLA).\n"
                        f"Evaluated 5 merchants, selected **{res.get('merchant')}** (ETA: `{res.get('eta_minutes')} mins`), "
                        f"and settled **`${res.get('amount', 0.0):.2f}`** via PayPal Sandbox (`{res.get('paypal_capture_id')}`)."
                    )
                else:
                    assistant_reply = res.get("message", f"Processed urgent restock proposal for {target_item}.")
                return ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=assistant_reply,
                    cards=cards,
                    timestamp=clock.now().isoformat(),
                )

        # S7: Direct purchase intent ("order X", "buy X", "get X", "need X", or mentioning a known catalog item)
        target_item = _resolve_item_from_text(db, user_lower)
        if target_item and any(
            w in user_lower
            for w in ["order", "buy", "get", "need", "purchase", "restock", "wd-40", "wd40", "milk", "paper", "protein", "eggs", "coffee", "bread", "batteries", "detergent"]
        ):
            qty = _extract_qty(user_lower, 1.0)
            is_urgent = any(w in user_lower for w in ["urgent", "now", "asap", "quick", "immediately", "fast"])
            urgency_hint = "urgent" if is_urgent else "routine"

            res = await agent_tool_handler.request_purchase(
                db, item_name=target_item, qty=qty, urgency_hint=urgency_hint
            )
            for c in res.get("cards", []):
                cards.append(CardPayload(**c))

            status = res.get("status")
            if status == "ORDER_PLACED":
                assistant_reply = (
                    f"Order placed for **{target_item}** (Qty: `{qty:g}`) with **{res.get('merchant')}** "
                    f"(ETA: `{res.get('eta_minutes')} mins`).\n"
                    f"Authorized (`{res.get('paypal_auth_id')}`) & captured (`{res.get('paypal_capture_id')}`) "
                    f"**`${res.get('amount', 0.0):.2f}`** via PayPal Sandbox."
                )
            elif status == "PENDING_APPROVAL":
                assistant_reply = (
                    f"Proposed order for **{target_item}** (Qty: `{qty:g}`), but your deterministic spending mandate "
                    f"flagged it as **NEEDS_APPROVAL**: *{res.get('message', '')}*\n"
                    f"Review the card below to **Approve** or **Reject**."
                )
            else:
                assistant_reply = res.get("message", f"Order denied by spending mandate.")

            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=cards,
                timestamp=clock.now().isoformat(),
            )

        # S8: Try Ollama (qwen2.5:7b) or Gemini function-calling LLM for open-ended conversation
        if gemini_client.is_available():
            llm_result = await gemini_client.generate_response(user_message, history)
            if llm_result:
                for fc in llm_result.get("function_calls", []):
                    name = fc["name"]
                    args = fc["args"]

                    if name == "request_purchase":
                        res = await agent_tool_handler.request_purchase(
                            db,
                            item_name=args.get("item_name", ""),
                            qty=float(args.get("qty", 1.0)),
                            urgency_hint=args.get("urgency_hint", "routine"),
                        )
                        cards.extend([CardPayload(**c) for c in res.get("cards", [])])
                        if not llm_result.get("text"):
                            assistant_reply += res.get("message", "") + " "

                    elif name == "set_stock":
                        res = agent_tool_handler.set_stock(
                            db,
                            item_name=args.get("item_name", ""),
                            qty=float(args.get("qty", 0.0)),
                            mode=args.get("mode", "absolute"),
                        )
                        assistant_reply += f"{res.get('message', '')} "

                    elif name == "create_rule":
                        res = agent_tool_handler.create_rule(
                            db,
                            item_name=args.get("item_name", ""),
                            rule_type=args.get("rule_type", "daily"),
                            qty=float(args.get("qty", 1.0)),
                        )
                        if "card" in res:
                            cards.append(CardPayload(**res["card"]))

                    elif name == "compare_offers":
                        res = await agent_tool_handler.compare_offers(
                            db,
                            item_name=args.get("item_name", ""),
                            qty=float(args.get("qty", 1.0)),
                        )
                        if "card" in res:
                            cards.append(CardPayload(**res["card"]))

                    elif name == "get_wallet_summary":
                        summary = agent_tool_handler.get_wallet_summary(db)
                        assistant_reply += f"Your e-wallet currently has ${summary['available_balance']:.2f} available. "

                    elif name == "list_items":
                        items_res = agent_tool_handler.list_items(db)
                        names = [f"{i['name']} ({i['stock_qty']} {i['unit']})" for i in items_res["items"]]
                        assistant_reply += f"Tracked inventory: {', '.join(names)}. "

                if llm_result.get("text"):
                    assistant_reply = (llm_result["text"] + " " + assistant_reply).strip()

                if assistant_reply or cards:
                    return ChatMessage(
                        id=str(uuid.uuid4()),
                        role="assistant",
                        content=assistant_reply or "Processed through your spending mandate.",
                        cards=cards,
                        timestamp=clock.now().isoformat(),
                    )

        # S9: If user explicitly asked to order/buy an unknown item, run it through the pipeline
        if any(w in user_lower for w in ["order ", "buy ", "purchase ", "get me "]):
            cleaned = re.sub(r"^(please\s+)?(order|buy|purchase|get me)\s+", "", user_message.strip(), flags=re.I).strip()
            res = await agent_tool_handler.request_purchase(db, item_name=cleaned, qty=1.0)
            for c in res.get("cards", []):
                cards.append(CardPayload(**c))
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=res.get("message", "Processed your purchase request through the mandate engine."),
                cards=cards,
                timestamp=clock.now().isoformat(),
            )

        # Otherwise return a clear, helpful assistant guidance message instead of failing
        return ChatMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content=(
                "I can help you **order items**, **set recurring or depletion rules**, **compare merchant prices**, "
                "or **check your wallet & inventory**.\n\n"
                "**Available catalog items:** Whole Milk 1L, Whey Protein Powder 1kg, A4 Copy Paper 500ct, WD-40 Multi-Use 300ml, "
                "Eggs 12ct, Coffee 500g, Bread 500g, AA Batteries 8-Pack, Laundry Detergent 2L.\n\n"
                "Try: *\"Order coffee\"*, *\"We're out of A4 paper\"*, or *\"Compare prices for milk\"*."
            ),
            cards=[],
            timestamp=clock.now().isoformat(),
        )


shopping_agent = ShoppingAgent()
