# Role 2: Policy & Security Engineer (R2)
**Scope:** Deterministic mandate engine, approvals workflow, emergency kill switch, mandate versioning, tamper-evident SHA-256 hash-chained audit log, authentication, and injection red-teaming.  
**Ownership Boundary (SRDD 7.2):** Exposes `evaluate_mandate(intent, decision, wallet_state, mandate) -> Verdict`. Does NOT call the wallet or adapters directly. The mandate evaluator is a pure function without network calls.
