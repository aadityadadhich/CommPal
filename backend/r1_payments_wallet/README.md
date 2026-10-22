# Role 1: Payments & Wallet Lead (R1)
**Scope:** PayPal sandbox integration, PaymentProvider protocols, wallet ledger, webhook deduplication, signature verification, refunds, and reconciliation.  
**Ownership Boundary (SRDD 7.2):** Exposes `reserve()`, `authorize()`, `capture()`, `void()`, `refund()`, and `verify_webhook()`. Does NOT call the mandate engine directly; called strictly by the orchestrator (R5).  
**Incorporated Work:** Includes Milind's payment framework from `milind_dev` (`Payment`, `PaymentEvent`, idempotency handling, webhook HMAC signature checking).
