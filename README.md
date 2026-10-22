# CommPal: Autonomous Agentic Commerce & Aggregation
### Built for the PayPal AI Hackathon ("Build What's Next with PayPal and AI")
> *"The agent proposes, the mandate decides, the wallet pays."*

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.12%2B%20%7C%203.13-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-16%2B-black.svg?logo=next.js&logoColor=white)](https://nextjs.org)
[![PayPal](https://img.shields.io/badge/PayPal-Sandbox%20REST%20v2-003087.svg?logo=paypal&logoColor=white)](https://developer.paypal.com)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4.svg?logo=google&logoColor=white)](https://ai.google.dev)

---

## 💡 The Core Problem & Philosophy
Autonomous commerce is only useful if it is **safe to delegate**.
Users are exhausted by repeated household and office restocking chores across dozens of platforms (milk, protein powder, printer paper, lubricants). However, handing an autonomous LLM an unrestricted credit card or bank credentials is a massive security hazard: LLMs can hallucinate, get misled by prompt-injections embedded in product descriptions, or execute runaway orders.

**CommPal solves this with a strict separation of powers:**
1. **The Agent Proposes:** The AI shopping assistant understands natural language and context, queries multiple merchant catalogs, and recommends optimal purchases. The LLM has **zero** access to bank accounts, cannot approve orders, cannot modify limits, and cannot touch payment tokens.
2. **The Mandate Decides:** A pure deterministic policy engine evaluates every proposed purchase against versioned spending caps (per-transaction, daily, monthly), merchant allowlists, and anomaly checks (e.g. price spikes >30%).
3. **The Wallet Pays:** An append-only double-entry e-wallet ledger backed by the **PayPal Developer Sandbox** executes payments using a safe 3-phase flow:
   $$\text{Reserve Ledger Hold} \longrightarrow \text{PayPal Authorize} \longrightarrow \text{Place Merchant Order} \longrightarrow \text{PayPal Capture}$$
   If merchant placement fails, the authorization is voided and funds are released back to the wallet immediately.

---

## 🚀 Key Features & Architectural Innovations

### 1. Urgency-Aware Multi-Merchant Router
Instead of fragile keyword heuristics, urgency is derived mathematically from time slack:
$$\text{Slack} = \text{needed\_by} - \text{current\_time}$$

* **URGENT ($\text{slack} < 2\text{h}$ or Stock $= 0$):** ETA weight $= 0.55$, Price weight $= 0.15$. Quick-commerce merchants (**Quick10**, **ZipBasket**) win for 15–30 minute delivery.
* **ROUTINE ($2\text{h} \le \text{slack} \le 48\text{h}$ or Perishable):** Balanced weights.
* **PLANNED ($\text{slack} > 48\text{h}$):** Price weight $= 0.55$, ETA weight $= 0.10$. Marketplaces (**MegaMart**, **BulkBarn**) win on lowest landed price.
* **Transparent Decision Explanations:** CommPal provides human-readable explanations detailing why the winning merchant was chosen, why the runner-up lost, and which merchants were filtered out.

### 2. Smart Inventory Depletion & Confidence Decay
* **Daily Staples (e.g., Whole Milk 1L):** Automated morning fulfillment slot.
* **Monthly Items (e.g., Whey Protein Powder 1kg):** Automatic monthly schedule.
* **Depletion Triggers (e.g., A4 Copy Paper 500ct, WD-40):** Tracks consumption rates, forecasts days of cover, and models confidence decay. When confidence decays below $0.5$ on shelf-stable goods, CommPal requests user stock verification.

### 3. PayPal Sandbox & Append-Only E-Wallet Ledger
* **Three-Bucket Ledger:** `available`, `held`, and `spent` balances are computed from an insert-only ledger table.
* **Dual Payment Providers:**
  - **Live PayPal Sandbox Provider:** Uses PayPal REST API v2 (`/v1/oauth2/token`, `/v2/checkout/orders` with `AUTHORIZE`, `/v2/payments/authorizations/{id}/capture`, etc.).
  - **High-Fidelity Mock Sandbox Provider:** Built-in simulation with realistic latency, webhook triggers, and failure injection for guaranteed offline reliability during evaluations.

### 4. Cryptographic SHA-256 Hash-Chained Audit Trail
Every system action (user chat, intent generation, router scoring, mandate verdict, ledger reservation, PayPal authorization, merchant delivery) is chained cryptographically:
$$\text{Hash}_n = \text{SHA-256}(\text{Hash}_{n-1} + \text{Timestamp} + \text{Actor} + \text{EventType} + \text{Payload})$$
The UI includes a **"Verify Integrity"** tool that re-hashes the entire sequence on the fly to prove zero post-facto tampering.

### 5. Demo Studio & Virtual Time-Travel
* Fast-forward simulated time ($+1\text{ hour}$, $+1\text{ day}$, $+1\text{ week}$) to demonstrate recurring rules firing autonomously.
* One-click reset to the seeded persona ("**Week with Asha**").
* Chaos injection: Simulate merchant downtime (503 Service Unavailable), stockouts, or PayPal authorization rejection to observe automatic failover and voiding.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons, Web Speech API |
| **Backend** | Python 3.12 / 3.13, FastAPI, Pydantic v2, SQLite / SQLAlchemy 2.0 |
| **Payments** | PayPal Developer Sandbox (Orders & Payments REST v2 APIs) |
| **AI / Agent** | Google Gemini API (`google-genai` SDK) + Deterministic Fallback Parser |
| **Testing** | Pytest, Pytest-AsyncIO, Starlette TestClient (100% core pass rate) |

---

## ⚡ Quickstart & Setup Guide

### 1. Prerequisites
* **Python 3.12+** or **3.13**
* **Node.js v20+** or **v22+** with `npm`

### 2. Backend Setup
```bash
# Navigate to backend and activate virtual environment
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Add your credentials to .env
# Copy .env.example to .env and insert GEMINI_API_KEY or PAYPAL sandbox keys
# If omitted, CommPal seamlessly runs on its high-fidelity mock sandbox and smart fallback parser!

# Seed database with "Week with Asha" scenario
python app/db/seed.py

# Run FastAPI backend server (runs on port 8000)
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
# In a new terminal, navigate to frontend
cd frontend

# Install packages
npm install

# Run Next.js development server (runs on port 3000)
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser (Google Chrome recommended for Web Speech API Push-to-Talk).

### 4. Running Backend Tests
```bash
# Run the complete test suite (evaluator, router, pipeline, API)
pytest backend/tests
```

---

## 🎬 2-Minute 45-Second Demo Walkthrough Script

| Time | Scene | Action & Narration |
| :--- | :--- | :--- |
| **0:00 - 0:25** | **The Dilemma & The Law** | Explain the paradox of autonomous commerce: users want shopping automated, but fear giving an LLM direct credit card access. CommPal's answer: *The agent proposes, the mandate decides, the wallet pays.* |
| **0:25 - 0:55** | **Natural Setup by Chat** | Asha types or speaks: *"I need milk daily, protein powder monthly, and reorder A4 paper when it runs out."* CommPal generates three structured confirmation cards. |
| **0:55 - 1:35** | **Urgent Depletion & Routing** | Asha: *"We're out of A4 paper."* Paper stock is zero ($\text{slack} < 2\text{h}$). Router queries 5 merchants: MegaMart is $\$3.50$ cheaper but takes 2 days; **Quick10** wins on ETA ($18$ mins). Mandate auto-approves ($\$13.98 < \$25$). PayPal authorizes & captures; funds deduct from the e-wallet ledger. |
| **1:35 - 2:05** | **Virtual Time-Travel** | Switch to the **Demo Studio**. Advance the virtual clock by $+1\text{ Day}$. The scheduler automatically triggers the daily milk rule at 7:00 AM with zero human prompt and routes it to Quick-Commerce. |
| **2:05 - 2:25** | **Guardrail Gating & Kill Switch** | Asha requests an untracked item: *"Order WD-40."* Mandate soft ceiling triggers: order pauses in `PENDING_APPROVAL`. Asha approves with one tap. Next, toggle the **EMERGENCY KILL SWITCH** &rarr; all spending is instantly frozen. |
| **2:25 - 2:45** | **Audit Trail & Verification** | Open the **Audit Ledger**. Click **"Verify Integrity"**. The cryptographic engine re-hashes all SHA-256 links, proving zero post-facto tampering. |

---

## 📄 License
This project is licensed under the **Apache-2.0 License**. See [LICENSE](LICENSE) for details.
