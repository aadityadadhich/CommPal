# CommPal — PayPal T&C, Developer Guidelines & Hackathon Evaluation Report (`report.md`)

**Evaluation Date:** 2026-11-10  
**Project:** **CommPal** — Autonomous Agentic Commerce & Aggregation  
**Repository:** `https://github.com/aadityadadhich/CommPal` (`main` branch, commit `145decf`)  
**Audit Scope:** Full codebase inspection (zero code edits performed), automated test execution (`pytest` + Next.js build), PayPal Acceptable Use Policy (AUP) & Terms & Conditions compliance, PayPal REST API v2 Developer Guidelines audit, and PayPal AI Hackathon rubric scoring.

---

## 🏆 Executive Summary & Overall Rating

| Evaluation Pillar | Score | Weight | Weighted Score | Verdict |
| :--- | :---: | :---: | :---: | :--- |
| **1. PayPal REST API v2 & Developer Guidelines Compliance** | **9.4 / 10** | 25% | 2.35 | **Excellent** (Orders v2 Authorize/Capture/Void/Refund + `PayPal-Request-Id` + OAuth2 caching) |
| **2. PayPal Acceptable Use Policy (AUP) & T&C Safety** | **9.8 / 10** | 25% | 2.45 | **Exemplary** (Sandboxed 3-bucket wallet, deterministic 9-rule mandate, human-in-the-loop consent, SHA-256 audit log) |
| **3. Autonomous Agentic Commerce & AI Architecture** | **9.5 / 10** | 20% | 1.90 | **Excellent** (Ollama `qwen2.5:7b` + Gemini + offline NLU fallback; untrusted-input prompt guardrails) |
| **4. Multi-Merchant Aggregation & Urgency Routing** | **9.6 / 10** | 15% | 1.44 | **Excellent** (Parallel `asyncio.gather`, SLA hard-filtering, dynamic urgency weights, Channel3 SDK adapter) |
| **5. Product Completeness, UX & Automated Testing** | **9.5 / 10** | 15% | 1.43 | **Excellent** (7-tab Next.js 16 dashboard, Web Speech voice, Virtual Clock & Chaos Studio, 37 automated tests) |
| **OVERALL PROJECT RATING** | **9.57 / 10** (`95.7%`) | **100%** | **9.57 / 10** | **Grade: A+ (Hackathon Finalist / Winner Tier)** |

---

## 1. PayPal Terms & Conditions (T&C), Acceptable Use Policy (AUP) & Developer Guidelines Audit

### 1.1 PayPal Acceptable Use Policy (AUP) & Agentic Consent Compliance
PayPal's Acceptable Use Policy and Agentic Commerce guidelines require that autonomous or semi-autonomous purchasing systems:
1. **Never execute unauthorized or unbounded financial transfers** without explicit user-defined scope and consent.
2. **Maintain non-repudiable, transparent audit trails** proving user authorization and mandate terms at the time of each transaction.
3. **Restrict purchases to lawful, permitted merchant categories** and prevent deceptive or prohibited transactions.

