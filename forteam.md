# CommPal — Team Guide (`forteam.md`)
**Where Your Code Lives in the Unified Professional Architecture**

We transitioned from the numbered `r1_..r7_` folders to a clean, production-grade software engineering structure (`backend/app/` and `frontend/src/`) while keeping **100% of everyone's code, features, and tests intact**.

This guide maps **each of the 7 SRDD Roles** to its new files, classes, functions, API endpoints, and test suites.

---

## Quick Directory Map (Old $\rightarrow$ New)

| Role | Old Folder | New Canonical Location |
| :--- | :--- | :--- |
| **Role 1 — Payments & Wallet Lead** *(Milind)* | `backend/r1_payments_wallet/` | `backend/app/wallet/` |
| **Role 2 — Policy, Security & Audit Lead** *(Kritika)* | `backend/r2_policy_security_audit/` | `backend/app/mandate/`, `backend/app/audit/`, `backend/tests/` |
| **Role 3 — Agent & Conversation Lead** | `backend/r3_agent_conversation/` | `backend/app/agent/` |
| **Role 4 — Aggregation & Router Lead** *(Ekansh)* | `backend/r4_aggregation_router/` | `backend/app/merchants/`, `backend/app/router/` |
| **Role 5 — Platform, Inventory & Orchestrator** *(Koshal & Lead)* | `backend/r5_platform_orchestrator/` | `backend/app/db/`, `backend/app/inventory/`, `backend/app/pipeline/`, `backend/app/scheduler/`, `backend/app/contracts/`, `backend/app/main.py`, `Dockerfile`, `docker-compose.yml` |
| **Role 6 — Chat & Live Order UI Lead** | `frontend/r6_chat_live_ui/` | `frontend/src/components/ChatTab.tsx`, `frontend/src/lib/` |
| **Role 7 — Dashboard, Policy & Demo Studio Lead** | `frontend/r7_dashboard_demo/` | `frontend/src/components/{Navbar,OverviewTab,InventoryTab,OrdersTab,MandateTab,AuditTab,DemoStudioTab}.tsx`, `frontend/src/app/page.tsx` |

---

## Role 1 — Payments & Wallet Lead *(Milind)*

Your work handles the **3-bucket sandboxed e-wallet ledger (`Available`, `Held`, `Spent`)**, **PayPal Orders v2 (`AUTHORIZE`, `CAPTURE`, `VOID`, `REFUND`)**, **idempotent payment records**, and **HMAC-SHA256 webhook verification & deduplication**.

### Files & Functions
1. **`backend/app/wallet/models.py`** *(from `origin/milind_dev`)*
   - `WalletLedger` — ORM model for the append-only 3-bucket wallet ledger (`wallet_ledger` table).
   - `Payment` — ORM model for payment records with unique `idempotency_key` (`payments` table).
   - `PaymentEvent` — ORM model for deduplicating incoming PayPal webhook events (`payment_events` table).
2. **`backend/app/wallet/services.py`** *(from `origin/milind_dev`)*
   - `create_payment(db, amount, currency, user_id, description, idempotency_key)` — Creates a payment or replays an existing one if `idempotency_key` matches; raises `IdempotencyConflict` (`409`) if parameters differ.
   - `cancel_payment(db, payment_id)` — Cancels a pending payment.
   - `verify_webhook_signature(raw_body, signature_header)` — Constant-time HMAC-SHA256 verification of `PayPal-Transmission-Sig`.
   - `process_provider_event(db, provider_name, payload)` — Deduplicates webhook events by `event_id` and transitions payment state (`succeeded` / `failed`).
3. **`backend/app/wallet/ledger.py`**
   - `LedgerService.get_wallet_summary(db, daily_cap, monthly_cap, kill_switch)` — Computes `available_balance`, `held_balance`, `spent_balance`, `daily_spent`, `monthly_spent`, and `category_spent` (optimized to eliminate N+1 SQL queries).
   - `LedgerService.top_up(db, amount, currency, idem_key, ref_id)` — Credits `available` bucket.
   - `LedgerService.reserve(db, amount, currency, idem_key, ref_id)` — Moves funds from `available` $\rightarrow$ `held` before PayPal authorization.
   - `LedgerService.settle(db, amount, currency, idem_key, ref_id)` — Moves funds from `held` $\rightarrow$ `spent` after PayPal capture.
   - `LedgerService.release(db, amount, currency, idem_key, ref_id)` — Releases `held` $\rightarrow$ `available` if PayPal authorization or merchant placement fails.
   - `LedgerService.refund(db, amount, currency, idem_key, ref_id)` — Returns `spent` $\rightarrow$ `available`.
