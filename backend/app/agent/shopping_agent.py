import re
import uuid
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.app.contracts.chat import ChatMessage, CardPayload
from backend.app.contracts.schemas import ItemCreate, StockUpdateRequest
from backend.app.agent.gemini_client import gemini_client
from backend.app.agent.tools import agent_tool_handler
from backend.app.inventory.service import inventory_service
from backend.app.db.models import OrderModel, RuleModel
from backend.app.scheduler.virtual_clock import clock


# Map common natural-language terms to canonical catalog item names
CATALOG_SYNONYMS: Dict[str, str] = {
    "milk": "Whole Milk 1L",
    "whole milk": "Whole Milk 1L",
    "dairy": "Whole Milk 1L",
    "protein": "Whey Protein Powder 1kg",
    "protein powder": "Whey Protein Powder 1kg",
    "whey": "Whey Protein Powder 1kg",
    "paper": "A4 Copy Paper 500ct",
    "a4 paper": "A4 Copy Paper 500ct",
    "copy paper": "A4 Copy Paper 500ct",
    "printer paper": "A4 Copy Paper 500ct",
    "wd-40": "WD-40 Multi-Use 300ml",
    "wd40": "WD-40 Multi-Use 300ml",
    "lubricant": "WD-40 Multi-Use 300ml",
    "egg": "Eggs 12ct",
    "eggs": "Eggs 12ct",
    "coffee": "Coffee 500g",
    "espresso": "Coffee 500g",
    "bread": "Bread 500g",
    "sourdough": "Bread 500g",
    "loaf": "Bread 500g",
    "battery": "AA Batteries 8-Pack",
    "batteries": "AA Batteries 8-Pack",
    "aa batteries": "AA Batteries 8-Pack",
    "detergent": "Laundry Detergent 2L",
    "laundry": "Laundry Detergent 2L",
    "tide": "Laundry Detergent 2L",
}

