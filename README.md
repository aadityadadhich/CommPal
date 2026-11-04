# CommPal — Autonomous Agentic Commerce & Aggregation

> **PayPal AI Hackathon Submission**  
> **Core Safety Principle:** *"The agent proposes • The mandate decides • The wallet pays."*

**CommPal** is an autonomous, conversational household & office purchasing assistant that understands natural human language, tracks inventory depletion, compares offers across multiple quick-commerce and standard marketplaces in parallel, enforces a deterministic 9-rule spending mandate, and settles payments exclusively through a **sandboxed PayPal e-wallet** (never touching the user's primary bank account).

---

## 🏗️ Professional Project Structure

All 7 engineering domains from the SRDD have been unified into a clean, modular production layout:

```text
CommPal/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point, CORS, REST & Webhook endpoints
│   │   ├── config.py                # Pydantic v2 Settings (Ollama, Gemini, PayPal, Channel3)
│   │   ├── contracts/               # Shared Pydantic v2 schemas (items, mandate, orders, wallet, chat)
│   │   ├── db/
│   │   │   ├── database.py          # SQLite WAL-mode engine & session management
│   │   │   ├── models.py            # Unified SQLAlchemy 2.0 ORM models
│   │   │   └── seed.py              # "Week with Asha" deterministic demo scenario seeder
│   │   ├── wallet/                  # Role 1: Payments, 3-Bucket Ledger & PayPal Webhooks
│   │   │   ├── ledger.py            # Append-only 3-bucket ledger (Available, Held, Spent)
│   │   │   ├── providers.py         # PayPalSandboxProvider (OAuth2 cached) & MockPaymentProvider
│   │   │   ├── services.py          # Idempotent payment creation, cancellation & HMAC webhooks
│   │   │   └── models.py            # Payment, PaymentEvent & WalletLedger ORM models
│   │   ├── mandate/                 # Role 2: Deterministic Policy Engine
│   │   │   └── evaluator.py         # Pure 9-rule policy engine (ALLOW / NEEDS_APPROVAL / DENY)
│   │   ├── audit/                   # Role 2: Tamper-Evident Cryptographic Ledger
│   │   │   └── hash_chain.py        # SHA-256 hash-chained audit log & chain verifier
│   │   ├── agent/                   # Role 3: Conversational AI & Tool-Calling Engine
│   │   │   ├── gemini_client.py     # Ollama (qwen2.5:7b) primary + Gemini secondary + NLU fallback
│   │   │   ├── shopping_agent.py    # Conversational orchestrator & rich UI card emitter
│   │   │   ├── prompts.py           # Untrusted-input safety guardrails & system prompt
│   │   │   └── tools.py             # 7 read/propose-only agent tool declarations
│   │   ├── merchants/               # Role 4: Multi-Merchant Adapters & Catalogs
│   │   │   ├── adapter.py           # 5 mock merchants + optional Channel3LiveAdapter
│   │   │   └── catalogs.py          # Realistic catalogs + Chaos injection flags
│   │   ├── router/                  # Role 4: Parallel Aggregation & SLA Scoring
│   │   │   ├── aggregator.py        # asyncio.gather fan-out with per-merchant timeout
│   │   │   └── scoring.py           # Urgency derivation, hard filters & transparent scoring
│   │   ├── inventory/               # Role 5: Inventory & Depletion Tracking
│   │   │   └── service.py           # Stock decay, days-of-cover & confidence calculation
│   │   ├── pipeline/                # Role 5: End-to-End Purchase Saga Orchestrator
│   │   │   └── orchestrator.py      # Reserve -> Authorize -> Place -> Capture -> Settle + Compensation
│   │   └── scheduler/               # Role 5: Virtual Time-Travel & Background Tick Worker
│   │       ├── virtual_clock.py     # Controllable virtual clock for live hackathon demos
│   │       └── worker.py            # Recurring rules, depletion triggers & delivery simulation
│   └── tests/                       # Role 2 & Team: 37 automated unit, API & E2E usage tests
├── frontend/
│   └── src/
│       ├── app/                     # Next.js 16 App Router (page.tsx, layout.tsx, globals.css)
│       ├── components/              # Role 6 & Role 7 UI Components
│       │   ├── Navbar.tsx           # Virtual clock controls, Ollama/PayPal badges & Kill Switch
│       │   ├── ChatTab.tsx          # Role 6: Conversational Assistant + Web Speech Voice + Cards
│       │   ├── OverviewTab.tsx      # Role 7: 3-Bucket Wallet, Category Budgets & Approvals
│       │   ├── InventoryTab.tsx     # Role 7: Depletion progress bars & "Ran Out" 1-click trigger
│       │   ├── OrdersTab.tsx        # Role 7: Order lifecycle & "Why this merchant?" modal
│       │   ├── MandateTab.tsx       # Role 7: Live spending limits, merchant rules & anomaly editor
│       │   ├── AuditTab.tsx         # Role 7: Cryptographic SHA-256 hash-chain verifier
│       │   └── DemoStudioTab.tsx    # Role 7: Time-travel controls & Chaos injection studio
│       └── lib/                     # Typed REST API client (api.ts) & contracts (types.ts)
├── Dockerfile                       # Multi-stage non-root Python 3.12 container image
└── docker-compose.yml               # One-command stack with Ollama host-gateway bridge
```

---

## 🔑 API Keys, Dependencies & Configuration Guide

CommPal is engineered to work **100% out-of-the-box offline** using your local **Ollama (`qwen2.5:7b`)** model and the built-in PayPal Sandbox simulator, while supporting drop-in live credentials via `backend/.env`.

### 1. Required Local Installations
| Tool | Version | Purpose | Status |
| :--- | :--- | :--- | :--- |
| **Python** | `3.11+` (`3.13` tested) | FastAPI backend, SQLAlchemy 2.0, Pytest | Installed |
| **Node.js & npm** | `20+` | Next.js 16 + React 19 + Tailwind CSS v4 frontend | Installed |
| **Ollama** | Latest | Local LLM runtime (`http://127.0.0.1:11434`) with `qwen2.5:7b` | Installed & Active |

To ensure Ollama has the model ready:
```bash
ollama pull qwen2.5:7b
ollama serve
```

### 2. Environment Variables (`backend/.env`)
Copy [`backend/.env.example`](file:///D:/working/Hackathon/CommPal/backend/.env.example) to `backend/.env`:

```ini
# Database & Security
DATABASE_URL=sqlite:///./commpal.db
SECRET_KEY=commpal-super-secret-hackathon-key

# Conversational AI Engine (Primary: Local Ollama qwen2.5:7b)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b

# Optional Secondary Cloud LLM Fallback (Google Gemini)
GEMINI_API_KEY=

# Optional Live Product Search Augmentation (Channel3 SDK)
# Leave empty to use the 5 deterministic mock merchants (Quick10, ZipBasket, CornerStore, MegaMart, BulkBarn)
CHANNEL3_API_KEY=

# PayPal Sandbox Configuration
# Set PAYPAL_MODE=mock for instant deterministic demo, or PAYPAL_MODE=sandbox with developer.paypal.com credentials
PAYPAL_MODE=mock
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_API_BASE=https://api-m.sandbox.paypal.com
```

---

## 🚀 Quickstart (Local Development)

### 1. Start the Backend API (`http://localhost:8000`)
```powershell
$env:PYTHONPATH="."
backend\venv\Scripts\uvicorn.exe backend.app.main:app --reload --port 8000
```
- Interactive Swagger UI: `http://localhost:8000/docs`
- Health & Ollama Status Check: `http://localhost:8000/api/health`

### 2. Start the Frontend Dashboard (`http://localhost:3000`)
```powershell
cd frontend
npm run dev
```

### 3. Run with Docker Compose
```bash
docker compose up --build
```

---

## 🧪 Running the Automated Test Suite

Run all 37 unit, integration, mandate policy, payment webhook, routing, and E2E usage tests:

```powershell
$env:PYTHONPATH="."
backend\venv\Scripts\pytest.exe backend\tests -v
```

---

## 🎬 3-Minute PayPal Hackathon Judge Walkthrough ("Week with Asha")

1. **Setup Rules via Natural Language (Assistant Tab):**
   - Click or type: *"I need milk daily, protein powder monthly, and reorder A4 paper when it runs out."*
   - CommPal creates all 3 rules and displays structured confirmation cards.
2. **Urgent Depletion Routing (Quick Commerce vs. Marketplace):**
   - Say: *"We're out of A4 paper."*
   - Stock drops to `0`, urgency becomes `URGENT` (`needed_by = +1h`), and the router filters out slow marketplaces (`MegaMart` 28h ETA) and selects `Quick10` (15m ETA) or `ZipBasket` (25m ETA), settling payment via PayPal Sandbox.
3. **Time-Travel & Planned Purchasing (Navbar / Demo Studio):**
   - Click **`+1d`** on the Virtual Clock in the Navbar.
   - Daily milk auto-orders and delivers; monthly protein powder (`PLANNED` urgency) selects `MegaMart` ($34.99 vs. $44.99 on Quick10), saving $10.00.
4. **Mandate Guardrail & Human-in-the-Loop Approval:**
   - Say: *"Order WD-40."*
   - Because WD-40 is untracked (`RULE_3_UNTRACKED_ITEM`), the deterministic Mandate Evaluator pauses execution (`NEEDS_APPROVAL`) and renders an **Approve / Reject** card in chat.
5. **Emergency Kill Switch & Tamper-Evident Audit Verification:**
   - Toggle **Kill Switch** in the Navbar $\rightarrow$ every subsequent purchase attempt is immediately blocked (`RULE_1_KILL_SWITCH`).
   - Open the **Audit Ledger** tab and click **Verify Hash Chain** to cryptographically validate every event from genesis (`64x '0'`) to the latest transaction.
