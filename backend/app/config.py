from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CommPal"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # Database
    DATABASE_URL: str = "sqlite:///./commpal.db"

    # Conversational AI (Ollama Primary -> Gemini Secondary -> Deterministic Fallback)
    LLM_PROVIDER: str = "ollama"  # "ollama", "gemini", or "offline"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    AGENT_MODE: str = "live"

    # Live Product Aggregation (Optional Channel3 SDK)
    CHANNEL3_API_KEY: Optional[str] = None

    # PayPal Sandbox / Mock E-Wallet
    PAYPAL_MODE: str = "mock"  # "mock" or "sandbox"
    PAYPAL_CLIENT_ID: Optional[str] = None
    PAYPAL_CLIENT_SECRET: Optional[str] = None
    PAYPAL_WEBHOOK_ID: Optional[str] = None
    PAYPAL_API_BASE: str = "https://api-m.sandbox.paypal.com"

    # Security & Webhook Signing
    SECRET_KEY: str = "commpal-hackathon-inviolable-secret-key-2026"
    INTERNAL_TICK_TOKEN: str = "tick-secret-token"

    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
