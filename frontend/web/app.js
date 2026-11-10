/* ==========================================================================
   CommPal — Simple 3-Column Smart Shopping & PayPal Assistant (app.js)
   ========================================================================== */

const state = {
  wallet: null,
  items: [],
  orders: [],
  approvals: [],
  mandate: null,
  mandateVersion: 1,
  auditEvents: [],
  auditVerify: { is_valid: true, events_count: 0 },
  health: null,
  resolvedApprovals: {},
  messages: [
    {
      role: "assistant",
      content:
        "Hi! I'm **CommPal**, your AI shopping assistant.\n\n" +
        "• Click **Ran Out (Auto-Buy)** on any item in **My Pantry** (left) to trigger an automatic PayPal order.\n" +
        "• Or click any quick button below to compare store prices or order items!",
      cards: [],
    },
  ],
};

/* --- Resilient API Client --- */
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const urls = [`http://127.0.0.1:8000/api${path}`, `http://localhost:8000/api${path}`];

  let lastError = null;
  for (const url of urls) {
    try {
      const res = await fetch(url, { ...options, headers });
      if (!res.ok) {
        let msg = `Error ${res.status}`;
        try {
          const j = await res.json();
          msg = j.detail || j.message || msg;
        } catch (_) {}
        throw new Error(msg);
      }
      return await res.json();
    } catch (err) {
      lastError = err;
      if (err.message && !err.message.includes("Failed to fetch") && !err.message.includes("NetworkError")) {
        throw err;
      }
    }
  }
  throw lastError || new Error("Could not connect to backend");
}

