/* ==========================================================================
   CommPal — Pure Vanilla JavaScript Client Controller (app.js)
   Zero framework overhead, 100% deterministic DOM & REST API integration
   ========================================================================== */

const state = {
  activeTab: "chat",
  wallet: null,
  items: [],
  rules: [],
  orders: [],
  approvals: [],
  mandate: null,
  mandateVersion: 1,
  auditEvents: [],
  auditVerify: { is_valid: true, total_events: 0 },
  clock: null,
  chaos: { payment_failure: false, down_merchants: [] },
  health: null,
  resolvedApprovals: {},
  chatMessages: [
    {
      id: "welcome-1",
      role: "assistant",
      content:
        "Welcome to **CommPal**. Your sandboxed PayPal e-wallet (`$200.00`) and deterministic spending mandate are active.\n\n" +
        "Click any quick command below, type a request in plain English, or use the **Inventory Quick-Trigger** on the right to test autonomous restocking.",
      cards: [],
    },
  ],
};

const ALL_MERCHANTS = ["quick10", "zipbasket", "cornerstore", "megamart", "bulkbarn"];

/* --- Smart API Helper with Same-Origin + Port 8000 Fallback --- */
async function apiCall(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const candidates =
    window.location.port === "8000"
      ? [`/api${path}`, `http://127.0.0.1:8000/api${path}`]
      : [`http://127.0.0.1:8000/api${path}`, `http://localhost:8000/api${path}`];

  let lastErr = null;
  for (const url of candidates) {
    try {
      const resp = await fetch(url, { ...options, headers });
      if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
          const errJson = await resp.json();
          detail = errJson.detail || errJson.message || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      return await resp.json();
    } catch (err) {
      lastErr = err;
      if (err.message && !err.message.includes("Failed to fetch") && !err.message.includes("NetworkError")) {
        throw err;
      }
    }
  }
  throw lastErr || new Error("Backend unreachable");
}

/* --- Toast Notifications --- */
function showToast(message, type = "info") {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `
    <span>${escapeHtml(message)}</span>
    <button class="btn btn-sm" style="padding:2px 6px;" onclick="this.parentElement.remove()">✕</button>
  `;
  stack.appendChild(el);
  setTimeout(() => {
    if (el.parentElement) el.remove();
  }, 4500);
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatMarkdown(text) {
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, '<code class="mono" style="background:var(--bg-elevated);padding:1px 5px;border-radius:4px;color:var(--paypal-cyan);">$1</code>')
    .replace(/\n/g, "<br/>");
}

function fmtMoney(val) {
  const num = Number(val || 0);
  return `$${num.toFixed(2)}`;
}

/* --- Tab Switching --- */
function switchTab(tabId) {
  state.activeTab = tabId;
  document.querySelectorAll(".nav-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `tab-${tabId}`);
  });
}

/* --- Master State Fetch & Render --- */
async function refreshAll() {
  try {
    const [wallet, items, rules, orders, approvals, mandateRes, auditEvents, auditVerify, clockRes, chaosRes, health] =
      await Promise.all([
        apiCall("/wallet"),
        apiCall("/items"),
        apiCall("/rules"),
        apiCall("/orders"),
        apiCall("/approvals"),
        apiCall("/mandate"),
        apiCall("/audit?limit=80"),
        apiCall("/audit/verify"),
        apiCall("/demo/clock"),
        apiCall("/demo/chaos"),
        apiCall("/health"),
      ]);

    state.wallet = wallet;
    state.items = items;
    state.rules = rules;
    state.orders = orders;
    state.approvals = approvals;
    state.mandate = mandateRes.mandate;
    state.mandateVersion = mandateRes.version;
    state.auditEvents = auditEvents;
    state.auditVerify = auditVerify;
    state.clock = clockRes;
    state.chaos = chaosRes;
    state.health = health;

    document.getElementById("offline-banner").classList.remove("show");
    document.getElementById("conn-dot").classList.remove("offline");
    document.getElementById("conn-text").textContent = health.ollama_active
      ? `ONLINE · Ollama (${health.ollama_model})`
      : "ONLINE · Deterministic NLU";

    renderHeader();
    renderChatSidebar();
    renderOverview();
    renderInventoryAndRules();
    renderOrders();
    renderMandate();
    renderAudit();
    renderDemoChaos();
  } catch (err) {
    console.error("Refresh failed:", err);
    document.getElementById("offline-banner").classList.add("show");
    document.getElementById("conn-dot").classList.add("offline");
    document.getElementById("conn-text").textContent = "OFFLINE";
  }
}