4. **`backend/app/wallet/providers.py`** (and **`backend/app/wallet/paypal_provider.py`**)
   - `PayPalSandboxProvider` — Live PayPal REST v2 client (`authorize`, `capture`, `void`, `refund`) with OAuth2 bearer token caching.
   - `MockPaymentProvider` — Deterministic offline PayPal simulator with Chaos payment-failure support.
   - `get_active_payment_provider()` — Factory returning `PayPalSandboxProvider` or `MockPaymentProvider` based on `PAYPAL_MODE`.

### API Endpoints (`backend/app/main.py`) & Tests
- `GET /api/wallet`, `POST /api/wallet/top-up`, `POST /api/payments`, `POST /api/payments/{payment_id}/cancel`, `POST /api/webhooks/paypal`
- **Tests:** `backend/tests/test_r1_payments.py` and `test_u1_*` in `backend/tests/test_comprehensive_usages.py`.

---

## Role 2 — Policy, Security & Audit Lead *(Kritika)*

Your work is the **deterministic safety gatekeeper** between the AI agent and the wallet, plus the **cryptographic SHA-256 tamper-evident audit ledger** and the **automated test suite**.

### Files & Functions
1. **`backend/app/mandate/evaluator.py`**
   - `evaluate_mandate(...) -> Verdict` — Pure, side-effect-free function evaluating all **9 deterministic mandate rules** in strict priority order:
     - `RULE_1_KILL_SWITCH` (`DENY` when kill switch is active)
     - `RULE_2_MERCHANT_BLOCK` / `RULE_2_MERCHANT_NOT_ALLOWED` (`DENY` for unauthorized merchants)
     - `RULE_3_UNTRACKED_ITEM` (`NEEDS_APPROVAL` for items not in tracked inventory, e.g., WD-40)
     - `RULE_4_PER_TXN_MAX` (`DENY` if order exceeds `per_txn_max`)
     - `RULE_5_DAILY_CAP` / `RULE_5_MONTHLY_CAP` / `RULE_5_CAT_BUDGET` (`DENY` on budget overflow)
     - `RULE_6_INSUFFICIENT_FUNDS` (`DENY` if `landed_total > available_balance`)
     - `RULE_7_PRICE_SPIKE` (`NEEDS_APPROVAL` if unit price spiked $>30\%$ above recent average)
     - `RULE_7_QTY_MULTIPLE` (`NEEDS_APPROVAL` if `intent_qty > item_reorder_qty * max_qty_multiple`)
     - `RULE_7_DUPLICATE_WINDOW` (`NEEDS_APPROVAL` if ordered within `duplicate_window_hours`)
     - `RULE_8_AUTO_APPROVE_THRESHOLD` (`NEEDS_APPROVAL` if `landed_total > auto_approve_under`)
     - `RULE_9_ALLOW_STANDARD` (`ALLOW`)
2. **`backend/app/audit/hash_chain.py`**
   - `calculate_hash(...)` / `compute_event_hash(...)` — Computes `SHA-256(prev_hash | seq | ts | actor | event_type | entity_type | entity_id | canonical_json(payload) | mandate_version)` starting from genesis `0000...0000` (64 zeros).
   - `append_audit_event(db, actor, event_type, entity_type, entity_id, payload, mandate_version)` — Appends a new hash-chained event to `audit_log`.
   - `verify_audit_chain(db)` — Walks the entire `audit_log` table from `seq=1` to `N` and detects any tampered payload or broken link.

### API Endpoints (`backend/app/main.py`) & Tests
- `GET /api/mandate`, `PUT /api/mandate`, `POST /api/mandate/kill-switch`, `GET /api/audit`, `GET /api/audit/verify`
- **Tests:** `backend/tests/test_evaluator.py` (all 9 unit tests) and `test_u2_*` / `test_u3_*` in `backend/tests/test_comprehensive_usages.py`.

---

## Role 3 — Agent & Conversation Lead

Your work powers the **conversational assistant**, **local Ollama (`qwen2.5:7b`) native tool-calling**, **Google Gemini cloud fallback**, **deterministic offline NLU fallback**, and **prompt-injection guardrails**.

