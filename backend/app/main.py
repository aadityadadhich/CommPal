"""
CommPal FastAPI Application Entrypoint.
Delegates to Role 5 (Platform Orchestrator) while maintaining backward-compatible module path.
"""
from backend.r5_platform_orchestrator.main import app, lifespan

__all__ = ["app", "lifespan"]
