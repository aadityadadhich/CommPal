from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "CommPal"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database
    DATABASE_URL: str = "sqlite:///./commpal.db"
    
    # AI / LLM
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    AGENT_MODE: str = "live"  # 'live' or 'cached'
    
    # PayPal Configuration
    PAYPAL_MODE: str = "mock"  # 'mock' or 'sandbox'
    PAYPAL_CLIENT_ID: Optional[str] = None
    PAYPAL_CLIENT_SECRET: Optional[str] = None
    PAYPAL_WEBHOOK_ID: Optional[str] = None
    PAYPAL_API_BASE: str = "https://api-m.sandbox.paypal.com"
    
    # Internal Auth / Secret
    SECRET_KEY: str = "commpal-hackathon-inviolable-secret-key-2026"
    INTERNAL_TICK_TOKEN: str = "tick-secret-token"

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
