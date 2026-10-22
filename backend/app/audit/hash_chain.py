from backend.r2_policy_security_audit.hash_chain import (
    GENESIS_HASH, calculate_hash, append_audit_event, verify_audit_chain
)

compute_event_hash = calculate_hash

__all__ = [
    "GENESIS_HASH", "calculate_hash", "compute_event_hash",
    "append_audit_event", "verify_audit_chain"
]
