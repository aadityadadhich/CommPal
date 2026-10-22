from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Literal

class CardPayload(BaseModel):
    card_type: Literal["order_preview", "rule_created", "approval_needed", "order_status", "decision_explanation"]
    title: str
    subtitle: Optional[str] = None
    data: Dict[str, Any]

class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    cards: Optional[List[CardPayload]] = None
    timestamp: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = "default"
