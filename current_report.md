# CommPal — Current Project Status, Usage Test Suite & Diagnostic Report

**Generated:** 2026-11-04  
**Active Branch:** `main` (only remaining branch locally and on `origin`)  
**Local LLM Environment:** Ollama running locally (`http://127.0.0.1:11434`) with `qwen2.5:7b` (`845dbda0ea48`, 4.7 GB) installed and verified.

---

## 1. Branch Consolidation Summary

All team branches have been fetched, merged into `main` while preserving every contributor's work and commit history, pushed to `origin/main`, and all non-`main` branches have been deleted locally and remotely:

| Contributor / Branch | Commit(s) | Work Preserved in `main` | Branch Status |
| :--- | :--- | :--- | :--- |
| **Mainline 7-Role Architecture** | `ec712ba`, `e9acc4c`, `9d09c0c` | Full 7-role SRDD structure (`r1`–`r7`), FastAPI backend, Next.js 16 frontend | Merged in `main` |
| **Milind Mathur** (`milind_dev`) | `e952880` (`17e93ed`) | Payment & webhook deduplication framework (`Payment`, `PaymentEvent`, HMAC SHA-256 verification, idempotency) incorporated in `backend/r1_payments_wallet/` | Merged & branch deleted |
| **Koshal Agarwal** (`feat/docker-infra`) | `f1a398b` (`7f91d25`) | Containerization setup (`Dockerfile`, `docker-compose.yml`, `.dockerignore`) | Merged & branch deleted |
| **Ekansh Tiwari** (`main`) | `91044c9`..`7c56930` | Channel3 product search SDK prototype in `backend/r4_aggregation_router/aggregator.py` | Merged in `main` |
| **Kritika Bhadauria** (`main`) | `9727adb` | Security mandate unit tests for daily cap, insufficient wallet balance, and duplicate order windows in `backend/tests/test_evaluator.py` | Merged in `main` |

---

## 2. Detailed Usage Test Suite Design

We designed and executed a comprehensive usage test suite across **5 test modules** covering all 7 SRDD roles and end-to-end project usages:

