import json
import logging
import time
from typing import Optional, Dict, Any, List
import httpx
from google import genai
from google.genai import types

from backend.app.config import settings
from backend.app.agent.prompts import SYSTEM_PROMPT

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
                "urgency_hint": {
                    "type": "STRING",
                    "description": "'urgent' if stock is zero or needed immediately, else 'routine' or 'planned'.",
                },
            },
            "required": ["item_name"],
        },
    },
    {
        "name": "set_stock",
        "description": "Update inventory stock quantity or mark an item as finished.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_name": {"type": "STRING", "description": "Item name."},
                "qty": {"type": "NUMBER", "description": "New quantity."},
                "mode": {
                    "type": "STRING",
                    "description": "'finished' if out of stock, 'absolute' to set quantity, 'delta' to adjust.",
                },
            },
            "required": ["item_name", "mode"],
        },
    },
    {
        "name": "create_rule",
        "description": "Create an autonomous restocking rule (daily, monthly, or depletion-triggered).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_name": {"type": "STRING", "description": "Item name."},
                "rule_type": {"type": "STRING", "description": "'daily', 'weekly', 'monthly', or 'depletion'."},
                "qty": {"type": "NUMBER", "description": "Quantity to order."},
            },
            "required": ["item_name", "rule_type"],
        },
    },
    {
        "name": "compare_offers",
        "description": "Preview and compare prices across all merchants without buying.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "item_name": {"type": "STRING", "description": "Item to compare."},
                "qty": {"type": "NUMBER", "description": "Quantity."},
            },
            "required": ["item_name"],
        },
    },
    {
        "name": "get_wallet_summary",
        "description": "Check current e-wallet balance and spend against mandate caps.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
    {
        "name": "list_items",
        "description": "List all tracked items in inventory with days of cover and stock levels.",
        "parameters": {"type": "OBJECT", "properties": {}},
    },
]

# Convert tool schema to OpenAI/Ollama tool format for qwen2.5:7b native function calling
OLLAMA_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": {
                "type": "object",
                "properties": {
                    k: {"type": v["type"].lower(), "description": v.get("description", "")}
                    for k, v in t["parameters"].get("properties", {}).items()
                },
                "required": t["parameters"].get("required", []),
            },
        },
    }
    for t in GEMINI_TOOLS_SCHEMA
]


class OllamaAgentClient:
    """
    Local Ollama LLM client for qwen2.5:7b with native tool-calling and connection reuse.
    """
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self._available_cache: Optional[bool] = None
        self._cache_ts: float = 0.0

    def is_available(self) -> bool:
        if settings.LLM_PROVIDER == "offline":
            return False
        now = time.monotonic()
        if self._available_cache is not None and (now - self._cache_ts) < 30.0:
            return self._available_cache
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                model_prefix = self.model.split(":")[0]
                self._available_cache = any(model_prefix in m for m in models)
            else:
                self._available_cache = False
        except Exception:
            self._available_cache = False
        self._cache_ts = now
        return bool(self._available_cache)

    async def generate_response(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            for msg in history:
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": OLLAMA_TOOLS_SCHEMA,
            "stream": False,
            "keep_alive": "15m",
            "options": {"temperature": 0.1},
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                message = data.get("message", {})
                text = message.get("content", "") or ""
                raw_tool_calls = message.get("tool_calls", []) or []

                function_calls = []
                for tc in raw_tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name")
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    if name:
                        function_calls.append({"name": name, "args": args})

                return {"text": text, "function_calls": function_calls, "provider": f"ollama:{self.model}"}
        except Exception as e:
            logger.debug(f"Ollama call skipped/timed out ({e}); falling back to deterministic NLU.")
            return None


class GeminiAgentClient:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.client = None
        self.ollama = OllamaAgentClient()
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def is_gemini_available(self) -> bool:
        return bool(self.client and self.api_key)

    def is_available(self) -> bool:
        if settings.LLM_PROVIDER == "ollama" and self.ollama.is_available():
            return True
        return self.is_gemini_available()

    @staticmethod
    def _fallback_parse(user_message: str) -> Dict[str, Any]:
        """Deterministic offline NLU parser for core shopping & inventory intents."""
        user_lower = user_message.strip().lower()
        tool_calls: List[Dict[str, Any]] = []

        if any(p in user_lower for p in ["out of", "ran out", "finished", "empty"]) and "paper" in user_lower:
            tool_calls.append({"name": "update_stock", "args": {"item_name": "A4 Copy Paper 500ct", "qty": 0.0, "mode": "finished"}})
            if any(p in user_lower for p in ["order", "buy", "need", "urgent"]):
                tool_calls.append({"name": "request_purchase", "args": {"item_name": "A4 Copy Paper 500ct", "qty": 1.0, "urgency_hint": "urgent"}})
            return {"tool_calls": tool_calls}

        if "wd-40" in user_lower or "wd40" in user_lower:
            tool_calls.append({"name": "request_purchase", "args": {"item_name": "WD-40 Multi-Use", "qty": 1.0, "urgency_hint": "routine"}})
            return {"tool_calls": tool_calls}

        if "milk" in user_lower:
            tool_calls.append({"name": "request_purchase", "args": {"item_name": "Whole Milk 1L", "qty": 1.0, "urgency_hint": "urgent"}})
            return {"tool_calls": tool_calls}

        if "protein" in user_lower:
            tool_calls.append({"name": "request_purchase", "args": {"item_name": "Whey Protein Powder 1kg", "qty": 1.0, "urgency_hint": "planned"}})
            return {"tool_calls": tool_calls}

        return {"tool_calls": tool_calls}

    async def generate_response(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        # 1. Try local Ollama (qwen2.5:7b) first when configured
        if settings.LLM_PROVIDER == "ollama" and self.ollama.is_available():
            ollama_res = await self.ollama.generate_response(user_message, history)
            if ollama_res and (ollama_res.get("function_calls") or ollama_res.get("text")):
                return ollama_res

        # 2. Try Google Gemini if API key is configured
        if not self.is_gemini_available():
            return None
        try:
            contents = []
            if history:
                for msg in history:
                    contents.append(
                        types.Content(
                            role="user" if msg["role"] == "user" else "model",
                            parts=[types.Part.from_text(text=msg["content"])],
                        )
                    )
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                tools=[{"function_declarations": GEMINI_TOOLS_SCHEMA}],
            )

            response = self.client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            function_calls = []
            if response.function_calls:
                for fc in response.function_calls:
                    function_calls.append({"name": fc.name, "args": fc.args})

            return {"text": response.text or "", "function_calls": function_calls, "provider": f"gemini:{settings.GEMINI_MODEL}"}
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return None


GeminiClient = GeminiAgentClient
ollama_client = OllamaAgentClient()
gemini_client = GeminiAgentClient()
