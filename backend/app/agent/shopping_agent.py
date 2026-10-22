import re
import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.app.agent.gemini_client import gemini_client
from backend.app.agent.tools import agent_tool_handler
from backend.app.contracts.chat import ChatMessage, CardPayload
from backend.app.scheduler.virtual_clock import clock

class ShoppingAgent:
    @staticmethod
    async def process_chat(
        db: Session,
        user_message: str,
        conversation_id: str = "default",
        history: List[Dict[str, str]] = None
    ) -> ChatMessage:
        user_lower = user_message.strip().lower()
        cards: List[CardPayload] = []
        assistant_reply = ""

        # Try Gemini LLM first if available
        if gemini_client.is_available():
            llm_result = await gemini_client.generate_response(user_message, history)
            if llm_result and llm_result.get("function_calls"):
                for fc in llm_result["function_calls"]:
                    name = fc["name"]
                    args = fc["args"]

                    if name == "request_purchase":
                        res = await agent_tool_handler.request_purchase(
                            db,
                            item_name=args.get("item_name", ""),
                            qty=float(args.get("qty", 1.0)),
                            urgency_hint=args.get("urgency_hint", "routine")
                        )
                        cards.extend([CardPayload(**c) for c in res.get("cards", [])])

                    elif name == "set_stock":
                        res = agent_tool_handler.set_stock(
                            db,
                            item_name=args.get("item_name", ""),
                            qty=float(args.get("qty", 0.0)),
                            mode=args.get("mode", "absolute")
                        )
                        assistant_reply += f"{res.get('message', '')} "

                    elif name == "create_rule":
                        res = agent_tool_handler.create_rule(
                            db,
                            item_name=args.get("item_name", ""),
                            rule_type=args.get("rule_type", "daily"),
                            qty=float(args.get("qty", 1.0))
                        )
                        if "card" in res:
                            cards.append(CardPayload(**res["card"]))

                    elif name == "compare_offers":
                        res = await agent_tool_handler.compare_offers(
                            db,
                            item_name=args.get("item_name", ""),
                            qty=float(args.get("qty", 1.0))
                        )
                        if "card" in res:
                            cards.append(CardPayload(**res["card"]))

                    elif name == "get_wallet_summary":
                        summary = agent_tool_handler.get_wallet_summary(db)
                        assistant_reply += (
                            f"Your e-wallet currently has ${summary['available_balance']:.2f} available "
                            f"(${summary['spent_balance']:.2f} spent today). "
                        )

                if llm_result.get("text"):
                    assistant_reply = llm_result["text"] + " " + assistant_reply

                return ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=assistant_reply.strip() or "Processed your request safely through the mandate engine.",
                    cards=cards,
                    timestamp=clock.now().isoformat()
                )

        # Smart deterministic offline intent processor (Guarantees 100% demo uptime)
        # Scenario 1: Multi-rule setup
        if any(w in user_lower for w in ["daily", "monthly", "when it runs out", "depletion"]):
            rules_created = []
            if "milk" in user_lower and "daily" in user_lower:
                r1 = agent_tool_handler.create_rule(db, "Whole Milk 1L", "daily", 1.0)
                cards.append(CardPayload(**r1["card"]))
                rules_created.append("daily milk")

            if "protein" in user_lower and ("monthly" in user_lower or "month" in user_lower):
                r2 = agent_tool_handler.create_rule(db, "Whey Protein Powder 1kg", "monthly", 1.0)
                cards.append(CardPayload(**r2["card"]))
                rules_created.append("monthly protein powder")

            if "paper" in user_lower and any(p in user_lower for p in ["finished", "runs out", "depletion", "empty"]):
                r3 = agent_tool_handler.create_rule(db, "A4 Copy Paper 500ct", "depletion", 1.0)
                cards.append(CardPayload(**r3["card"]))
                rules_created.append("A4 paper depletion trigger")

            if rules_created:
                assistant_reply = (
                    f"Understood! I've configured autonomous purchasing rules for: {', '.join(rules_created)}. "
                    "Each order will be checked against your mandate before payment."
                )
                return ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=assistant_reply,
                    cards=cards,
                    timestamp=clock.now().isoformat()
                )

        # Scenario 2: Urgent out-of-stock order (Paper or Milk)
        if any(phrase in user_lower for phrase in ["out of", "ran out", "finished", "order now", "urgent", "need paper", "buy paper"]):
            if "paper" in user_lower:
                # Update stock to 0
                agent_tool_handler.set_stock(db, "A4 Copy Paper 500ct", qty=0.0, mode="finished")
                # Request urgent purchase
                res = await agent_tool_handler.request_purchase(
                    db,
                    item_name="A4 Copy Paper 500ct",
                    qty=1.0,
                    urgency_hint="urgent"
                )
                for c in res.get("cards", []):
                    cards.append(CardPayload(**c))

                assistant_reply = (
                    f"You're out of A4 paper! I compared 5 merchants and selected {res.get('merchant', 'Quick10')} "
                    f"for fast delivery ({res.get('eta_minutes', 18)} mins). "
                    f"Payment of ${res.get('amount', 13.98):.2f} was authorized & captured through PayPal Sandbox."
                )
                return ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=assistant_reply,
                    cards=cards,
                    timestamp=clock.now().isoformat()
                )

        # Scenario 3: Untracked item order (WD-40) -> Mandate requires approval
        if "wd-40" in user_lower or "wd40" in user_lower:
            res = await agent_tool_handler.request_purchase(
                db,
                item_name="WD-40 Multi-Use 300ml",
                qty=1.0,
                urgency_hint="routine"
            )
            for c in res.get("cards", []):
                cards.append(CardPayload(**c))

            assistant_reply = (
                "I found WD-40, but since it is currently an untracked item, your spending mandate requires approval. "
                "Please review the card below and tap Approve."
            )
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=cards,
                timestamp=clock.now().isoformat()
            )

        # Scenario 4: Wallet or balance inquiry
        if any(w in user_lower for w in ["wallet", "balance", "money", "budget", "cap"]):
            summary = agent_tool_handler.get_wallet_summary(db)
            assistant_reply = (
                f"E-Wallet Status:\n"
                f"• Available Balance: ${summary['available_balance']:.2f}\n"
                f"• Spent Today: ${summary['daily_spent']:.2f} / ${summary['daily_cap']:.2f} limit\n"
                f"• Spent This Month: ${summary['monthly_spent']:.2f} / ${summary['monthly_cap']:.2f} cap\n"
                f"• Emergency Kill Switch: {'ACTIVE' if summary['kill_switch'] else 'Disabled'}"
            )
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=[],
                timestamp=clock.now().isoformat()
            )

        # Scenario 5: Price comparison preview
        if any(w in user_lower for w in ["compare", "price", "cheapest"]):
            item_query = "Whole Milk 1L" if "milk" in user_lower else ("Whey Protein Powder 1kg" if "protein" in user_lower else "A4 Copy Paper 500ct")
            res = await agent_tool_handler.compare_offers(db, item_query, qty=1.0)
            if "card" in res:
                cards.append(CardPayload(**res["card"]))
            assistant_reply = f"Here is the live price and ETA comparison for {item_query} across all 5 merchants."
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=cards,
                timestamp=clock.now().isoformat()
            )

        # General order fallback
        res = await agent_tool_handler.request_purchase(
            db,
            item_name=user_message.strip(),
            qty=1.0
        )
        for c in res.get("cards", []):
            cards.append(CardPayload(**c))
            
        assistant_reply = res.get("message", "Request evaluated by mandate engine.")
        return ChatMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content=assistant_reply,
            cards=cards,
            timestamp=clock.now().isoformat()
        )

shopping_agent = ShoppingAgent()