/* --- 1. Render Topbar & Alerts --- */
function renderHeader() {
  const w = state.wallet;
  if (!w) return;

  document.getElementById("hdr-avail").textContent = fmtMoney(w.available_balance);
  document.getElementById("hdr-held").textContent = fmtMoney(w.held_balance);
  document.getElementById("hdr-daily").textContent = `$${w.daily_spent.toFixed(0)} / $${w.daily_cap.toFixed(0)}`;

  if (state.clock && state.clock.current_time) {
    const dt = new Date(state.clock.current_time);
    document.getElementById("hdr-clock").textContent = dt.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  const killBanner = document.getElementById("kill-switch-banner");
  const killBtn = document.getElementById("hdr-kill-btn");
  if (w.kill_switch) {
    killBanner.classList.add("show");
    killBtn.textContent = "Kill Switch: FROZEN (Click to Unfreeze)";
    killBtn.className = "btn btn-danger-solid";
  } else {
    killBanner.classList.remove("show");
    killBtn.textContent = "Kill Switch: OFF";
    killBtn.className = "btn btn-danger";
  }

  if (state.health) {
    const modeEl = document.getElementById("header-paypal-mode");
    modeEl.textContent = state.health.paypal_mode === "sandbox" ? "PAYPAL LIVE SANDBOX" : "PAYPAL SANDBOX SIM";
    const llmBadge = document.getElementById("chat-llm-badge");
    if (llmBadge) {
      llmBadge.textContent = state.health.ollama_active
        ? `Ollama ${state.health.ollama_model} + Mandate`
        : "Deterministic NLU + Mandate";
    }
  }

  // Badges
  const appBadge = document.getElementById("badge-approvals");
  if (state.approvals.length > 0) {
    appBadge.style.display = "inline-block";
    appBadge.textContent = state.approvals.length;
  } else {
    appBadge.style.display = "none";
  }
  document.getElementById("badge-items").textContent = state.items.length;
  document.getElementById("badge-orders").textContent = state.orders.length;
}

/* --- 2. Chat Console & Right Sidebar --- */
function renderChatMessages() {
  const container = document.getElementById("chat-messages");
  if (!container) return;

  container.innerHTML = state.chatMessages
    .map((m) => {
      const cardsHtml = (m.cards || []).map((c) => renderActionCard(c)).join("");
      return `
        <div class="msg-row ${m.role === "user" ? "user" : "assistant"}">
          <div class="msg-avatar">${m.role === "user" ? "YOU" : "CP"}</div>
          <div style="max-width:84%;">
            <div class="msg-bubble">${formatMarkdown(m.content)}</div>
            ${cardsHtml}
          </div>
        </div>
      `;
    })
    .join("");

  container.scrollTop = container.scrollHeight;
}

function renderActionCard(card) {
  const d = card.data || {};

  if (card.card_type === "order_status") {
    return `
      <div class="action-card dispatched">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <strong style="color:var(--emerald); font-size:12.5px;">✓ ${escapeHtml(card.title)}</strong>
          <span class="badge badge-green">${ fmtMoney(d.amount) }</span>
        </div>
        <div style="font-size:12px; color:var(--text-secondary); margin-bottom:6px;">
          ${escapeHtml(card.subtitle || "")}
        </div>
        <div class="mono" style="font-size:11px; color:var(--text-muted);">
          PayPal Auth: ${escapeHtml(d.paypal_auth_id || "N/A")} · Capture: ${escapeHtml(d.paypal_capture_id || "N/A")}
        </div>
      </div>
    `;
  }

  if (card.card_type === "approval_needed") {
    const intentId = d.intent_id || "";
    const resolved = state.resolvedApprovals[intentId];
    return `
      <div class="action-card approval">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <strong style="color:var(--amber); font-size:12.5px;">⚠ ${escapeHtml(card.title)}</strong>
          <span class="badge badge-amber">${fmtMoney(d.amount)}</span>
        </div>
        <div style="font-size:12px; color:var(--text-secondary); margin-bottom:10px;">
          Merchant: <strong>${escapeHtml(d.merchant || "Best Offer")}</strong> · Reason: ${escapeHtml(card.subtitle || d.message || "")}
        </div>
        ${
          resolved
            ? `<span class="badge ${resolved === "approved" ? "badge-green" : "badge-red"}">
                 ${resolved === "approved" ? "✓ APPROVED & DISPATCHED" : "✕ REJECTED BY USER"}
               </span>`
            : `<div style="display:flex; gap:8px;">
                 <button class="btn btn-sm btn-success" onclick="handleApproval('${escapeHtml(intentId)}', 'approve')">Approve &amp; Capture Funds</button>
                 <button class="btn btn-sm btn-danger" onclick="handleApproval('${escapeHtml(intentId)}', 'reject')">Reject Order</button>
               </div>`
        }
      </div>
    `;
  }

  if (card.card_type === "order_preview" && Array.isArray(d.offers)) {
    const rows = d.offers
      .map(
        (o) => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:6px 8px; background:var(--bg-panel); border-radius:4px; font-size:12px;">
          <div>
            <strong>${escapeHtml(o.merchant_name)}</strong>
            <span style="color:var(--text-muted); margin-left:6px;">ETA ${o.eta_minutes}m · ★${o.rating}</span>
          </div>
          <div style="display:flex; align-items:center; gap:8px;">
            <span class="mono" style="font-weight:600;">${fmtMoney(o.landed_price)}</span>
          </div>
        </div>
      `
      )
      .join("");
    return `
      <div class="action-card">
        <div style="font-weight:600; font-size:12.5px; margin-bottom:8px;">${escapeHtml(card.title)}</div>
        <div style="display:flex; flex-direction:column; gap:5px;">${rows}</div>
      </div>
    `;
  }

  if (card.card_type === "rule_created") {
    return `
      <div class="action-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong style="color:var(--paypal-cyan); font-size:12.5px;">⟳ ${escapeHtml(card.title)}</strong>
          <span class="badge badge-blue">ACTIVE RULE</span>
        </div>
        <div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">${escapeHtml(card.subtitle || "")}</div>
      </div>
    `;
  }

  return `
    <div class="action-card">
      <div style="font-weight:600; font-size:12.5px;">${escapeHtml(card.title)}</div>
      <div style="font-size:12px; color:var(--text-secondary); margin-top:4px;">${escapeHtml(card.subtitle || d.explanation || "")}</div>
    </div>
  `;
}

function renderChatSidebar() {
  const w = state.wallet;
  if (w) {
    document.getElementById("side-avail").textContent = fmtMoney(w.available_balance);
    document.getElementById("side-held").textContent = fmtMoney(w.held_balance);
    document.getElementById("side-spent").textContent = fmtMoney(w.spent_balance);
    document.getElementById("side-daily-label").textContent = `${fmtMoney(w.daily_spent)} / ${fmtMoney(w.daily_cap)}`;
    const pct = Math.min(100, (w.daily_spent / Math.max(1, w.daily_cap)) * 100);
    document.getElementById("side-daily-bar").style.width = `${pct}%`;
  }

  // Pending Approvals in Sidebar
  const appCard = document.getElementById("sidebar-approvals-card");
  const appList = document.getElementById("sidebar-approvals-list");
  if (state.approvals.length > 0) {
    appCard.style.display = "block";
    document.getElementById("sidebar-approval-count").textContent = state.approvals.length;
    appList.innerHTML = state.approvals
      .map(
        (a) => `
        <div style="background:var(--bg-panel); border:1px solid var(--amber-border); border-radius:6px; padding:10px;">
          <div style="font-weight:600; font-size:12.5px;">${escapeHtml(a.item_name)} (Qty: ${a.qty})</div>
          <div style="font-size:11.5px; color:var(--text-secondary); margin:4px 0 8px;">${escapeHtml(a.explanation)}</div>
          <div style="display:flex; gap:6px;">
            <button class="btn btn-sm btn-success" onclick="handleApproval('${escapeHtml(a.intent_id)}', 'approve')">Approve</button>
            <button class="btn btn-sm btn-danger" onclick="handleApproval('${escapeHtml(a.intent_id)}', 'reject')">Reject</button>
          </div>
        </div>
      `
      )
      .join("");
  } else {
    appCard.style.display = "none";
  }

  // Quick Inventory Depletion List
  const invList = document.getElementById("sidebar-inventory-list");
  invList.innerHTML = state.items
    .map((it) => {
      const low = it.stock_qty <= 0 || it.days_of_cover <= it.threshold_days;
      return `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:8px 10px; background:var(--bg-panel); border:1px solid var(--border-subtle); border-radius:6px;">
          <div>
            <div style="font-weight:600; font-size:12.5px;">${escapeHtml(it.name)}</div>
            <div class="mono" style="font-size:11px; color:${low ? "var(--red)" : "var(--text-secondary)"};">
              Stock: ${it.stock_qty} ${escapeHtml(it.unit)} · ${it.days_of_cover}d cover
            </div>
          </div>
          <div style="display:flex; gap:5px;">
            <button class="btn btn-sm btn-amber" onclick="updateItemStock('${escapeHtml(it.id)}', '${escapeHtml(it.name)}', 'finished', 0)">Deplete (0)</button>
            <button class="btn btn-sm btn-primary" onclick="directOrderItem('${escapeHtml(it.name)}', 1)">Order 1x</button>
          </div>
        </div>
      `;
    })
    .join("");
}

async function handleChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const text = (input.value || "").trim();
  if (!text) return;
  input.value = "";
  await sendChatPrompt(text);
}

async function sendChatPrompt(messageText) {
  switchTab("chat");
  state.chatMessages.push({
    id: `user-${Date.now()}`,
    role: "user",
    content: messageText,
    cards: [],
  });
  renderChatMessages();

  const btn = document.getElementById("chat-send-btn");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Working...";
  }

  try {
    const reply = await apiCall("/chat", {
      method: "POST",
      body: JSON.stringify({ message: messageText, conversation_id: "default" }),
    });
    state.chatMessages.push(reply);
    renderChatMessages();
    await refreshAll();
  } catch (err) {
    state.chatMessages.push({
      id: `err-${Date.now()}`,
      role: "assistant",
      content: `**Error:** ${err.message}`,
      cards: [],
    });
    renderChatMessages();
    showToast(err.message, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Execute";
    }
  }
}

/* --- 3. Overview & Wallet --- */
function renderOverview() {
  const w = state.wallet;
  if (!w) return;

  document.getElementById("ov-avail").textContent = fmtMoney(w.available_balance);
  document.getElementById("ov-held").textContent = fmtMoney(w.held_balance);
  document.getElementById("ov-spent").textContent = fmtMoney(w.spent_balance);
  document.getElementById("ov-orders-count").textContent = `${state.orders.length} autonomous order(s) processed`;

  const statusEl = document.getElementById("ov-audit-status");
  statusEl.textContent = state.auditVerify.is_valid ? "VERIFIED" : "TAMPERED";
  statusEl.style.color = state.auditVerify.is_valid ? "var(--emerald)" : "var(--red)";
  document.getElementById("ov-audit-events").textContent = `${state.auditVerify.total_events || state.auditEvents.length} SHA-256 linked events`;

  // Mandate Caps
  const capsEl = document.getElementById("ov-caps-container");
  const dailyPct = Math.min(100, (w.daily_spent / Math.max(1, w.daily_cap)) * 100);
  const monthlyPct = Math.min(100, (w.monthly_spent / Math.max(1, w.monthly_cap)) * 100);
  const catBudgets = state.mandate?.limits?.category_budgets || { grocery: 150, supplies: 100, fitness: 120 };
  const catSpent = w.category_spent || {};

  let html = `
    <div>
      <div style="display:flex; justify-content:space-between; font-size:12.5px; margin-bottom:5px;">
        <span>Daily Spending Cap</span>
        <span class="mono">${fmtMoney(w.daily_spent)} / ${fmtMoney(w.daily_cap)} (${dailyPct.toFixed(0)}%)</span>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:${dailyPct}%;"></div></div>
    </div>
    <div>
      <div style="display:flex; justify-content:space-between; font-size:12.5px; margin-bottom:5px;">
        <span>Monthly Spending Cap</span>
        <span class="mono">${fmtMoney(w.monthly_spent)} / ${fmtMoney(w.monthly_cap)} (${monthlyPct.toFixed(0)}%)</span>
      </div>
      <div class="progress-track"><div class="progress-fill green" style="width:${monthlyPct}%;"></div></div>
    </div>
  `;

  Object.entries(catBudgets).forEach(([cat, limit]) => {
    const spent = Number(catSpent[cat] || 0);
    const pct = Math.min(100, (spent / Math.max(1, limit)) * 100);
    html += `
      <div>
        <div style="display:flex; justify-content:space-between; font-size:12px; color:var(--text-secondary); margin-bottom:4px;">
          <span style="text-transform:capitalize;">Category: ${escapeHtml(cat)}</span>
          <span class="mono">${fmtMoney(spent)} / ${fmtMoney(limit)}</span>
        </div>
        <div class="progress-track"><div class="progress-fill amber" style="width:${pct}%;"></div></div>
      </div>
    `;
  });
  capsEl.innerHTML = html;

  // Recent Orders
  const recEl = document.getElementById("ov-recent-orders");
  if (state.orders.length === 0) {
    recEl.innerHTML = `<div style="color:var(--text-muted); font-size:12.5px; padding:14px 0;">No orders placed yet. Trigger a depletion or send a chat command!</div>`;
  } else {
    recEl.innerHTML = state.orders
      .slice(0, 5)
      .map(
        (o) => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 12px; background:var(--bg-panel); border:1px solid var(--border-subtle); border-radius:6px;">
          <div>
            <div style="font-weight:600; font-size:13px;">${escapeHtml(o.item_name)} &times; ${o.qty}</div>
            <div style="font-size:11.5px; color:var(--text-secondary);">
              ${escapeHtml(o.merchant_name)} · ETA ${o.eta_minutes}m · <span class="mono">${escapeHtml(o.paypal_capture_id || "")}</span>
            </div>
          </div>
          <div style="text-align:right;">
            <div class="mono" style="font-weight:600;">${fmtMoney(o.amount)}</div>
            <span class="badge ${o.state === "DELIVERED" ? "badge-green" : "badge-blue"}">${escapeHtml(o.state)}</span>
          </div>
        </div>
      `
      )
      .join("");
  }
}

async function topUpWallet(amount) {
  try {
    await apiCall("/wallet/top-up", {
      method: "POST",
      body: JSON.stringify({ amount: Number(amount), currency: "USD", payment_method: "paypal_sandbox" }),
    });
    showToast(`Credited ${fmtMoney(amount)} to PayPal Sandbox Wallet`, "success");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function topUpCustom() {
  const inp = document.getElementById("custom-topup-input");
  const val = parseFloat(inp.value);
  if (!val || val <= 0) {
    showToast("Enter a valid positive dollar amount", "warning");
    return;
  }
  inp.value = "";
  await topUpWallet(val);
}

/* --- 4. Inventory & Rules --- */
function renderInventoryAndRules() {
  const tbody = document.getElementById("inventory-tbody");
  tbody.innerHTML = state.items
    .map((it) => {
      const isZero = it.stock_qty <= 0;
      const isLow = it.days_of_cover <= it.threshold_days;
      const badgeClass = isZero ? "badge-red" : isLow ? "badge-amber" : "badge-green";
      return `
        <tr>
          <td>
            <div style="font-weight:600;">${escapeHtml(it.name)}</div>
            <span class="badge" style="margin-top:3px;">${escapeHtml(it.category)}</span>
          </td>
          <td class="mono" style="font-weight:600;">
            ${it.stock_qty} ${escapeHtml(it.unit)}
          </td>
          <td class="mono" style="color:var(--text-secondary);">
            ${it.burn_rate_per_day}/day
          </td>
          <td>
            <span class="badge ${badgeClass}">${it.days_of_cover} days</span>
          </td>
          <td class="mono">
            ${Math.round((it.stock_confidence || 1) * 100)}%
          </td>
          <td style="text-align:right;">
            <div style="display:inline-flex; gap:6px; flex-wrap:wrap; justify-content:flex-end;">
              <button class="btn btn-sm" onclick="updateItemStock('${escapeHtml(it.id)}', '${escapeHtml(it.name)}', 'delta', -1)">-1</button>
              <button class="btn btn-sm" onclick="updateItemStock('${escapeHtml(it.id)}', '${escapeHtml(it.name)}', 'delta', 1)">+1</button>
              <button class="btn btn-sm btn-amber" onclick="updateItemStock('${escapeHtml(it.id)}', '${escapeHtml(it.name)}', 'finished', 0)">Out of Stock (Auto-Order)</button>
              <button class="btn btn-sm btn-primary" onclick="directOrderItem('${escapeHtml(it.name)}', ${it.reorder_qty || 1})">Order Now</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");

  const rulesGrid = document.getElementById("rules-grid");
  if (state.rules.length === 0) {
    rulesGrid.innerHTML = `<div style="color:var(--text-muted); font-size:12.5px;">No rules configured yet.</div>`;
  } else {
    rulesGrid.innerHTML = state.rules
      .map(
        (r) => `
        <div style="background:var(--bg-panel); border:1px solid var(--border-subtle); border-radius:6px; padding:12px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <strong style="font-size:13px;">${escapeHtml(r.item_name)}</strong>
            <span class="badge badge-blue" style="text-transform:uppercase;">${escapeHtml(r.type)}</span>
          </div>
          <div class="mono" style="font-size:11.5px; color:var(--text-secondary);">
            Reorder Qty: ${r.qty} · Last Fired: ${escapeHtml(r.last_period_key || "Never")}
          </div>
        </div>
      `
      )
      .join("");
  }
}

function fillItemPreset(name, category, unit, stock, burn, threshold, price) {
  document.getElementById("new-item-name").value = name;
  document.getElementById("new-item-cat").value = category;
  document.getElementById("new-item-unit").value = unit;
  document.getElementById("new-item-stock").value = stock;
  document.getElementById("new-item-burn").value = burn;
}

async function handleCreateItem(e) {
  e.preventDefault();
  const name = document.getElementById("new-item-name").value.trim();
  const category = document.getElementById("new-item-cat").value;
  const unit = document.getElementById("new-item-unit").value.trim() || "unit";
  const stock_qty = parseFloat(document.getElementById("new-item-stock").value || "2");
  const burn_rate_per_day = parseFloat(document.getElementById("new-item-burn").value || "0.5");

  if (!name) return;
  try {
    await apiCall("/items", {
      method: "POST",
      body: JSON.stringify({
        name,
        category,
        unit,
        stock_qty,
        burn_rate_per_day,
        threshold_days: 2.0,
        reorder_qty: 1.0,
        last_price: 9.99,
      }),
    });
    document.getElementById("new-item-name").value = "";
    showToast(`Tracked "${name}" with active depletion rule`, "success");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function updateItemStock(itemId, itemName, mode, qty) {
  try {
    const res = await apiCall(`/items/${itemId}/stock`, {
      method: "POST",
      body: JSON.stringify({ mode, qty, reason: "UI stock control" }),
    });
    if (res.triggered_order) {
      const ord = res.triggered_order;
      if (ord.status === "ORDER_PLACED") {
        showToast(
          `Depletion Triggered! Ordered ${itemName} from ${ord.merchant} (${fmtMoney(ord.amount)}, ETA ${ord.eta_minutes}m)`,
          "success"
        );
      } else {
        showToast(`Depletion Triggered for ${itemName}: ${ord.status} — ${ord.message || ""}`, "warning");
      }
    } else {
      showToast(`Updated ${itemName} stock to ${res.stock_qty} ${res.unit}`, "info");
    }
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function directOrderItem(itemName, qty = 1) {
  try {
    const res = await apiCall("/orders/purchase", {
      method: "POST",
      body: JSON.stringify({
        item_name: itemName,
        qty: Number(qty),
        source: "chat",
        urgency_hint: "routine",
      }),
    });
    if (res.status === "ORDER_PLACED") {
      showToast(
        `Order Placed: ${itemName} via ${res.merchant} (${fmtMoney(res.amount)}, PayPal Capture ${res.paypal_capture_id})`,
        "success"
      );
    } else if (res.status === "PENDING_APPROVAL") {
      showToast(`Approval Required for ${itemName}: ${res.message}`, "warning");
    } else {
      showToast(`Order Denied: ${res.message}`, "error");
    }
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function runSchedulerTick() {
  try {
    const res = await apiCall("/demo/clock/advance?minutes=5", { method: "POST" });
    const tr = res.tick_result || {};
    showToast(
      `Scheduler Tick Complete: ${tr.rules_fired || 0} rule(s) fired, ${tr.orders_delivered || 0} order(s) delivered`,
      "success"
    );
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

/* --- 5. Orders & Routing Breakdown Modal --- */
function renderOrders() {
  const tbody = document.getElementById("orders-tbody");
  if (state.orders.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:28px;">No autonomous orders placed yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.orders
    .map(
      (o) => `
      <tr>
        <td class="mono" style="font-size:12px;">#${escapeHtml(o.id.slice(-8))}</td>
        <td>
          <strong>${escapeHtml(o.item_name)}</strong>
          <span class="mono" style="color:var(--text-secondary); margin-left:4px;">&times;${o.qty}</span>
        </td>
        <td>
          <strong>${escapeHtml(o.merchant_name)}</strong>
          <div style="font-size:11px; color:var(--text-muted);">ETA ${o.eta_minutes} mins</div>
        </td>
        <td class="mono" style="font-weight:600;">${fmtMoney(o.amount)}</td>
        <td class="mono" style="font-size:11px;">
          <div>Auth: <span style="color:var(--paypal-cyan);">${escapeHtml(o.paypal_auth_id || "—")}</span></div>
          <div>Cap: <span style="color:var(--emerald);">${escapeHtml(o.paypal_capture_id || "—")}</span></div>
        </td>
        <td>
          <span class="badge ${o.state === "DELIVERED" ? "badge-green" : "badge-blue"}">${escapeHtml(o.state)}</span>
        </td>
        <td style="text-align:right;">
          <button class="btn btn-sm btn-primary" onclick="openDecisionModal('${escapeHtml(o.id)}')">Score Breakdown</button>
        </td>
      </tr>
    `
    )
    .join("");
}

async function openDecisionModal(orderId) {
  try {
    const detail = await apiCall(`/orders/${orderId}`);
    const ord = detail.order;
    const dec = detail.decision || {};
    document.getElementById("dec-modal-title").textContent = `Order #${ord.id.slice(-8)} — ${ord.item_name} (${ord.merchant_name})`;
    document.getElementById("dec-modal-sub").textContent = dec.explanation || "Multi-merchant deterministic utility scoring";

    const scores = dec.score_breakdown || [];
    const filtered = dec.filtered_out || {};

    const scoresRows = scores
      .map(
        (s, idx) => `
        <tr>
          <td>
            <strong>${escapeHtml(s.merchant_id.toUpperCase())}</strong>
            ${idx === 0 ? '<span class="badge badge-green" style="margin-left:6px;">WINNER</span>' : ""}
          </td>
          <td class="mono">${(s.price_score * 100).toFixed(1)}</td>
          <td class="mono">${(s.eta_score * 100).toFixed(1)}</td>
          <td class="mono">${(s.rating_score * 100).toFixed(1)}</td>
          <td class="mono">${(s.fit_score * 100).toFixed(1)}</td>
          <td class="mono" style="font-weight:700; color:var(--paypal-cyan);">${(s.total_score * 100).toFixed(1)}</td>
        </tr>
      `
      )
      .join("");

    const filteredEntries = Object.entries(filtered);
    const filteredHtml =
      filteredEntries.length === 0
        ? `<div style="font-size:12px; color:var(--text-muted);">No merchants disqualified by hard SLA/mandate filters.</div>`
        : filteredEntries
            .map(
              ([m, reason]) => `
              <div style="display:flex; justify-content:space-between; padding:6px 10px; background:var(--red-bg); border:1px solid var(--red-border); border-radius:4px; font-size:12px;">
                <strong style="color:var(--red);">${escapeHtml(m)}</strong>
                <span>${escapeHtml(reason)}</span>
              </div>
            `
            )
            .join("");

    document.getElementById("dec-modal-body").innerHTML = `
      <div style="margin-bottom:14px;">
        <div class="metric-label" style="margin-bottom:8px;">Candidate Score Breakdown (0 – 100 Utility Scale)</div>
        <div class="table-wrap" style="border:1px solid var(--border-subtle); border-radius:6px;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Merchant</th>
                <th>Price Score</th>
                <th>ETA Score</th>
                <th>Rating Score</th>
                <th>Spec Fit</th>
                <th>Total Utility</th>
              </tr>
            </thead>
            <tbody>${scoresRows}</tbody>
          </table>
        </div>
      </div>
      <div>
        <div class="metric-label" style="margin-bottom:8px;">Disqualified / Filtered-Out Offers</div>
        <div style="display:flex; flex-direction:column; gap:6px;">${filteredHtml}</div>
      </div>
    `;
    document.getElementById("decision-modal").classList.add("open");
  } catch (err) {
    showToast(err.message, "error");
  }
}

function closeDecisionModal() {
  document.getElementById("decision-modal").classList.remove("open");
}

/* --- 6. Approvals Handler --- */
async function handleApproval(intentId, action) {
  try {
    state.resolvedApprovals[intentId] = action === "approve" ? "approved" : "rejected";
    renderChatMessages();

    const res = await apiCall(`/orders/${intentId}/action`, {
      method: "POST",
      body: JSON.stringify({ action, reason: `User ${action}d via console` }),
    });

    if (action === "approve") {
      showToast(
        `Approved! Settled ${fmtMoney(res.amount || 0)} with ${res.merchant || "merchant"} (${res.paypal_capture_id || "captured"})`,
        "success"
      );
    } else {
      showToast("Order proposal rejected", "warning");
    }
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

/* --- 7. Mandate Policy Editor --- */
function renderMandate() {
  const m = state.mandate;
  if (!m) return;

  document.getElementById("mandate-version-badge").textContent = `v${state.mandateVersion}`;
  document.getElementById("m-auto-approve").value = m.limits.auto_approve_under;
  document.getElementById("m-per-txn").value = m.limits.per_txn_max;
  document.getElementById("m-daily-cap").value = m.limits.daily_cap;
  document.getElementById("m-monthly-cap").value = m.limits.monthly_cap;

  const cats = m.limits.category_budgets || {};
  document.getElementById("m-cat-grocery").value = cats.grocery ?? 150;
  document.getElementById("m-cat-supplies").value = cats.supplies ?? 100;
  document.getElementById("m-cat-fitness").value = cats.fitness ?? 120;
  document.getElementById("m-allow-untracked").checked = Boolean(m.items?.allow_untracked);

  document.getElementById("m-spike-pct").value = m.anomalies.max_price_spike_pct;
  document.getElementById("m-qty-mult").value = m.anomalies.max_qty_multiple;
  document.getElementById("m-dup-hours").value = m.anomalies.duplicate_window_hours;

  const allowed = new Set(m.merchants?.allowlist || ALL_MERCHANTS);
  document.getElementById("m-merchants-boxes").innerHTML = ALL_MERCHANTS.map(
    (merch) => `
      <label class="badge" style="cursor:pointer; padding:5px 8px;">
        <input type="checkbox" class="merch-allow-cb" value="${merch}" ${allowed.has(merch) ? "checked" : ""} />
        <span>${merch}</span>
      </label>
    `
  ).join("");
}

async function saveMandate() {
  const m = state.mandate;
  if (!m) return;

  const allowlist = Array.from(document.querySelectorAll(".merch-allow-cb:checked")).map((cb) => cb.value);

  const payload = {
    version: state.mandateVersion + 1,
    kill_switch: Boolean(m.kill_switch),
    limits: {
      per_txn_max: parseFloat(document.getElementById("m-per-txn").value || "60"),
      auto_approve_under: parseFloat(document.getElementById("m-auto-approve").value || "25"),
      daily_cap: parseFloat(document.getElementById("m-daily-cap").value || "80"),
      monthly_cap: parseFloat(document.getElementById("m-monthly-cap").value || "400"),
      category_budgets: {
        grocery: parseFloat(document.getElementById("m-cat-grocery").value || "150"),
        supplies: parseFloat(document.getElementById("m-cat-supplies").value || "100"),
        fitness: parseFloat(document.getElementById("m-cat-fitness").value || "120"),
      },
    },
    merchants: {
      allowlist,
      blocklist: m.merchants?.blocklist || [],
    },
    items: {
      allow_untracked: document.getElementById("m-allow-untracked").checked,
    },
    anomalies: {
      max_price_spike_pct: parseFloat(document.getElementById("m-spike-pct").value || "20"),
      max_qty_multiple: parseFloat(document.getElementById("m-qty-mult").value || "2"),
      duplicate_window_hours: parseInt(document.getElementById("m-dup-hours").value || "12", 10),
    },
  };

  try {
    const res = await apiCall("/mandate", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    showToast(`Saved Mandate Policy v${res.version} to Audit Log`, "success");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function toggleKillSwitch(forceState) {
  const current = Boolean(state.wallet?.kill_switch);
  const next = typeof forceState === "boolean" ? forceState : !current;
  try {
    await apiCall("/mandate/kill-switch", {
      method: "POST",
      body: JSON.stringify({ active: next, reason: next ? "Emergency freeze from console" : "Unfrozen by user" }),
    });
    showToast(next ? "KILL SWITCH ENGAGED: All autonomous orders frozen" : "Kill Switch disengaged: Agent active", next ? "error" : "success");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

/* --- 8. Audit Hash Chain --- */
function renderAudit() {
  const v = state.auditVerify;
  const titleEl = document.getElementById("audit-banner-title");
  if (v && v.is_valid) {
    titleEl.textContent = `✓ SHA-256 Cryptographic Hash Chain Verified (${v.total_events || state.auditEvents.length} Events)`;
    titleEl.style.color = "var(--emerald)";
  } else {
    titleEl.textContent = "✕ TAMPER DETECTED IN AUDIT HASH CHAIN";
    titleEl.style.color = "var(--red)";
  }

  const tbody = document.getElementById("audit-tbody");
  tbody.innerHTML = state.auditEvents
    .map((ev) => {
      const payloadStr = JSON.stringify(ev.payload || {});
      return `
        <tr>
          <td class="mono">#${ev.id}</td>
          <td class="mono" style="font-size:11.5px; color:var(--text-secondary);">${new Date(ev.ts).toLocaleTimeString()}</td>
          <td><span class="badge">${escapeHtml(ev.actor)}</span></td>
          <td><strong class="mono" style="font-size:12px; color:var(--paypal-cyan);">${escapeHtml(ev.event_type)}</strong></td>
          <td class="mono" style="font-size:11.5px;">${escapeHtml(ev.entity_type)}:${escapeHtml((ev.entity_id || "").slice(-8))}</td>
          <td class="mono" style="font-size:11px; color:var(--text-secondary); max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(payloadStr)}">
            ${escapeHtml(payloadStr)}
          </td>
          <td class="mono" style="font-size:11px; color:var(--emerald);">
            ${escapeHtml((ev.prev_hash || "").slice(0, 8))} &rarr; ${escapeHtml((ev.hash || "").slice(0, 10))}
          </td>
        </tr>
      `;
    })
    .join("");
}

async function verifyAuditChainNow() {
  try {
    const res = await apiCall("/audit/verify");
    state.auditVerify = res;
    renderAudit();
    showToast(
      res.is_valid
        ? `SHA-256 Integrity Verified across all ${res.total_events} audit records`
        : `Tampering detected at event #${res.broken_at_id}`,
      res.is_valid ? "success" : "error"
    );
  } catch (err) {
    showToast(err.message, "error");
  }
}

/* --- 9. Demo Studio, Virtual Clock & Chaos --- */
function renderDemoChaos() {
  const c = state.chaos || {};
  const payBtn = document.getElementById("chaos-pay-btn");
  if (payBtn) {
    payBtn.textContent = c.payment_failure ? "ACTIVE (FAIL NEXT ORDER)" : "OFF";
    payBtn.className = c.payment_failure ? "btn btn-sm btn-danger-solid" : "btn btn-sm";
  }

  const q10Down = (c.down_merchants || []).includes("quick10");
  const q10Btn = document.getElementById("chaos-q10-btn");
  if (q10Btn) {
    q10Btn.textContent = q10Down ? "OFFLINE (FAILOVER ACTIVE)" : "ONLINE";
    q10Btn.className = q10Down ? "btn btn-sm btn-danger-solid" : "btn btn-sm btn-success";
  }
}

async function advanceClock(hours = 0, days = 0) {
  try {
    const res = await apiCall(`/demo/clock/advance?hours=${hours}&days=${days}`, { method: "POST" });
    const tr = res.tick_result || {};
    showToast(
      `Advanced Clock (+${days}d ${hours}h): ${tr.rules_fired || 0} rule(s) fired, ${tr.orders_delivered || 0} order(s) delivered`,
      "success"
    );
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function resetDemo() {
  try {
    await apiCall("/demo/reset", { method: "POST" });
    state.resolvedApprovals = {};
    showToast('Reset to clean "Week with Asha" baseline ($200.00 wallet)', "success");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function toggleChaosPaymentFailure() {
  try {
    const next = !Boolean(state.chaos?.payment_failure);
    await apiCall("/demo/chaos", {
      method: "POST",
      body: JSON.stringify({ payment_failure: next }),
    });
    showToast(next ? "PayPal Capture Failure Simulation ENABLED" : "PayPal Capture Failure Simulation DISABLED", next ? "warning" : "info");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function toggleChaosMerchant(merchantId) {
  try {
    await apiCall("/demo/chaos", {
      method: "POST",
      body: JSON.stringify({ down_merchant: merchantId }),
    });
    showToast(`Toggled ${merchantId} availability`, "info");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function runDemoScenario(scenarioKey) {
  if (scenarioKey === "paper_stockout") {
    await sendChatPrompt("We ran out of A4 paper");
  } else if (scenarioKey === "wd40_approval") {
    await sendChatPrompt("Order WD-40");
  } else if (scenarioKey === "advance_24h") {
    await advanceClock(0, 1);
  }
}

/* --- 10. Live .env Configuration Modal --- */
async function openEnvModal() {
  try {
    const cfg = await apiCall("/config/env");
    document.getElementById("env-paypal-mode").value = cfg.PAYPAL_MODE || "mock";
    document.getElementById("env-llm-provider").value = cfg.LLM_PROVIDER || "ollama";
    document.getElementById("env-paypal-id").value = cfg.PAYPAL_CLIENT_ID || "";
    document.getElementById("env-paypal-secret").value = cfg.PAYPAL_CLIENT_SECRET || "";
    document.getElementById("env-ollama-url").value = cfg.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
    document.getElementById("env-ollama-model").value = cfg.OLLAMA_MODEL || "qwen2.5:7b";
    document.getElementById("env-gemini-key").value = cfg.GEMINI_API_KEY || "";
    document.getElementById("env-channel3-key").value = cfg.CHANNEL3_API_KEY || "";
  } catch (_) {}
  document.getElementById("env-modal").classList.add("open");
}

function closeEnvModal() {
  document.getElementById("env-modal").classList.remove("open");
}

async function saveEnvConfig(e) {
  e.preventDefault();
  const payload = {
    PAYPAL_MODE: document.getElementById("env-paypal-mode").value,
    LLM_PROVIDER: document.getElementById("env-llm-provider").value,
    PAYPAL_CLIENT_ID: document.getElementById("env-paypal-id").value.trim(),
    PAYPAL_CLIENT_SECRET: document.getElementById("env-paypal-secret").value.trim(),
    OLLAMA_BASE_URL: document.getElementById("env-ollama-url").value.trim(),
    OLLAMA_MODEL: document.getElementById("env-ollama-model").value.trim(),
    GEMINI_API_KEY: document.getElementById("env-gemini-key").value.trim(),
    CHANNEL3_API_KEY: document.getElementById("env-channel3-key").value.trim(),
  };

  try {
    await apiCall("/config/env", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    closeEnvModal();
    showToast("Saved API keys to .env and reloaded runtime configuration", "success");
    await refreshAll();
  } catch (err) {
    showToast(err.message, "error");
  }
}

/* --- Boot Application --- */
window.addEventListener("DOMContentLoaded", () => {
  renderChatMessages();
  refreshAll();
  setInterval(refreshAll, 6000);
});