1. **[`backend/tests/test_comprehensive_usages.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_comprehensive_usages.py)** *(New — 13 usage & diagnostic tests)*:
   - **Usage 1 (R1 Wallet & Payments):**
     - `test_u1_wallet_three_bucket_lifecycle`: Top-up (`$200`) $\rightarrow$ Reserve (`$30` held) $\rightarrow$ Idempotent reserve replay $\rightarrow$ Settle (`$30` spent) $\rightarrow$ Refund (`$10`).
     - `test_u1_wallet_release_and_overdraft_protection`: Hold release on abort + `InsufficientFundsError` overdraft block.
     - `test_u1_mock_paypal_provider_and_chaos`: `MockPaymentProvider` authorize, capture, refund, and chaos `payment_failure` injection.
   - **Usage 2 (R2 Deterministic 9-Rule Mandate Evaluator):**
     - `test_u2_mandate_all_nine_rules`: Tests Kill-Switch (`RULE_1`), Blocked Merchant (`RULE_2`), Untracked Item (`RULE_3`), Per-Txn Max (`RULE_4`), Daily/Monthly/Category Caps (`RULE_5`), Insufficient Funds (`RULE_6`), Price Spike & Duplicate Window Anomalies (`RULE_7`), Auto-Approve Threshold (`RULE_8`), and Standard Allow (`RULE_9`).
   - **Usage 3 (R2 Cryptographic Audit Hash-Chain):**
     - `test_u3_audit_hash_chain_and_tamper_detection`: Appends sequential SHA-256 chained events, verifies chain integrity, mutates a DB row payload, and verifies tamper detection (`Tampered hash at row 1`).
   - **Usage 4 (R5 Inventory Depletion & Virtual Clock):**
     - `test_u4_inventory_depletion_and_stock_modes`: Virtual clock time-travel (`+12h`), linear consumption decay, confidence decay, and `"finished"` stock mode (`0.0` cover).
   - **Usage 5 (R4 Multi-Merchant Routing & SLA Scoring):**
     - `test_u5_merchant_adapters_and_urgency_scoring`: Queries all 5 merchant adapters (`Quick10`, `ZipBasket`, `MegaMart`, `BulkBarn`, `CornerStore`), derives `URGENT` vs `PLANNED` urgency from slack time, applies hard filters, and verifies quick-commerce selection under urgency.
     - `test_u5_router_aggregator_module_integrity`: Verifies `backend.r4_aggregation_router.aggregator` exports `RouterAggregator` and `router_aggregator`.
   - **Usage 6 (R3 Conversational Agent & Ollama `qwen2.5:7b` Readiness):**
     - `test_u6_agent_module_export_consistency`: Verifies `backend.app.agent.gemini_client` exports cleanly.
     - `test_u6_ollama_qwen25_7b_daemon_and_code_support`: Pings local Ollama HTTP API (`http://127.0.0.1:11434/api/tags`) to confirm `qwen2.5:7b` is installed, and checks if backend `Settings` and `r3_agent_conversation` are wired to use Ollama.
   - **Usage 7 (Infrastructure, Security & Test Hygiene):**
     - `test_u7_docker_infrastructure_files_present`: Checks `Dockerfile`, `docker-compose.yml`, and `.dockerignore`.
     - `test_u7_no_committed_api_keys_in_repo`: Checks for plaintext API keys committed to git.
     - `test_u7_test_evaluator_no_nested_test_functions`: AST check for accidentally nested test functions.
2. **[`backend/tests/test_evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_evaluator.py)** *(7 mandate unit tests)*
3. **[`backend/tests/test_r1_payments.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_r1_payments.py)** *(3 payment & webhook tests)*
4. **[`backend/tests/test_routing.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_routing.py)** *(2 router aggregator E2E tests)*
5. **[`backend/tests/test_pipeline.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_pipeline.py)** *(3 purchase pipeline E2E tests)*
6. **[`backend/tests/test_api.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_api.py)** *(7 FastAPI endpoint integration tests)*

---

## 3. Current Test Execution Results

### Summary Metrics
- **Backend Pytest Suite:** `18 passed, 5 failed, 3 collection errors` (out of 23 collected + 12 blocked by `aggregator.py` import error)
- **Frontend Next.js 16 Build (`npm run build`):** **PASSED** (Turbopack compiled in 678ms, TypeScript typecheck passed in 1.63s, 4/4 static pages generated with 0 errors)
- **Local Ollama Daemon (`http://127.0.0.1:11434`):** **ONLINE** (`qwen2.5:7b` verified present)

### Detailed Test Breakdown

| Test File / Case | Role / Subsystem | Status | Notes |
| :--- | :--- | :--- | :--- |
| `test_comprehensive_usages.py::test_u1_wallet_three_bucket_lifecycle` | R1 Wallet Ledger | ✅ PASSED | 3-bucket reserve/settle/refund & idempotency work |
| `test_comprehensive_usages.py::test_u1_wallet_release_and_overdraft_protection` | R1 Wallet Ledger | ✅ PASSED | Overdraft blocked & hold release works |
| `test_comprehensive_usages.py::test_u1_mock_paypal_provider_and_chaos` | R1 PayPal Provider | ✅ PASSED | Auth/capture/refund & chaos failure work |
| `test_comprehensive_usages.py::test_u2_mandate_all_nine_rules` | R2 Mandate Policy | ✅ PASSED | All 9 deterministic mandate rules verified |
| `test_comprehensive_usages.py::test_u3_audit_hash_chain_and_tamper_detection` | R2 Audit Chain | ✅ PASSED | SHA-256 chain & tamper detection work |
| `test_comprehensive_usages.py::test_u4_inventory_depletion_and_stock_modes` | R5 Inventory & Clock | ✅ PASSED | Virtual clock & depletion math work |
| `test_comprehensive_usages.py::test_u5_merchant_adapters_and_urgency_scoring` | R4 Adapters & Scoring | ✅ PASSED | 5 adapters, hard filters & SLA scoring work |
| `test_comprehensive_usages.py::test_u5_router_aggregator_module_integrity` | R4 Router Aggregator | ❌ FAILED | `aggregator.py` overwritten with Channel3 snippet |
| `test_comprehensive_usages.py::test_u6_agent_module_export_consistency` | R3 Agent Compatibility | ❌ FAILED | `GeminiClient` vs `GeminiAgentClient` name mismatch |
| `test_comprehensive_usages.py::test_u6_ollama_qwen25_7b_daemon_and_code_support` | R3 Ollama `qwen2.5:7b` | ❌ FAILED | Ollama daemon is online, but backend only has Gemini wired |
| `test_comprehensive_usages.py::test_u7_docker_infrastructure_files_present` | R5 Docker Infra | ✅ PASSED | `Dockerfile`, `docker-compose.yml`, `.dockerignore` present |
| `test_comprehensive_usages.py::test_u7_no_committed_api_keys_in_repo` | Security Hygiene | ❌ FAILED | Plaintext key in `backend/r4_aggregation_router/keys.env` |
| `test_comprehensive_usages.py::test_u7_test_evaluator_no_nested_test_functions` | Test Hygiene | ❌ FAILED | `test_insufficient_wallet_balance_denies` nested at line 111 |
| `test_evaluator.py` (7 tests) | R2 Mandate Policy | ✅ PASSED | 7/7 collected tests pass |
| `test_r1_payments.py` (3 tests) | R1 Payments & Webhooks | ✅ PASSED | 3/3 Milind payment & HMAC webhook tests pass |
| `test_routing.py` (2 tests) | R4 Router Aggregator | ⚠️ ERROR | Blocked at import by `channel3_sdk` in `aggregator.py` |
| `test_pipeline.py` (3 tests) | R5 Purchase Pipeline | ⚠️ ERROR | Blocked at import by `channel3_sdk` in `aggregator.py` |
| `test_api.py` (7 tests) | R5 FastAPI Endpoints | ⚠️ ERROR | Blocked at import by `channel3_sdk` in `aggregator.py` |
| `frontend` (`npm run build`) | R6 & R7 Next.js UI | ✅ PASSED | Clean production build & TypeScript check |

---

## 4. Problems Identified in Current `main`

### Problem 1 (Critical Blocker): `backend/r4_aggregation_router/aggregator.py` Was Overwritten
- **Where:** [`backend/r4_aggregation_router/aggregator.py`](file:///D:/working/Hackathon/CommPal/backend/r4_aggregation_router/aggregator.py#L1-L17) (commits `91044c9`..`7c56930`).
- **What Happened:** The `RouterAggregator` class and `router_aggregator` singleton (which orchestrate concurrent merchant searches, urgency derivation, hard filtering, and offer scoring) were replaced with a 17-line top-level test script that runs `from channel3_sdk import Channel3` and searches `"nike"` on import.
- **Impact:**
  1. `channel3_sdk` is not listed in `backend/requirements.txt`, causing `ModuleNotFoundError: No module named 'channel3_sdk'` whenever the FastAPI app, purchase pipeline, or router is imported.
  2. Even if `channel3_sdk` were installed, executing `client.products.search(query="nike")` at module import time makes a blocking live network call on startup and no longer exports `RouterAggregator` or `router_aggregator`, breaking `pipeline.py`, `tools.py`, `test_api.py`, `test_pipeline.py`, and `test_routing.py`.

### Problem 2 (High Priority): Local Ollama (`qwen2.5:7b`) Is Not Yet Wired into R3 Agent
- **Where:** [`backend/app/config.py`](file:///D:/working/Hackathon/CommPal/backend/app/config.py) and [`backend/r3_agent_conversation/gemini_client.py`](file:///D:/working/Hackathon/CommPal/backend/r3_agent_conversation/gemini_client.py).
- **What Happened:** The local Ollama server is running at `http://127.0.0.1:11434` with `qwen2.5:7b` installed, but R3 (`r3_agent_conversation`) is currently written exclusively for `google-genai` (`GEMINI_API_KEY`). Because `GEMINI_API_KEY` is `None`, the agent always drops back to the hardcoded keyword rules in `shopping_agent.py` instead of calling `qwen2.5:7b` via Ollama's tool-calling / chat API.

### Problem 3 (Security Issue): Plaintext API Key Committed in `backend/r4_aggregation_router/keys.env`
- **Where:** [`backend/r4_aggregation_router/keys.env`](file:///D:/working/Hackathon/CommPal/backend/r4_aggregation_router/keys.env) and [`backend/r4_aggregation_router/keys.gitignore`](file:///D:/working/Hackathon/CommPal/backend/r4_aggregation_router/keys.gitignore) (commit `7b69038`).
- **What Happened:** A file named `keys.gitignore` was created instead of adding `keys.env` to `.gitignore`, and `keys.env` containing a plaintext `CHANNEL3_API_KEY` was committed to the repository.

### Problem 4 (Medium): Indentation Bug in `backend/tests/test_evaluator.py`
- **Where:** [`backend/tests/test_evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/tests/test_evaluator.py#L111) (commit `9727adb`).
- **What Happened:** `def test_insufficient_wallet_balance_denies():` is indented 4 spaces inside `test_untracked_item_needs_approval()`, so `pytest` never collects or executes `test_insufficient_wallet_balance_denies` as a test function.

### Problem 5 (Low): Class Name Mismatch in `backend/app/agent/gemini_client.py`
- **Where:** [`backend/app/agent/gemini_client.py`](file:///D:/working/Hackathon/CommPal/backend/app/agent/gemini_client.py#L1) vs [`backend/r3_agent_conversation/gemini_client.py`](file:///D:/working/Hackathon/CommPal/backend/r3_agent_conversation/gemini_client.py#L76).
- **What Happened:** `r3_agent_conversation/gemini_client.py` defines `GeminiAgentClient`, whereas the compatibility re-export `backend/app/agent/gemini_client.py` tries to import `GeminiClient`.

### Problem 6 (Low): `max_qty_multiple` Anomaly Rule Not Checked in `evaluator.py`
- **Where:** [`backend/r2_policy_security_audit/evaluator.py`](file:///D:/working/Hackathon/CommPal/backend/r2_policy_security_audit/evaluator.py#L74-L100).
- **What Happened:** `MandateBody.anomaly.max_qty_multiple` (`2.0`) is defined in the mandate contract and UI, but `evaluate_mandate()` only checks `price_spike_pct` and `duplicate_window_hours`, omitting the `intent_qty > item_reorder_qty * max_qty_multiple` anomaly check.

---

## 5. What Is Left To Do (Action Plan)

1. **Restore `RouterAggregator` & Properly Integrate Channel3 Adapter (R4):**
   - Restore `RouterAggregator` and `router_aggregator` in `backend/r4_aggregation_router/aggregator.py` (from commit `9d09c0c`).
   - Move Ekansh's Channel3 SDK integration into `backend/r4_aggregation_router/adapters.py` as an optional live merchant adapter (guarded by `try: from channel3_sdk import Channel3` and `settings.CHANNEL3_API_KEY`) so it works alongside the 5 mock merchants without breaking offline/test runs.
2. **Integrate Local Ollama (`qwen2.5:7b`) into R3 Conversational Agent (R3):**
   - Add `LLM_PROVIDER: str = "ollama"`, `OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"`, and `OLLAMA_MODEL: str = "qwen2.5:7b"` to `backend/app/config.py`.
   - Implement an Ollama tool-calling client in `backend/r3_agent_conversation/` (using `httpx.AsyncClient` against `/api/chat` with `qwen2.5:7b` native tool support, with Gemini and deterministic fallback as secondary options).
   - Update `/api/health` and the frontend navbar badge to display Ollama (`qwen2.5:7b`) status.
3. **Clean Up Leaked Key & Fix Hygiene Issues:**
   - Remove `backend/r4_aggregation_router/keys.env` and `keys.gitignore` from git tracking, add `*.env` / `keys.env` to root `.gitignore`, and move `CHANNEL3_API_KEY` to `.env.example`.
   - Un-indent `def test_insufficient_wallet_balance_denies():` at line 111 of `backend/tests/test_evaluator.py`.
   - Alias `GeminiClient = GeminiAgentClient` in `backend/r3_agent_conversation/gemini_client.py`.
   - Add the `max_qty_multiple` anomaly rule check to `backend/r2_policy_security_audit/evaluator.py`.
4. **Update Docker Compose for Ollama Host Access (R5):**
   - Add `extra_hosts: ["host.docker.internal:host-gateway"]` and `OLLAMA_BASE_URL=http://host.docker.internal:11434` to `docker-compose.yml` so the containerized backend can talk to the host's Ollama `qwen2.5:7b` instance.
