import json
import logging
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types

from backend.app.config import settings
from backend.r3_agent_conversation.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

GEMINI_TOOLS_SCHEMA = [
    {
        "name": "request_purchase",
        "description": "Submit a purchase proposal to the deterministic mandate engine.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_name": {"type": "STRING", "description": "Product name (e.g. 'A4 paper', 'milk', 'WD-40')."},
                "qty": {"type": "NUMBER", "description": "Quantity to order."},
                "urgency_hint": {"type": "STRING", "description": "'urgent' if stock is zero or needed immediately, else 'routine' or 'planned'."}
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "set_stock",
        "description": "Update inventory stock quantity or mark an item as finished.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_name": {"type": "STRING", "description": "Item name."},
                "qty": {"type": "NUMBER", "description": "New quantity."},
                "mode": {"type": "STRING", "description": "'finished' if out of stock, 'absolute' to set quantity, 'delta' to adjust."}
            },
            "required": ["item_name", "mode"]
        }
    },
    {
        "name": "create_rule",
        "description": "Create an autonomous restocking rule (daily, monthly, or depletion-triggered).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_name": {"type": "STRING", "description": "Item name."},
                "rule_type": {"type": "STRING", "description": "'daily', 'weekly', 'monthly', or 'depletion'."},
                "qty": {"type": "NUMBER", "description": "Quantity to order."}
            },
            "required": ["item_name", "rule_type"]
        }
    },
    {
        "name": "compare_offers",
        "description": "Preview and compare prices across all merchants without buying.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_name": {"type": "STRING", "description": "Item to compare."},
                "qty": {"type": "NUMBER", "description": "Quantity."}
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "get_wallet_summary",
        "description": "Check current e-wallet balance and spend against mandate caps.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "list_items",
        "description": "List all tracked items in inventory with days of cover and stock levels.",
        "parameters": {"type": "OBJECT", "properties": {}}
    }
]

class GeminiAgentClient:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def is_available(self) -> bool:
        return bool(self.client and self.api_key)

    async def generate_response(self, user_message: str, history: List[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None
        try:
            contents = []
            if history:
                for msg in history:
                    contents.append(types.Content(
                        role="user" if msg["role"] == "user" else "model",
                        parts=[types.Part.from_text(text=msg["content"])]
                    ))
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)]
            ))

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                tools=[{"function_declarations": GEMINI_TOOLS_SCHEMA}]
            )

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=config
            )

            function_calls = []
            if response.function_calls:
                for fc in response.function_calls:
                    function_calls.append({"name": fc.name, "args": fc.args})

            return {
                "text": response.text or "",
                "function_calls": function_calls
            }
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return None

gemini_client = GeminiAgentClient()