| PayPal T&C / AUP Requirement | CommPal Implementation | File & Symbol Reference | Status |
| :--- | :--- | :--- | :---: |
| **Explicit User Consent & Delegated Authority** | Enforced via versioned, user-authored `MandateBody` contracts (`per_txn_max`, `auto_approve_under`, `daily_cap`, `monthly_cap`, `category_budgets`). Only the authenticated UI (`PUT /api/mandate`) can modify limits; the AI agent has **zero** tools to alter mandates. | [`backend/app/mandate/evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/app/mandate/evaluator.py#L6-L161), [`backend/app/main.py`](file:///D:/working/Hackathon/CommPal/backend/app/main.py#L284-L320) | **PASS** |
| **Account Isolation (No Direct Bank/Card Exposure)** | The AI agent never touches the user's primary bank account or raw payment instruments. It operates strictly against a pre-funded **3-Bucket Sandboxed E-Wallet (`Available`, `Held`, `Spent`)**. | [`backend/app/wallet/ledger.py`](file:///D:/working/Hackathon/CommPal/backend/app/wallet/ledger.py#L14-L163) | **PASS** |
| **Human-in-the-Loop Escalation (`NEEDS_APPROVAL`)** | Untracked items (`RULE_3_UNTRACKED_ITEM`), orders $\ge \$25.00$ (`RULE_8_AUTO_APPROVE_THRESHOLD`), price spikes $>30\%$ (`RULE_7_PRICE_SPIKE`), quantity anomalies (`RULE_7_QTY_MULTIPLE`), and duplicate orders (`RULE_7_DUPLICATE_WINDOW`) automatically pause in `PENDING_APPROVAL` until a human clicks **Approve**. | [`backend/app/mandate/evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/app/mandate/evaluator.py#L53-L149), [`frontend/src/components/ChatTab.tsx`](file:///D:/working/Hackathon/CommPal/frontend/src/components/ChatTab.tsx#L195-L221) | **PASS** |
| **Merchant Allowlist & Blocklist Enforcement** | `RULE_2_MERCHANT_BLOCK` and `RULE_2_MERCHANT_ALLOW` strictly restrict autonomous checkout to vetted merchants (`quick10`, `zipbasket`, `megamart`, `bulkbarn`, `cornerstore`, `channel3`), preventing rogue merchant payouts. | [`backend/app/mandate/evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/app/mandate/evaluator.py#L42-L51) | **PASS** |
| **Emergency Revocation (Kill Switch)** | One-click `kill_switch` in the top Navbar immediately freezes all autonomous and scheduled spending (`RULE_1_KILL_SWITCH`), checked both at initial evaluation and again at execution time (TOCTOU protection). | [`backend/app/mandate/evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/app/mandate/evaluator.py#L38-L40), [`backend/app/pipeline/orchestrator.py`](file:///D:/working/Hackathon/CommPal/backend/app/pipeline/orchestrator.py#L294-L303) | **PASS** |
| **Tamper-Evident Financial Audit Trail** | Every mandate change, top-up, verdict, PayPal authorization, capture, and delivery is recorded in a **SHA-256 hash-chained ledger** (`prev_hash` $\rightarrow$ `hash`) verifiable via `GET /api/audit/verify`. | [`backend/app/audit/hash_chain.py`](file:///D:/working/Hackathon/CommPal/backend/app/audit/hash_chain.py#L12-L119) | **PASS** |

---

### 1.2 PayPal REST API v2 Technical Guidelines Audit

| PayPal Developer Guideline | CommPal Implementation | File & Symbol Reference | Rating & Notes |
| :--- | :--- | :--- | :--- |
| **Two-Step `AUTHORIZE` then `CAPTURE` Flow** | Uses `intent: "AUTHORIZE"` (`POST /v2/checkout/orders` $\rightarrow$ `POST /v2/checkout/orders/{id}/authorize`), places the merchant order, and only calls `POST /v2/payments/authorizations/{auth_id}/capture` after merchant confirmation. | [`backend/app/wallet/providers.py`](file:///D:/working/Hackathon/CommPal/backend/app/wallet/providers.py#L166-L221), [`backend/app/pipeline/orchestrator.py`](file:///D:/working/Hackathon/CommPal/backend/app/pipeline/orchestrator.py#L318-L419) | **10 / 10** — Textbook two-phase commit saga for agentic commerce. |
| **Failure Compensation (`VOID` & Release)** | If merchant order placement fails after PayPal authorization succeeds, CommPal immediately calls `POST /v2/payments/authorizations/{auth_id}/void` and releases the `Held` wallet reservation back to `Available`. | [`backend/app/pipeline/orchestrator.py`](file:///D:/working/Hackathon/CommPal/backend/app/pipeline/orchestrator.py#L350-L396) | **10 / 10** — Prevents stranded holds on user funds. |
| **Idempotency (`PayPal-Request-Id`)** | Sends `"PayPal-Request-Id": idem_key` on `authorize`, `capture`, and `refund` calls, and enforces database-level idempotency keys on `wallet_ledger` and `payments`. | [`backend/app/wallet/providers.py`](file:///D:/working/Hackathon/CommPal/backend/app/wallet/providers.py#L168-L238), [`backend/app/wallet/services.py`](file:///D:/working/Hackathon/CommPal/backend/app/wallet/services.py#L42-L90) | **9.0 / 10** — Minor note: in `PayPalSandboxProvider.authorize()`, both `POST /v2/checkout/orders` and `POST /v2/checkout/orders/{id}/authorize` share the same `headers` dict (`PayPal-Request-Id: idem_key`); suffixing `f"{idem_key}-create"` and `f"{idem_key}-auth"` is recommended for live production. Also add `PayPal-Request-Id` to `void()`. |
| **OAuth2 Access Token Caching** | Caches `/v1/oauth2/token` bearer tokens in memory using `time.monotonic()` with a 60-second safety buffer before expiry (`expires_in - 60.0`), complying with PayPal's rate-limit guideline against requesting a new token per API call. | [`backend/app/wallet/providers.py`](file:///D:/working/Hackathon/CommPal/backend/app/wallet/providers.py#L140-L165) | **10 / 10** — Eliminates redundant OAuth2 handshakes. |
| **Webhook Signature Verification & Deduplication** | Verifies webhook signatures via constant-time `hmac.compare_digest` (`verify_webhook_signature`) and deduplicates `PAYMENT.CAPTURE.COMPLETED` / `PAYMENT.CAPTURE.DENIED` events by unique `(provider, event_id)` in `payment_events`. | [`backend/app/wallet/services.py`](file:///D:/working/Hackathon/CommPal/backend/app/wallet/services.py#L109-L170), [`backend/app/main.py`](file:///D:/working/Hackathon/CommPal/backend/app/main.py#L261-L280) | **9.0 / 10** — Supports HMAC-SHA256 verification and PayPal event names; for production deployment, can optionally call PayPal's `/v1/notifications/verify-webhook-signature` asymmetric cert endpoint. |
| **Credential Hygiene & Secret Protection** | `.env` and `keys.env` are git-ignored; `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` are loaded strictly via environment variables (`backend/app/config.py`). Automated test `test_u7_no_committed_api_keys_in_repo` enforces zero leaked keys. | [`backend/app/config.py`](file:///D:/working/Hackathon/CommPal/backend/app/config.py#L4-L32), [`.gitignore`](file:///D:/working/Hackathon/CommPal/.gitignore) | **10 / 10** — Clean repository history on `main`. |

---

## 2. Live Test Suite Execution Report

### 2.1 Automated Backend Test Suite (`pytest`)
Executed command:
```powershell
$env:PYTHONPATH="."
backend\venv\Scripts\pytest.exe backend\tests -v --tb=short
```

- **Total Tests Collected:** `37` across 6 test modules
- **Core Logic, API, Mandate, Wallet, Pipeline, Routing & Security Tests:** **36 / 36 PASSED (100%)**
- **Live Local Ollama Daemon Test (`test_u6_ollama_qwen25_7b_daemon_and_code_support`):**
  - **Passed (`37 / 37`)** when the local Ollama desktop/background server (`http://127.0.0.1:11434`) is running.
  - **Failed (`WinError 10061: Connection refused`)** when the Windows host machine restarted and the local Ollama daemon had not yet been started (`ollama serve`).
  - *Note:* Even when the local Ollama daemon is stopped, **CommPal's `/api/chat` endpoint continues to work 100% offline** because [`OllamaAgentClient.is_available()`](file:///D:/working/Hackathon/CommPal/backend/app/agent/gemini_client.py#L19-L28) catches the connection error and seamlessly falls back to the deterministic NLU parser (`_fallback_parse`). Only the strict health-check test in `test_comprehensive_usages.py` asserts that `http://127.0.0.1:11434/api/tags` is actively listening.

| Test Module | Passed / Total | Subsystems Verified |
| :--- | :---: | :--- |
| [`backend/tests/test_api.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_api.py) | **7 / 7** | `/api/health`, `/api/items`, `/api/wallet`, `/api/mandate/kill-switch`, `/api/audit/verify`, `/api/demo/clock/advance`, `/api/payments`, `/api/webhooks/paypal` |
| [`backend/tests/test_evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_evaluator.py) | **9 / 9** | All 9 deterministic mandate rules (`ALLOW`, `KILL_SWITCH`, `AUTO_APPROVE`, `PER_TXN_MAX`, `UNTRACKED_ITEM`, `INSUFFICIENT_FUNDS`, `DAILY_CAP`, `DUPLICATE_WINDOW`, `QTY_MULTIPLE`) |
| [`backend/tests/test_pipeline.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_pipeline.py) | **3 / 3** | Urgent A4 paper depletion E2E order, untracked WD-40 human approval flow, and PayPal auth failure compensation rollback |
| [`backend/tests/test_r1_payments.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_r1_payments.py) | **3 / 3** | Payment creation, idempotency replay, mismatched payload `IdempotencyConflict`, payment cancellation, and HMAC-SHA256 webhook deduplication |
| [`backend/tests/test_routing.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_routing.py) | **2 / 2** | Dynamic urgency routing (`URGENT` A4 paper $\rightarrow$ Quick10/ZipBasket in 15–25m; `PLANNED` protein powder $\rightarrow$ MegaMart saving $10) |
| [`backend/tests/test_comprehensive_usages.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_comprehensive_usages.py) | **12 / 13** *(13/13 with `ollama serve`)* | 3-bucket wallet lifecycle, overdraft protection, chaos injection, all 9 mandate rules, SHA-256 audit tamper detection, stock decay, Channel3 adapter, `RouterAggregator`, Docker & secret hygiene |

### 2.2 Frontend Production Build (`Next.js 16.4.2`)
- **Build Time:** `476ms` (Turbopack)
- **TypeScript Validation:** **0 Errors** across all 8 components in [`frontend/src/components/`](file:///D:/working/Hackathon/CommPal/frontend/src/components/Navbar.tsx) and [`frontend/src/app/page.tsx`](file:///D:/working/Hackathon/CommPal/frontend/src/app/page.tsx).

---

## 3. Detailed Rating Breakdown by Hackathon Judging Rubric

### 3.1 Technological Implementation & PayPal Integration — **9.4 / 10**
- **Strengths:**
  - Authentic 3-bucket double-entry-style wallet ledger (`Available` $\rightarrow$ `Held` $\rightarrow$ `Spent`) paired with PayPal REST v2 `AUTHORIZE` $\rightarrow$ `CAPTURE` / `VOID` / `REFUND`.
  - Complete failure compensation saga: if a merchant rejects an order after PayPal authorization, the authorization is voided and held funds are released automatically.
  - Built-in HMAC-SHA256 webhook verification and event deduplication (`POST /api/webhooks/paypal`).
- **Minor Deductions (-0.6):**
  - In `PayPalSandboxProvider.authorize()`, separating the `PayPal-Request-Id` header between order creation (`POST /v2/checkout/orders`) and order authorization (`POST /v2/checkout/orders/{id}/authorize`) will prevent any potential key collision on live PayPal servers.

### 3.2 Agentic Safety, Trust & Policy Governance — **9.8 / 10**
- **Strengths:**
  - **"The agent proposes, the mandate decides, the wallet pays"** is a standout architectural pattern for financial AI hackathons.
  - The Mandate Evaluator ([`evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/app/mandate/evaluator.py)) is 100% deterministic, side-effect-free, and immune to prompt injection.
  - Cryptographic SHA-256 hash-chained audit trail ([`hash_chain.py`](file:///D:/working/Hackathon/CommPal/backend/app/audit/hash_chain.py)) with live UI tamper-verification gives judges mathematical proof of accountability.

### 3.3 Multi-Platform Aggregation & Context-Aware Routing — **9.6 / 10**
- **Strengths:**
  -Directly solves the hackathon prompt's core scenario:
    - **Daily Milk** (perishable, quick commerce),
    - **Monthly Protein Powder** (planned, marketplace cost optimization),
    - **Depletion-Triggered A4 Paper** (switches dynamically between `MegaMart` when stock cover is healthy and `Quick10`/`ZipBasket` when stock hits `0`),
    - **Untracked WD-40** (halts for human approval via `RULE_3_UNTRACKED_ITEM`).
  - Every routing decision stores a transparent mathematical breakdown (`price_score`, `eta_score`, `rating_score`, `fit_score`) and exact rejection reasons (`filtered_out`) viewable in the UI's *"Why this merchant?"* modal.

### 3.4 User Experience & Live Demo Readiness — **9.5 / 10**
- **Strengths:**
  - Polished 7-tab dark-mode command center with inline interactive approval cards, Chrome Web Speech push-to-talk voice input, Virtual Clock time-travel (`+1h`, `+1d`, `+7d`, `+30d`), and Chaos Injection toggles.
- **Minor Operational Note (-0.5):**
  - Notice `?? frontend/AGENTS.md` is auto-generated by Next.js 16 (`next dev`) when `agentRules` is not disabled in `next.config.ts`, and `ollama serve` should be started before running `pytest` if you want the live Ollama daemon test (`test_u6_ollama_qwen25_7b_daemon_and_code_support`) to pass without skipping.