# Built-in Culinary & Goal Knowledge Graph for instant, deterministic recipe/project decomposition
RECIPE_AND_GOAL_GRAPH: Dict[str, Dict[str, Any]] = {
    "paneer butter masala": {
        "title": "Paneer Butter Masala",
        "items": [
            {"name": "Fresh Malai Paneer 200g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Unsalted Creamery Butter 100g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Fresh Roma Tomatoes 500g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Heavy Cooking Cream 200ml", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Cashews & Garam Masala Spice Kit", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "shahi paneer": {
        "title": "Shahi Paneer",
        "items": [
            {"name": "Fresh Malai Paneer 200g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Heavy Cooking Cream 200ml", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Cashews & Almond Paste 150g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Pure Desi Ghee 200ml", "category": "grocery", "unit": "jar", "qty": 1},
            {"name": "Saffron & Cardamom Spice Mix", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "palak paneer": {
        "title": "Palak Paneer",
        "items": [
            {"name": "Fresh Malai Paneer 200g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Organic Baby Spinach 300g", "category": "grocery", "unit": "bag", "qty": 2},
            {"name": "Heavy Cooking Cream 200ml", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Ginger Garlic & Green Chili Paste", "category": "grocery", "unit": "jar", "qty": 1},
        ],
    },
    "butter chicken": {
        "title": "Butter Chicken (Murgh Makhani)",
        "items": [
            {"name": "Boneless Chicken Tikka Cut 500g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Unsalted Creamery Butter 100g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Fresh Roma Tomatoes 500g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Heavy Cooking Cream 200ml", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Tandoori & Garam Masala Spice Pack", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "biryani": {
        "title": "Hyderabadi Dum Biryani",
        "items": [
            {"name": "Aged Basmati Rice 1kg", "category": "grocery", "unit": "bag", "qty": 1},
            {"name": "Fresh Mint & Cilantro Bunch", "category": "grocery", "unit": "bunch", "qty": 1},
            {"name": "Greek Yogurt 400g", "category": "grocery", "unit": "tub", "qty": 1},
            {"name": "Pure Desi Ghee 200ml", "category": "grocery", "unit": "jar", "qty": 1},
            {"name": "Shahi Biryani Masala & Crispy Onions", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "dal makhani": {
        "title": "Dal Makhani",
        "items": [
            {"name": "Whole Black Urad Dal & Rajma 500g", "category": "grocery", "unit": "bag", "qty": 1},
            {"name": "Unsalted Creamery Butter 100g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Heavy Cooking Cream 200ml", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Fresh Roma Tomatoes 500g", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "pav bhaji": {
        "title": "Mumbai Pav Bhaji",
        "items": [
            {"name": "Soft Ladi Pav Buns 6-Pack", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Unsalted Creamery Butter 100g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Potatoes, Peas & Cauliflower Mix 500g", "category": "grocery", "unit": "bag", "qty": 1},
            {"name": "Pav Bhaji Masala & Lemon Pack", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "chole": {
        "title": "Punjabi Chole Masala",
        "items": [
            {"name": "Kabuli Chickpeas 500g", "category": "grocery", "unit": "bag", "qty": 1},
            {"name": "Fresh Roma Tomatoes & Onions 500g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Chole Masala Spice Blend", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "masala dosa": {
        "title": "South Indian Masala Dosa",
        "items": [
            {"name": "Fresh Idli-Dosa Batter 1kg", "category": "grocery", "unit": "tub", "qty": 1},
            {"name": "Potatoes & Curry Leaves Pack 500g", "category": "grocery", "unit": "bag", "qty": 1},
            {"name": "Fresh Coconut Chutney & Sambar Kit", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "pasta": {
        "title": "Creamy Italian Pasta",
        "items": [
            {"name": "Durum Wheat Penne Pasta 500g", "category": "grocery", "unit": "box", "qty": 1},
            {"name": "Heavy Cooking Cream 200ml", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Grated Parmesan Cheese 150g", "category": "grocery", "unit": "tub", "qty": 1},
            {"name": "Unsalted Creamery Butter 100g", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "pizza": {
        "title": "Homemade Margherita Pizza",
        "items": [
            {"name": "Artisan Pizza Dough Base 2-Pack", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Fresh Mozzarella Cheese 250g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "San Marzano Tomato Pizza Sauce", "category": "grocery", "unit": "jar", "qty": 1},
            {"name": "Fresh Sweet Basil & Oregano", "category": "grocery", "unit": "bunch", "qty": 1},
        ],
    },
    "cake": {
        "title": "Homemade Chocolate Cake",
        "items": [
            {"name": "All-Purpose Baking Flour 1kg", "category": "grocery", "unit": "bag", "qty": 1},
            {"name": "Dutch-Process Cocoa Powder 200g", "category": "grocery", "unit": "tin", "qty": 1},
            {"name": "Eggs 12ct", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Whole Milk 1L", "category": "grocery", "unit": "bottle", "qty": 1},
            {"name": "Unsalted Creamery Butter 100g", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "pancake": {
        "title": "Fluffy Breakfast Pancakes",
        "items": [
            {"name": "All-Purpose Baking Flour 1kg", "category": "grocery", "unit": "bag", "qty": 1},
            {"name": "Eggs 12ct", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Whole Milk 1L", "category": "grocery", "unit": "bottle", "qty": 1},
            {"name": "Pure Maple Syrup 250ml", "category": "grocery", "unit": "bottle", "qty": 1},
        ],
    },
    "breakfast": {
        "title": "Complete Morning Breakfast",
        "items": [
            {"name": "Eggs 12ct", "category": "grocery", "unit": "carton", "qty": 1},
            {"name": "Bread 500g", "category": "grocery", "unit": "loaf", "qty": 1},
            {"name": "Whole Milk 1L", "category": "grocery", "unit": "bottle", "qty": 1},
            {"name": "Coffee 500g", "category": "grocery", "unit": "bag", "qty": 1},
        ],
    },
    "chai": {
        "title": "Masala Chai",
        "items": [
            {"name": "Whole Milk 1L", "category": "grocery", "unit": "bottle", "qty": 1},
            {"name": "Assam Loose Leaf Tea 250g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Fresh Ginger & Cardamom Pods", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "sandwich": {
        "title": "Grilled Cheese & Veggie Sandwich",
        "items": [
            {"name": "Bread 500g", "category": "grocery", "unit": "loaf", "qty": 1},
            {"name": "Sliced Cheddar Cheese 200g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Unsalted Creamery Butter 100g", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    },
    "home office": {
        "title": "Home Office Essentials Kit",
        "items": [
            {"name": "A4 Copy Paper 500ct", "category": "supplies", "unit": "ream", "qty": 1},
            {"name": "AA Batteries 8-Pack", "category": "supplies", "unit": "pack", "qty": 1},
            {"name": "Gel Rollerball Pens 12-Pack", "category": "supplies", "unit": "pack", "qty": 1},
        ],
    },
}


def _resolve_item_from_text(db: Session, text: str) -> Optional[str]:
    text_lower = text.lower()
    for it in inventory_service.get_all_items(db):
        if it.name.lower() in text_lower:
            return it.name
        first_word = it.name.lower().split()[0]
        if len(first_word) >= 4 and re.search(rf"\b{re.escape(first_word)}\b", text_lower):
            return it.name

    for alias in sorted(CATALOG_SYNONYMS.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", text_lower):
            return CATALOG_SYNONYMS[alias]
    return None


def _extract_qty(text: str, default: float = 1.0) -> float:
    m = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:x|bottles?|packs?|reams?|bags?|cans?|cartons?|loaves?|units?|boxes?|liters?|kg)?\b",
        text.lower(),
    )
    if m:
        val = float(m.group(1))
        if 0 < val <= 50 and str(int(val)) not in ["40", "4"]:
            return val
    return default


def _is_recipe_or_goal_intent(user_lower: str) -> bool:
    """Detect whether the user is asking the AI Assistant to plan/order ingredients for a dish, meal, or multi-item goal."""
    goal_triggers = [
        "make ",
        "making ",
        "cook ",
        "cooking ",
        "prepare ",
        "preparing ",
        "bake ",
        "baking ",
        "ingredients",
        "recipe",
        "paneer",
        "masala",
        "biryani",
        "butter chicken",
        "dal makhani",
        "pav bhaji",
        "chole",
        "dosa",
        "pasta",
        "pizza",
        "cake",
        "pancake",
        "breakfast",
        "chai",
        "sandwich",
        "home office",
    ]
    if any(t in user_lower for t in goal_triggers):
        return True
    # Also detect comma-separated multi-item orders like "order paneer, butter, and tomatoes"
    if "," in user_lower and any(w in user_lower for w in ["order", "buy", "need", "get"]):
        return True
    return False


async def _build_goal_plan(user_message: str) -> Dict[str, Any]:
    """
    Decompose a user's dish, recipe, project, or multi-item shopping list into
    structured ingredients and reasoning steps.
    """
    user_lower = user_message.strip().lower()

    # 1. Check curated Recipe & Goal Knowledge Graph first for instant, high-accuracy culinary recipes
    for key, plan in RECIPE_AND_GOAL_GRAPH.items():
        if key in user_lower:
            return {
                "goal_title": plan["title"],
                "items": plan["items"],
            }

    # Check partial keyword matches (e.g. "paneer" -> Paneer Butter Masala)
    if "paneer" in user_lower:
        plan = RECIPE_AND_GOAL_GRAPH["paneer butter masala"]
        return {"goal_title": plan["title"], "items": plan["items"]}

    # 2. Check comma-separated shopping list (e.g. "order tomatoes, onions, and butter")
    if "," in user_message and any(w in user_lower for w in ["order", "buy", "get", "need"]):
        cleaned = re.sub(
            r"^(?:i\s+need\s+to\s+|please\s+)?(?:order|buy|get|purchase|need)\s+",
            "",
            user_message.strip(),
            flags=re.I,
        )
        parts = [
            re.sub(r"^(?:and|all|some)\s+", "", p.strip(), flags=re.I).strip()
            for p in re.split(r",|\band\b", cleaned)
        ]
        parts = [p for p in parts if len(p) >= 2 and "ingredient" not in p.lower()]
        if len(parts) >= 2:
            return {
                "goal_title": "Multi-Item Shopping List",
                "items": [
                    {
                        "name": CATALOG_SYNONYMS.get(p.lower(), f"{p.title()} Pack"),
                        "category": "grocery",
                        "unit": "pack",
                        "qty": 1,
                    }
                    for p in parts[:6]
                ],
            }

    # 3. Try LLM (Ollama qwen2.5:7b or Google Gemini) for arbitrary custom dishes/projects
    llm_plan = await gemini_client.decompose_goal_with_llm(user_message)
    if llm_plan and llm_plan.get("items"):
        return llm_plan

    # 4. Smart Dynamic Culinary Extractor for any custom dish ("i need to make <dish>, order all ingredients")
    m = re.search(
        r"(?:make|cook|prepare|bake|for)\s+([a-zA-Z0-9\s\-]+?)(?:\s*,|\s+and\s+order|\s+order|\s+buy|\s+ingredients|$)",
        user_lower,
    )
    dish_name = (m.group(1).strip().title() if m else "Custom Dish").replace("All Ingredients", "").strip() or "Custom Meal"

    return {
        "goal_title": dish_name,
        "items": [
            {"name": f"Fresh {dish_name} Base Pack", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Fresh Roma Tomatoes & Onions 500g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": "Unsalted Creamery Butter 100g", "category": "grocery", "unit": "pack", "qty": 1},
            {"name": f"{dish_name} Signature Spice & Herb Kit", "category": "grocery", "unit": "pack", "qty": 1},
        ],
    }


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
                    f"Hello! I'm **CommPal**, your autonomous AI shopping & inventory assistant.\n\n"
                    f"**Current Status:**\n"
                    f"• **PayPal Wallet:** `${summary['available_balance']:.2f}` available (`${summary['daily_spent']:.2f} / ${summary['daily_cap']:.2f}` daily cap used)\n"
                    f"• **Tracked Pantry:** {len(items_res)} items ({', '.join(i['name'] for i in items_res[:4])})\n\n"
                    f"**Try asking me to think & plan for you:**\n"
                    f"• *\"I need to make paneer butter masala, order all ingredients\"*\n"
                    f"• *\"We ran out of A4 paper\"* (triggers urgent quick-commerce fulfillment)\n"
                    f"• *\"Order WD-40\"* (demonstrates safety approval gate)\n"
                    f"• *\"Compare prices for whole milk\"*"
                ),
                cards=[],
                timestamp=clock.now().isoformat(),
            )

        # S1: Multi-rule or single-rule recurring setup ("milk daily, protein monthly...")
        if any(
            w in user_lower
            for w in ["daily", "weekly", "monthly", "every day", "every month", "when it runs out", "depletion", "schedule"]
        ):
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

        # S2: AGENTIC GOAL, RECIPE & MULTI-ITEM DECOMPOSITION ("i need to make paneer butter masala , order all ingredients")
        if _is_recipe_or_goal_intent(user_lower):
            plan = await _build_goal_plan(user_message)
            goal_title = plan.get("goal_title", "Recipe & Goal Plan")
            planned_items = plan.get("items", [])

            reasoning_steps: List[str] = [
                f"🎯 Goal Identified: Preparing **{goal_title}** — decomposed into {len(planned_items)} required ingredients.",
            ]

            bundle_results: List[Dict[str, Any]] = []
            total_bundle_cost = 0.0
            ordered_count = 0
            skipped_in_pantry = 0

            for ing in planned_items:
                ing_name = ing["name"]
                ing_qty = float(ing.get("qty", 1.0))
                ing_cat = ing.get("category", "grocery")
                ing_unit = ing.get("unit", "pack")

                # 1. Check if item is already in My Pantry with enough stock!
                existing = inventory_service.get_item_by_name(db, ing_name)
                if existing:
                    cur_stock, _, _, _ = inventory_service.calculate_stock_and_cover(existing, clock.now())
                    if cur_stock >= ing_qty:
                        skipped_in_pantry += 1
                        reasoning_steps.append(
                            f"✓ Pantry Check: **{existing.name}** is already in stock (`{cur_stock} {existing.unit}`) — skipped buying to save you money."
                        )
                        bundle_results.append(
                            {
                                "item_name": existing.name,
                                "qty": ing_qty,
                                "decision": "IN_PANTRY",
                                "merchant": "My Pantry (In Stock)",
                                "eta_minutes": 0,
                                "amount": 0.0,
                                "paypal_id": "SKIPPED",
                            }
                        )
                        continue
                else:
                    # Register the recipe ingredient in My Pantry so it's tracked and visible in Left Column
                    existing = inventory_service.create_item(
                        db,
                        ItemCreate(
                            name=ing_name,
                            category=ing_cat,
                            unit=ing_unit,
                            stock_qty=0.0,
                            burn_rate_per_day=0.5,
                            threshold_days=1.5,
                            reorder_qty=ing_qty,
                            last_price=4.99,
                        ),
                    )

                # 2. Execute multi-merchant routing, mandate evaluation & PayPal settlement
                res = await agent_tool_handler.request_purchase(
                    db=db,
                    item_name=existing.name,
                    qty=ing_qty,
                    urgency_hint="urgent",
                )
                status = res.get("status")
                if status == "ORDER_PLACED":
                    ordered_count += 1
                    amt = float(res.get("amount", 0.0))
                    total_bundle_cost += amt
                    # Stock the item into Pantry so user sees their new ingredients ready
                    inventory_service.update_stock(
                        db,
                        existing.id,
                        StockUpdateRequest(mode="absolute", qty=ing_qty, reason=f"Ordered for {goal_title}"),
                    )
                    reasoning_steps.append(
                        f"🛒 Ordered **{existing.name}** (&times;{ing_qty:g}) from **{res.get('merchant')}** (`${amt:.2f}`, ETA `{res.get('eta_minutes')}m`, PayPal `{res.get('paypal_capture_id')}`)."
                    )
                    bundle_results.append(
                        {
                            "item_name": existing.name,
                            "qty": ing_qty,
                            "decision": "ORDERED",
                            "merchant": res.get("merchant"),
                            "eta_minutes": res.get("eta_minutes"),
                            "amount": amt,
                            "paypal_id": res.get("paypal_capture_id") or res.get("paypal_auth_id"),
                        }
                    )
                elif status == "PENDING_APPROVAL":
                    reasoning_steps.append(
                        f"⚠ **{existing.name}** paused for human approval: {res.get('message', '')}"
                    )
                    bundle_results.append(
                        {
                            "item_name": existing.name,
                            "qty": ing_qty,
                            "decision": "PENDING_APPROVAL",
                            "merchant": res.get("merchant", "Best Store"),
                            "eta_minutes": res.get("eta_minutes", 20),
                            "amount": float(res.get("amount", 0.0)),
                            "paypal_id": "NEEDS_APPROVAL",
                        }
                    )
                else:
                    reasoning_steps.append(
                        f"✕ **{existing.name}** could not be ordered: {res.get('message', status)}"
                    )
                    bundle_results.append(
                        {
                            "item_name": existing.name,
                            "qty": ing_qty,
                            "decision": "DENIED",
                            "merchant": "—",
                            "eta_minutes": 0,
                            "amount": 0.0,
                            "paypal_id": status,
                        }
                    )

            # Attach AI Reasoning Card + Recipe Bundle Card
            cards.append(
                CardPayload(
                    card_type="ai_reasoning",
                    title=f"🧠 AI Assistant Decision Trace: {goal_title}",
                    subtitle=f"Analyzed {len(planned_items)} ingredients · {ordered_count} ordered · {skipped_in_pantry} already in Pantry",
                    data={"steps": reasoning_steps},
                )
            )
            cards.append(
                CardPayload(
                    card_type="recipe_bundle",
                    title=f"🍲 {goal_title} — Ingredient Orders",
                    subtitle=f"Total PayPal Settlement: ${total_bundle_cost:.2f} across {ordered_count} item(s)",
                    data={
                        "goal_title": goal_title,
                        "total_cost": round(total_bundle_cost, 2),
                        "ordered_count": ordered_count,
                        "skipped_count": skipped_in_pantry,
                        "items": bundle_results,
                    },
                )
            )

            summary_text = (
                f"I analyzed what you need to make **{goal_title}**, checked **My Pantry**, compared all 5 stores, "
                f"and placed **{ordered_count} PayPal order(s)** totaling **`${total_bundle_cost:.2f}`**"
                + (
                    f" (and skipped **{skipped_in_pantry} item(s)** you already had in stock!)."
                    if skipped_in_pantry > 0
                    else "."
                )
            )

            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=summary_text,
                cards=cards,
                timestamp=clock.now().isoformat(),
            )

        # S3: Price comparison across merchants
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
                    f"Compared **{len(offers)} live store offers** for **{target_item}** (Qty: {qty:g}):\n"
                    f"• **Lowest Price:** {cheapest['merchant_name']} at `${cheapest['landed_price']:.2f}` (ETA: {cheapest['eta_minutes']}m)\n"
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

        # S4: Inventory / Stock inspection
        if any(
            w in user_lower
            for w in ["inventory", "pantry", "what do we have", "stock level", "show items", "list items", "days of cover"]
        ):
            items_res = agent_tool_handler.list_items(db)["items"]
            lines = [
                f"• **{it['name']}**: `{it['stock_qty']} {it['unit']}` ({it['days_of_cover']}d cover)"
                for it in items_res
            ]
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Current Tracked Pantry:\n" + "\n".join(lines),
                cards=[],
                timestamp=clock.now().isoformat(),
            )

        # S5: Wallet / Budget / Mandate inspection
        if any(w in user_lower for w in ["wallet", "balance", "money", "budget", "cap", "spent", "mandate"]):
            summary = agent_tool_handler.get_wallet_summary(db)
            assistant_reply = (
                f"**Sandboxed PayPal Wallet Summary:**\n"
                f"• **Available Balance:** `${summary['available_balance']:.2f}`\n"
                f"• **Held in Escrow:** `${summary['held_balance']:.2f}`\n"
                f"• **Total Settled Spend:** `${summary['spent_balance']:.2f}`\n"
                f"• **Daily Mandate Cap:** `${summary['daily_spent']:.2f} / ${summary['daily_cap']:.2f}`\n"
                f"• **Kill Switch:** `{'PAUSED' if summary['kill_switch'] else 'ACTIVE'}`"
            )
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=[],
                timestamp=clock.now().isoformat(),
            )

        # S6: Order history / Explanation query
        if any(w in user_lower for w in ["recent orders", "my orders", "order status", "why did you choose", "why did you pick"]):
            orders = db.query(OrderModel).order_by(OrderModel.created_at.desc()).limit(4).all()
            if not orders:
                return ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content="No orders have been placed yet. Try saying *\"I need to make paneer butter masala, order all ingredients\"* or *\"We ran out of A4 paper\"*.",
                    cards=[],
                    timestamp=clock.now().isoformat(),
                )
            lines = [
                f"• **#{o.id[-8:]}** — {o.item_name} via **{o.merchant_name}** (`${o.amount:.2f}`, {o.state}, PayPal `{o.paypal_capture_id}`)"
                for o in orders
            ]
            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content="Recent Autonomous Orders:\n" + "\n".join(lines),
                cards=cards,
                timestamp=clock.now().isoformat(),
            )

        # S7: Stockout / Depletion trigger ("we're out of X", "ran out of X", "X is empty/finished")
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
                        f"Evaluated 5 stores, selected **{res.get('merchant')}** (ETA: `{res.get('eta_minutes')} mins`), "
                        f"and paid **`${res.get('amount', 0.0):.2f}`** via PayPal (`{res.get('paypal_capture_id')}`)."
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

        # S8: Direct single-item purchase intent ("order X", "buy X", "get X", "need X")
        target_item = _resolve_item_from_text(db, user_lower)
        if target_item and any(
            w in user_lower
            for w in [
                "order",
                "buy",
                "get",
                "need",
                "purchase",
                "restock",
                "wd-40",
                "wd40",
                "milk",
                "paper",
                "protein",
                "eggs",
                "coffee",
                "bread",
                "batteries",
                "detergent",
            ]
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
                    f"Paid **`${res.get('amount', 0.0):.2f}`** via PayPal (`{res.get('paypal_capture_id')}`)."
                )
            elif status == "PENDING_APPROVAL":
                assistant_reply = (
                    f"I found the best offer for **{target_item}** (Qty: `{qty:g}`), but your safety rules "
                    f"paused it for your permission: *{res.get('message', '')}*\n"
                    f"Click **✓ Approve & Pay with PayPal** above to complete the order."
                )
            else:
                assistant_reply = res.get("message", "Order denied by spending mandate.")

            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=cards,
                timestamp=clock.now().isoformat(),
            )

        # S9: Open-ended single-item order ("order <custom item>", "buy <custom item>")
        if any(w in user_lower for w in ["order ", "buy ", "purchase ", "get me "]):
            cleaned = re.sub(
                r"^(please\s+|can you\s+|i want to\s+)?(order|buy|purchase|get me)\s+",
                "",
                user_message.strip(),
                flags=re.I,
            ).strip()
            qty = _extract_qty(cleaned, 1.0)
            cleaned_name = re.sub(r"^\d+(?:\.\d+)?\s*(?:x|packs?|bags?|bottles?)?\s*", "", cleaned, flags=re.I).strip() or cleaned

            # Track item in Pantry if not restricted like WD-40
            existing = inventory_service.get_item_by_name(db, cleaned_name)
            if not existing and "wd-40" not in cleaned_name.lower() and "wd40" not in cleaned_name.lower():
                existing = inventory_service.create_item(
                    db,
                    ItemCreate(
                        name=cleaned_name.title(),
                        category="grocery",
                        unit="unit",
                        stock_qty=0.0,
                        burn_rate_per_day=0.5,
                        threshold_days=1.5,
                        reorder_qty=qty,
                        last_price=5.99,
                    ),
                )

            res = await agent_tool_handler.request_purchase(
                db, item_name=existing.name if existing else cleaned_name, qty=qty, urgency_hint="urgent"
            )
            for c in res.get("cards", []):
                cards.append(CardPayload(**c))

            if res.get("status") == "ORDER_PLACED" and existing:
                inventory_service.update_stock(
                    db, existing.id, StockUpdateRequest(mode="absolute", qty=qty, reason="Ordered via AI Assistant")
                )
                assistant_reply = (
                    f"Ordered **{existing.name}** (Qty: `{qty:g}`) from **{res.get('merchant')}** "
                    f"(ETA `{res.get('eta_minutes')} mins`, **`${res.get('amount', 0.0):.2f}`** via PayPal `{res.get('paypal_capture_id')}`)."
                )
            else:
                assistant_reply = res.get("message", "Processed your purchase request through the mandate engine.")

            return ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=assistant_reply,
                cards=cards,
                timestamp=clock.now().isoformat(),
            )

        # S10: Try Ollama / Gemini for general conversation
        if gemini_client.is_available():
            llm_result = await gemini_client.generate_response(user_message, history)
            if llm_result and llm_result.get("text"):
                return ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=llm_result["text"],
                    cards=[],
                    timestamp=clock.now().isoformat(),
                )

        # Helpful guidance fallback
        return ChatMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content=(
                "I can **plan recipes & order all missing ingredients**, **buy any item**, **compare store prices**, "
                "or **set recurring restock rules**.\n\n"
                "Try asking:\n"
                "• *\"I need to make paneer butter masala, order all ingredients\"*\n"
                "• *\"I want to cook biryani tonight, order everything\"*\n"
                "• *\"We ran out of A4 paper\"*\n"
                "• *\"Compare prices for milk\"*"
            ),
            cards=[],
            timestamp=clock.now().isoformat(),
        )


shopping_agent = ShoppingAgent()