### Files & Functions
1. **`backend/app/agent/gemini_client.py`**
   - `OllamaAgentClient` (`ollama_client`) — Connects to local Ollama (`http://127.0.0.1:11434/api/chat`) using `qwen2.5:7b` (`keep_alive="15m"`), executes multi-turn tool calling, and falls back gracefully if offline.
   - `GeminiAgentClient` (`gemini_client`, aliased as `GeminiClient`) — Secondary cloud LLM client using `gemini-2.5-flash`, automatically delegating to `ollama_client` when `LLM_PROVIDER="ollama"`.
   - `_fallback_parse(user_message)` — Deterministic regex/NLU fallback when neither Ollama nor Gemini is used.
2. **`backend/app/agent/shopping_agent.py`**
   - `ShoppingAgent.process_chat(db, user_message, conversation_id)` — Processes user chat messages, runs fast deterministic handlers for multi-rule setup, stock depletion (`"we're out of paper"`), price comparison, wallet checks, and direct orders, or invokes `OllamaAgentClient` (`qwen2.5:7b`) tool-calling for open-ended conversation, returning `ChatMessage` with rich `CardPayload` UI cards.
3. **`backend/app/agent/tools.py`**
   - `AGENT_TOOLS_SPEC` — OpenAI/Ollama/Gemini-compatible JSON schema declarations for the 7 read/propose-only tools (`get_inventory`, `update_stock`, `create_or_update_rule`, `search_offers`, `request_purchase`, `get_order_status`, `get_wallet_summary`). Notice there is **no** tool to edit the mandate or call PayPal directly.
   - `execute_agent_tool(db, tool_name, args)` — Dispatches LLM tool calls to the backend services.
4. **`backend/app/agent/prompts.py`**
   - `SYSTEM_PROMPT` — Enforces untrusted-input boundaries so merchant titles/descriptions can never trigger prompt-injection or policy changes.

### API Endpoints (`backend/app/main.py`) & Tests
- `POST /api/chat`
- **Tests:** `test_u6_*` in `backend/tests/test_comprehensive_usages.py`.

---

## Role 4 — Aggregation & Router Lead *(Ekansh)*

Your work handles **parallel multi-merchant catalog querying**, **live Channel3 SDK integration**, **dynamic urgency derivation (`URGENT` / `ROUTINE` / `PLANNED`)**, **hard SLA filtering**, and **transparent weighted offer scoring**.

### Files & Functions
1. **`backend/app/merchants/catalogs.py`**
   - `CATALOGS` — Realistic SKU catalogs, pricing, delivery fees, ETAs, and ratings for the 5 built-in merchants:
     - Quick Commerce (10–30 min ETA): `Quick10`, `ZipBasket`, `CornerStore`
     - Standard Marketplace (1–3 day ETA, lower unit prices): `MegaMart`, `BulkBarn`
   - `chaos_flags` & `reset_chaos()` — Runtime chaos injection state (`out_of_stock_items`, `down_merchants`, `slow_merchants`, `price_spikes`, `payment_failure`).