function toast(text, type = "info") {
  const box = document.getElementById("toast-container");
  if (!box) return;
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = text;
  box.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function md(text) {
  return esc(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`(.*?)`/g, '<code class="mono" style="background:#0e1118;padding:1px 5px;border-radius:4px;color:#38bdf8;">$1</code>')
    .replace(/\n/g, "<br/>");
}

function money(val) {
  return `$${Number(val || 0).toFixed(2)}`;
}

/* --- Fault-Tolerant Refresh (Uses Promise.allSettled so 1 endpoint never breaks UI) --- */
async function refreshAll() {
  const results = await Promise.allSettled([
    api("/wallet"),
    api("/items"),
    api("/orders"),
    api("/approvals"),
    api("/mandate"),
    api("/audit?limit=50"),
    api("/audit/verify"),
    api("/health"),
  ]);

  const [wRes, iRes, oRes, aRes, mRes, audRes, verRes, hRes] = results;

  if (wRes.status === "fulfilled") state.wallet = wRes.value;
  if (iRes.status === "fulfilled") state.items = iRes.value;
  if (oRes.status === "fulfilled") state.orders = oRes.value;
  if (aRes.status === "fulfilled") state.approvals = aRes.value;
  if (mRes.status === "fulfilled") {
    state.mandate = mRes.value.mandate;
    state.mandateVersion = mRes.value.version;
  }
  if (audRes.status === "fulfilled") state.auditEvents = audRes.value;
  if (verRes.status === "fulfilled") state.auditVerify = verRes.value;
  if (hRes.status === "fulfilled") state.health = hRes.value;

  const anySuccess = results.some((r) => r.status === "fulfilled");
  const statusBadge = document.getElementById("status-badge");
  if (statusBadge) {
    statusBadge.textContent = anySuccess ? "● Online" : "○ Offline";
    statusBadge.className = anySuccess ? "badge badge-green" : "badge badge-red";
  }

  renderHeader();
  renderPantry();
  renderApprovals();
  renderOrders();
  renderAuditFooter();
}

/* --- 1. Top Header --- */
function renderHeader() {
  const w = state.wallet;
  if (!w) return;

  document.getElementById("top-balance").textContent = money(w.available_balance);
  document.getElementById("top-daily").textContent = `$${w.daily_spent.toFixed(0)} / $${w.daily_cap.toFixed(0)}`;

  const pauseBanner = document.getElementById("pause-banner");
  const killBtn = document.getElementById("kill-btn");
  if (w.kill_switch) {
    pauseBanner.classList.add("show");
    killBtn.textContent = "▶ Resume Agent";
    killBtn.className = "btn btn-green";
  } else {
    pauseBanner.classList.remove("show");
    killBtn.textContent = "⏸ Pause Agent";
    killBtn.className = "btn btn-red";
  }

  if (state.health) {
    const ppBadge = document.getElementById("paypal-badge");
    ppBadge.textContent = state.health.paypal_mode === "sandbox" ? "PayPal Live Sandbox" : "PayPal Sandbox";
    const llmBadge = document.getElementById("llm-badge");
    llmBadge.textContent = state.health.ollama_active ? `Ollama (${state.health.ollama_model})` : "Smart NLU Active";
  }
}

/* --- 2. Left Column: My Pantry --- */
function renderPantry() {
  document.getElementById("pantry-count").textContent = `${state.items.length} items`;
  const list = document.getElementById("pantry-list");

  list.innerHTML = state.items
    .map((it) => {
      const empty = it.stock_qty <= 0;
      const low = it.days_of_cover <= it.threshold_days;
      const statusBadge = empty
        ? `<span class="badge badge-red">Empty (0 left)</span>`
        : low
        ? `<span class="badge badge-amber">Running Low (${it.stock_qty} ${esc(it.unit)})</span>`
        : `<span class="badge badge-green">${it.stock_qty} ${esc(it.unit)} in stock</span>`;

      return `
        <div class="pantry-item">
          <div class="pantry-top">
            <div>
              <div class="pantry-name">${esc(it.name)}</div>
              <div class="pantry-meta">Lasts ~${it.days_of_cover} days · Category: ${esc(it.category)}</div>
            </div>
            ${statusBadge}
          </div>

          <div class="pantry-actions">
            <div style="display:flex; gap:5px;">
              <button class="btn btn-sm" onclick="changeStock('${esc(it.id)}', '${esc(it.name)}', 'delta', -1)" title="Use 1">−1</button>
              <button class="btn btn-sm" onclick="changeStock('${esc(it.id)}', '${esc(it.name)}', 'delta', 1)" title="Add 1">+1</button>
              <button class="btn btn-sm btn-blue" onclick="buyNow('${esc(it.name)}', 1)">Buy 1</button>
            </div>
            <button class="btn btn-sm btn-amber" onclick="changeStock('${esc(it.id)}', '${esc(it.name)}', 'finished', 0)">
              ⚡ Ran Out (Auto-Buy)
            </button>
          </div>
        </div>
      `;
    })
    .join("");
}

async function changeStock(itemId, itemName, mode, qty) {
  try {
    const res = await api(`/items/${itemId}/stock`, {
      method: "POST",
      body: JSON.stringify({ mode, qty, reason: "User pantry button" }),
    });

    if (res.triggered_order) {
      const ord = res.triggered_order;
      if (ord.status === "ORDER_PLACED") {
        toast(`Auto-Ordered ${itemName} from ${ord.merchant} (${money(ord.amount)}) via PayPal!`, "success");
      } else {
        toast(`${itemName}: ${ord.message || ord.status}`, "warning");
      }
    } else {
      toast(`Updated ${itemName} stock to ${res.stock_qty}`, "info");
    }
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function buyNow(itemName, qty = 1) {
  try {
    const res = await api("/orders/purchase", {
      method: "POST",
      body: JSON.stringify({ item_name: itemName, qty, source: "chat", urgency_hint: "routine" }),
    });
    if (res.status === "ORDER_PLACED") {
      toast(`Ordered ${itemName} from ${res.merchant} (${money(res.amount)}) via PayPal!`, "success");
    } else if (res.status === "PENDING_APPROVAL") {
      toast(`Approval needed for ${itemName} — check Center column!`, "warning");
    } else {
      toast(`Blocked: ${res.message}`, "error");
    }
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function quickAddItem(name, category, unit) {
  try {
    await api("/items", {
      method: "POST",
      body: JSON.stringify({
        name,
        category,
        unit,
        stock_qty: 2,
        burn_rate_per_day: 0.5,
        threshold_days: 1.5,
        reorder_qty: 1,
        last_price: 8.99,
      }),
    });
    toast(`Added ${name} to My Pantry!`, "success");
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function handleCustomAddItem(e) {
  e.preventDefault();
  const inp = document.getElementById("custom-item-input");
  const name = inp.value.trim();
  if (!name) return;
  inp.value = "";
  await quickAddItem(name, "grocery", "unit");
}

/* --- 3. Center Column: Approvals & Chat --- */
function renderApprovals() {
  const box = document.getElementById("pending-approvals-container");
  if (!state.approvals || state.approvals.length === 0) {
    box.innerHTML = "";
    return;
  }

  box.innerHTML = state.approvals
    .map(
      (a) => `
      <div class="approval-box">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <strong style="color:#fbbf24; font-size:13.5px;">⚠ Needs Your Permission: ${esc(a.item_name)} (&times;${a.qty})</strong>
          <span class="badge badge-amber">Paused by Safety Rule</span>
        </div>
        <div style="font-size:12.5px; color:var(--text-muted); margin-bottom:10px;">
          ${esc(a.explanation || "This item is not in your tracked Pantry or exceeds your auto-approve limit.")}
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-sm btn-green" onclick="decideApproval('${esc(a.intent_id)}', 'approve')">
            ✓ Approve &amp; Pay with PayPal
          </button>
          <button class="btn btn-sm btn-red" onclick="decideApproval('${esc(a.intent_id)}', 'reject')">
            ✕ Cancel Order
          </button>
        </div>
      </div>
    `
    )
    .join("");
}

function renderChat() {
  const stream = document.getElementById("chat-stream");
  stream.innerHTML = state.messages
    .map((m) => {
      const cardsHtml = (m.cards || []).map((c) => renderChatCard(c)).join("");
      return `
        <div class="chat-msg ${m.role === "user" ? "user" : "assistant"}">
          <div class="chat-bubble">${md(m.content)}</div>
          ${cardsHtml}
        </div>
      `;
    })
    .join("");
  stream.scrollTop = stream.scrollHeight;
}

function renderChatCard(card) {
  const d = card.data || {};
  if (card.card_type === "order_preview" && Array.isArray(d.offers)) {
    const rows = d.offers
      .map(
        (o) => `
        <div style="display:flex; justify-content:space-between; padding:6px 8px; background:#0e1118; border-radius:6px; font-size:12px;">
          <span><strong>${esc(o.merchant_name)}</strong> · ${o.eta_minutes} mins · ★${o.rating}</span>
          <strong class="mono" style="color:#38bdf8;">${money(o.landed_price)}</strong>
        </div>
      `
      )
      .join("");
    return `
      <div style="background:var(--bg-panel); border:1px solid var(--border-light); border-radius:8px; padding:10px; display:flex; flex-direction:column; gap:5px;">
        <div style="font-size:12px; font-weight:600; color:var(--text-muted);">${esc(card.title)}</div>
        ${rows}
      </div>
    `;
  }
  return "";
}

async function handleChatSubmit(e) {
  e.preventDefault();
  const inp = document.getElementById("chat-input");
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = "";
  await sendChat(txt);
}

async function sendChat(text) {
  state.messages.push({ role: "user", content: text, cards: [] });
  renderChat();

  const btn = document.getElementById("send-btn");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "...";
  }

  try {
    const reply = await api("/chat", {
      method: "POST",
      body: JSON.stringify({ message: text, conversation_id: "default" }),
    });
    state.messages.push(reply);
    renderChat();
    await refreshAll();
  } catch (err) {
    state.messages.push({ role: "assistant", content: `Error: ${err.message}`, cards: [] });
    renderChat();
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Send";
    }
  }
}

async function decideApproval(intentId, action) {
  try {
    const res = await api(`/orders/${intentId}/action`, {
      method: "POST",
      body: JSON.stringify({ action, reason: "User clicked button" }),
    });
    if (action === "approve") {
      toast(`Approved! Paid ${money(res.amount || 0)} to ${res.merchant || "store"} via PayPal`, "success");
    } else {
      toast("Order cancelled", "warning");
    }
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

/* --- 4. Right Column: Live Orders & PayPal Receipts --- */
function renderOrders() {
  const list = document.getElementById("orders-list");
  if (!state.orders || state.orders.length === 0) {
    list.innerHTML = `
      <div style="text-align:center; padding:32px 16px; color:var(--text-muted); font-size:13px;">
        No orders yet.<br/>Click <strong>"⚡ Ran Out (Auto-Buy)"</strong> on any Pantry item or ask CommPal to buy something!
      </div>
    `;
    return;
  }

  list.innerHTML = state.orders
    .map((o) => {
      const delivered = o.state === "DELIVERED";
      return `
        <div class="order-card">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
            <div>
              <div style="font-weight:600; font-size:14px;">${esc(o.item_name)} &times; ${o.qty}</div>
              <div style="font-size:12px; color:var(--text-muted);">
                Store: <strong style="color:var(--text);">${esc(o.merchant_name)}</strong> · ETA ${o.eta_minutes} mins
              </div>
            </div>
            <div style="text-align:right;">
              <div class="mono" style="font-weight:700; font-size:15px;">${money(o.amount)}</div>
              <span class="badge ${delivered ? "badge-green" : "badge-blue"}">
                ${delivered ? "✓ DELIVERED" : "🚚 IN TRANSIT"}
              </span>
            </div>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; padding-top:8px; border-top:1px solid var(--border);">
            <span class="mono" style="font-size:11px; color:var(--text-muted);">
              PayPal ID: ${esc((o.paypal_capture_id || o.paypal_auth_id || "PAID").slice(0, 18))}
            </span>
            <button class="btn btn-sm" onclick="showWhyStore('${esc(o.id)}')">Why this store?</button>
          </div>
        </div>
      `;
    })
    .join("");
}

async function showWhyStore(orderId) {
  try {
    const data = await api(`/orders/${orderId}`);
    const ord = data.order;
    const dec = data.decision || {};
    document.getElementById("store-modal-title").textContent = `${ord.item_name} — Picked ${ord.merchant_name} (${money(ord.amount)})`;
    document.getElementById("store-modal-sub").textContent = dec.explanation || "";

    const rows = (dec.score_breakdown || [])
      .map(
        (s, i) => `
        <tr>
          <td>
            <strong>${esc(s.merchant_id.toUpperCase())}</strong>
            ${i === 0 ? '<span class="badge badge-green" style="margin-left:6px;">BEST PICK</span>' : ""}
          </td>
          <td class="mono">${Math.round(s.price_score * 100)}/100</td>
          <td class="mono">${Math.round(s.eta_score * 100)}/100</td>
          <td class="mono">${Math.round(s.rating_score * 100)}/100</td>
          <td class="mono" style="font-weight:700; color:#38bdf8;">${Math.round(s.total_score * 100)}/100</td>
        </tr>
      `
      )
      .join("");

    document.getElementById("store-modal-body").innerHTML = `
      <table class="simple-table">
        <thead>
          <tr>
            <th>Store</th>
            <th>Price Score</th>
            <th>Speed Score</th>
            <th>Rating</th>
            <th>Overall Score</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    document.getElementById("store-modal").classList.add("open");
  } catch (err) {
    toast(err.message, "error");
  }
}

/* --- 5. Top Bar Controls & Modals --- */
async function topUpWallet(amount) {
  try {
    await api("/wallet/top-up", {
      method: "POST",
      body: JSON.stringify({ amount, currency: "USD", payment_method: "paypal_sandbox" }),
    });
    toast(`Added ${money(amount)} to your PayPal Wallet!`, "success");
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function advanceTime(hours = 0, days = 0) {
  try {
    const res = await api(`/demo/clock/advance?hours=${hours}&days=${days}`, { method: "POST" });
    const tr = res.tick_result || {};
    toast(
      `Fast-forwarded +${days ? days + "d" : hours + "h"}: ${tr.orders_delivered || 0} order(s) delivered, ${tr.rules_fired || 0} daily rule(s) triggered!`,
      "success"
    );
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function toggleKillSwitch(forceState) {
  const active = typeof forceState === "boolean" ? forceState : !Boolean(state.wallet?.kill_switch);
  try {
    await api("/mandate/kill-switch", {
      method: "POST",
      body: JSON.stringify({ active, reason: "User toggled Pause button" }),
    });
    toast(active ? "Agent Paused — all purchases blocked" : "Agent Resumed!", active ? "warning" : "success");
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

async function resetDemo() {
  try {
    await api("/demo/reset", { method: "POST" });
    toast("Demo reset to $200.00 PayPal balance and 3 Pantry items!", "success");
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

function openLimitsModal() {
  const m = state.mandate;
  if (m) {
    document.getElementById("lim-auto").value = m.limits.auto_approve_under;
    document.getElementById("lim-max-txn").value = m.limits.per_txn_max;
    document.getElementById("lim-daily").value = m.limits.daily_cap;
    document.getElementById("lim-monthly").value = m.limits.monthly_cap;
    document.getElementById("lim-untracked").checked = Boolean(m.items?.allow_untracked);
  }
  document.getElementById("limits-modal").classList.add("open");
}

async function saveLimits(e) {
  e.preventDefault();
  const m = state.mandate || {};
  const payload = {
    version: (state.mandateVersion || 1) + 1,
    kill_switch: Boolean(state.wallet?.kill_switch),
    limits: {
      auto_approve_under: parseFloat(document.getElementById("lim-auto").value || "25"),
      per_txn_max: parseFloat(document.getElementById("lim-max-txn").value || "60"),
      daily_cap: parseFloat(document.getElementById("lim-daily").value || "80"),
      monthly_cap: parseFloat(document.getElementById("lim-monthly").value || "400"),
      category_budgets: m.limits?.category_budgets || { grocery: 150, supplies: 100, fitness: 120 },
    },
    merchants: m.merchants || { allowlist: ["quick10", "zipbasket", "cornerstore", "megamart", "bulkbarn"], blocklist: [] },
    items: { allow_untracked: document.getElementById("lim-untracked").checked },
    anomalies: m.anomalies || { max_price_spike_pct: 20, max_qty_multiple: 2, duplicate_window_hours: 12 },
  };

  try {
    await api("/mandate", { method: "PUT", body: JSON.stringify(payload) });
    closeModal("limits-modal");
    toast("Spend limits saved!", "success");
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

function renderAuditFooter() {
  const v = state.auditVerify;
  const title = document.getElementById("audit-summary-title");
  const sub = document.getElementById("audit-summary-sub");
  if (v && v.is_valid) {
    title.textContent = `✓ Audit Log Verified (${v.events_count || state.auditEvents.length} SHA-256 Events)`;
    title.style.color = "#34d399";
    sub.textContent = "Every PayPal payment & safety rule check is cryptographically linked";
  }
}

function openAuditModal() {
  const rows = state.auditEvents
    .map(
      (ev) => `
      <tr>
        <td class="mono">#${ev.seq}</td>
        <td><span class="badge">${esc(ev.actor)}</span></td>
        <td><strong class="mono" style="color:#38bdf8;">${esc(ev.event_type)}</strong></td>
        <td class="mono" style="font-size:11px; color:#34d399;">${esc((ev.hash || "").slice(0, 12))}...</td>
      </tr>
    `
    )
    .join("");

  document.getElementById("audit-modal-body").innerHTML = `
    <table class="simple-table">
      <thead>
        <tr><th>#</th><th>Actor</th><th>Action</th><th>SHA-256 Hash</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  document.getElementById("audit-modal").classList.add("open");
}

async function openEnvModal() {
  try {
    const cfg = await api("/config/env");
    document.getElementById("env-paypal-mode").value = cfg.PAYPAL_MODE || "sandbox";
    document.getElementById("env-llm-provider").value = cfg.LLM_PROVIDER || "ollama";
    document.getElementById("env-paypal-id").value = cfg.PAYPAL_CLIENT_ID || "";
    document.getElementById("env-paypal-secret").value = cfg.PAYPAL_CLIENT_SECRET || "";
    document.getElementById("env-gemini-key").value = cfg.GEMINI_API_KEY || "";
    document.getElementById("env-channel3-key").value = cfg.CHANNEL3_API_KEY || "";
  } catch (_) {}
  document.getElementById("env-modal").classList.add("open");
}

async function saveEnv(e) {
  e.preventDefault();
  try {
    await api("/config/env", {
      method: "POST",
      body: JSON.stringify({
        PAYPAL_MODE: document.getElementById("env-paypal-mode").value,
        LLM_PROVIDER: document.getElementById("env-llm-provider").value,
        PAYPAL_CLIENT_ID: document.getElementById("env-paypal-id").value.trim(),
        PAYPAL_CLIENT_SECRET: document.getElementById("env-paypal-secret").value.trim(),
        GEMINI_API_KEY: document.getElementById("env-gemini-key").value.trim(),
        CHANNEL3_API_KEY: document.getElementById("env-channel3-key").value.trim(),
      }),
    });
    closeModal("env-modal");
    toast("Saved API keys to .env!", "success");
    await refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
}

function closeModal(id) {
  document.getElementById(id).classList.remove("open");
}

window.addEventListener("DOMContentLoaded", () => {
  renderChat();
  refreshAll();
  setInterval(refreshAll, 5000);
});