2. **`backend/app/merchants/adapter.py`**
   - `MerchantAdapter` & `MERCHANTS` — Async adapter querying each merchant's catalog (`search`) and placing idempotent merchant orders (`place_order`).
   - `Channel3LiveAdapter` (`channel3_adapter`) — *(Ekansh's Channel3 SDK integration)* Automatically queries live Channel3 product search whenever `CHANNEL3_API_KEY` is set in `backend/.env` and converts results into standard `Offer` objects.
3. **`backend/app/router/scoring.py`**
   - `derive_urgency(needed_by, current_time, stock_qty, user_said_urgent)` — Derives `URGENT` ($\le 3\text{h}$ or `stock_qty <= 0`), `ROUTINE` ($3\text{h}\text{–}48\text{h}$), or `PLANNED` ($>48\text{h}$).
   - `apply_hard_filters(...)` — Filters out offers that fail stock quantity, arrival SLA (`eta > needed_by`), perishable constraints, required brand, minimum rating, or mandate blocked-merchant rules, recording exact rejection reasons in `filtered_out`.
   - `score_and_rank_offers(valid_offers, urgency, spec)` — Computes `price_score`, `eta_score`, `rating_score`, and `fit_score` using urgency-specific weights (`URGENT` weights ETA at `0.50`; `PLANNED` weights Price at `0.55`) and generates a human-readable explanation.
4. **`backend/app/router/aggregator.py`**
   - `RouterAggregator.find_and_decide(...)` (`router_aggregator`) — Queries all 5 mock merchants (plus `channel3_adapter` if enabled) in parallel via `asyncio.gather` with a `1.5s` per-merchant timeout and returns `(Decision, all_offers, filtered_out)`.

### Tests
- `backend/tests/test_routing.py` and `test_u5_*` in `backend/tests/test_comprehensive_usages.py`.

---

## Role 5 — Platform, Inventory & Orchestrator Lead *(Koshal & Lead)*

Your work owns the **SQLite WAL database & ORM models**, **shared Pydantic contracts**, **inventory depletion & confidence decay**, **the end-to-end purchase saga (`PurchasePipeline`)**, **the virtual time-travel clock & scheduler (`TickWorker`)**, **FastAPI routes**, and **Docker containerization**.

### Files & Functions
1. **`backend/app/contracts/schemas.py`** (plus `items.py`, `mandate.py`, `orders.py`, `wallet.py`, `chat.py`)
   - All shared Pydantic v2 request/response contracts across all 7 roles.
2. **`backend/app/db/database.py`**, **`backend/app/db/models.py`**, & **`backend/app/db/seed.py`**
   - `engine`, `SessionLocal`, `get_db()`, `init_db()` — SQLite engine with Write-Ahead Logging (`PRAGMA journal_mode=WAL`).
   - Unified SQLAlchemy ORM models (`ItemModel`, `RuleModel`, `MandateModel`, `OrderIntentModel`, `OfferModel`, `DecisionModel`, `VerdictModel`, `ApprovalModel`, `OrderModel`, `AuditLogModel`, `StockEventModel`, `WalletLedger`, `Payment`, `PaymentEvent`).
   - `seed_week_with_asha(db)` — Seeds the deterministic `"Week with Asha"` hackathon scenario ($200 wallet, Mandate v1, Milk, Protein Powder, A4 Paper, and 3 rules).
3. **`backend/app/inventory/service.py`**
   - `InventoryService.calculate_stock_and_cover(item, current_time)` — Computes decayed stock (`stock_qty - rate_per_day * days_passed`), `days_of_cover`, `stock_confidence`, and `needed_by`.
   - `InventoryService.get_all_items(db)`, `create_item(db, item_in)`, `update_stock(db, item_id, update_req)` (`absolute`, `delta`, and `finished` modes).
4. **`backend/app/pipeline/orchestrator.py`**
   - `PurchasePipeline.request_purchase(db, intent_in, actor)` — Runs the full pre-payment pipeline: resolves item & urgency $\rightarrow$ suppresses duplicate in-flight rule orders (`SCH-6`) $\rightarrow$ calls `router_aggregator.find_and_decide` $\rightarrow$ calls `evaluate_mandate` $\rightarrow$ routes to `DENIED`, `PENDING_APPROVAL`, or `execute_approved_order`.
   - `PurchasePipeline.execute_approved_order(db, intent_id, actor)` — Runs the transactional payment & fulfilment saga with automatic rollback compensation:
     1. TOCTOU re-check of mandate & wallet balance
     2. `ledger_service.reserve` (`Available` $\rightarrow$ `Held`)
     3. `payment_provider.authorize` (PayPal Authorize; releases reserve on failure)
     4. `adapter.place_order` (Merchant order placement; voids PayPal auth & releases reserve on failure)
     5. `payment_provider.capture` & `ledger_service.settle` (`Held` $\rightarrow$ `Spent`)
     6. Creates `OrderModel` (`IN_TRANSIT`) and appends `ORDER_FULFILLED` to the SHA-256 audit log.
5. **`backend/app/scheduler/virtual_clock.py`** & **`backend/app/scheduler/worker.py`**
   - `VirtualClock` (`clock`) — Thread-safe virtual clock supporting `.now()`, `.advance(hours, days, minutes)`, and `.reset()`.
   - `TickWorker.run_tick(db)` (`tick_worker`) — Expires stale approvals, delivers in-transit orders when `now >= created_at + eta_minutes`, fires recurring `daily`/`weekly`/`monthly` rules once per `period_key`, and triggers `depletion` rules when `days_of_cover <= threshold_days`.
6. **`Dockerfile`**, **`docker-compose.yml`**, & **`.dockerignore`** *(Koshal's Docker infrastructure from `origin/feat/docker-infra`)*
   - Multi-stage Python 3.12 container image and Docker Compose stack with `host.docker.internal` bridge for local Ollama (`qwen2.5:7b`).

### Tests
- `backend/tests/test_api.py`, `backend/tests/test_pipeline.py`, and `test_u4_*` / `test_u7_*` in `backend/tests/test_comprehensive_usages.py`.

---

## Role 6 — Chat & Live Order UI Lead

Your work is the **conversational assistant interface**, **Chrome Web Speech API voice input**, and **interactive inline chat cards**.

### Files & Functions
1. **`frontend/src/components/ChatTab.tsx`**
   - `ChatTab` — Full conversational assistant UI with:
     - Push-to-talk voice recognition (`toggleVoice` using `SpeechRecognition` / `webkitSpeechRecognition`).
     - One-click suggested demo prompt chips (`samplePrompts`).
     - `renderCard(card, idx)` — Renders 4 rich interactive card types directly inside the chat stream:
       - `rule_created` (schedule confirmation card)
       - `order_status` (live order card showing Merchant, Total Billed, `PayPal Auth ID`, and `PayPal Capture ID`)
       - `approval_needed` (interactive **Approve / Reject** buttons calling `actOnApproval(intentId, action)`)
       - `order_preview` (multi-merchant price & ETA comparison card)
2. **`frontend/src/lib/api.ts`** & **`frontend/src/lib/types.ts`**
   - `sendChatMessage(message, conversationId)` and `actOnApproval(intentId, action)` typed API helpers and `ChatMessage` / `CardPayload` TypeScript interfaces.

---

## Role 7 — Dashboard, Policy & Demo Studio Lead

Your work is the **command-center shell**, **top navigation bar with virtual clock & emergency kill switch**, and the **6 operational dashboard tabs**.

### Files & Functions
1. **`frontend/src/app/page.tsx`**
   - `Home` — Main 7-tab application shell with parallel state hydration (`Promise.all`) and visibility-aware 5-second live polling.
2. **`frontend/src/components/Navbar.tsx`**
   - `Navbar` — Displays the **Virtual Clock** with **`+1h`**, **`+1d`**, and **Reset** buttons, status badges for **`Ollama (qwen2.5:7b)`** and **`PayPal Sandbox`**, and the one-click **Emergency Kill Switch** (`toggleKillSwitch`).
3. **`frontend/src/components/OverviewTab.tsx`**
   - `OverviewTab` — Displays the **3-Bucket Sandboxed Wallet** (`Available`, `Held`, `Spent`), `$50` instant PayPal Sandbox Top-Up button, Daily/Monthly cap progress bars, Category Budget bars, and Pending Human Approvals queue.
4. **`frontend/src/components/InventoryTab.tsx`**
   - `InventoryTab` — Displays tracked household/office items, depletion progress bars, confidence badges, `+1 Restock`, and the one-click **`"Ran Out"`** depletion trigger (`updateItemStock(id, "finished")`).
5. **`frontend/src/components/OrdersTab.tsx`**
   - `OrdersTab` — Displays the order lifecycle table with PayPal Auth/Capture IDs and the **"Why this merchant?"** decision modal showing the exact weighted score breakdown (`price_score`, `eta_score`, `rating_score`, `fit_score`) and filtered-out merchants.
6. **`frontend/src/components/MandateTab.tsx`**
   - `MandateTab` — Interactive policy editor for `per_txn_max`, `auto_approve_under`, `daily_cap`, `monthly_cap`, `category_budgets`, `anomaly` rules, and `allow_untracked`, saving new immutable mandate versions via `PUT /api/mandate`.
7. **`frontend/src/components/AuditTab.tsx`**
   - `AuditTab` — Displays the chronological `audit_log` ledger with `prev_hash` and `hash` digests and the **Verify Hash Chain** button (`GET /api/audit/verify`).
8. **`frontend/src/components/DemoStudioTab.tsx`**
   - `DemoStudioTab` — Live judge control panel with **Virtual Time-Travel** (`+6 Hours`, `+1 Day`, `+7 Days`, `+30 Days`), **Chaos Injection Toggles** (Out-of-Stock Milk, Down Quick10, Down MegaMart, Simulate PayPal Auth Failure), and the 3-minute judge walkthrough script.
