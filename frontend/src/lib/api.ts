import {
  Item,
  WalletSummary,
  MandateBody,
  Order,
  PendingApproval,
  ChatMessage,
  AuditEvent,
  ClockState,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

async function handleResponse<T>(res: Response, fallbackMsg: string): Promise<T> {
  if (!res.ok) {
    let detail = fallbackMsg;
    try {
      const err = await res.json();
      if (err?.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    } catch {
      // ignore JSON parse error
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/health`);
  return handleResponse(res, "Backend health check failed");
}

export async function sendChatMessage(message: string, conversationId: string = "default"): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  return handleResponse(res, "Chat request failed");
}

export async function fetchItems(): Promise<Item[]> {
  const res = await fetch(`${API_BASE}/api/items`);
  return handleResponse(res, "Failed to fetch inventory items");
}

export async function createItem(payload: {
  name: string;
  unit: string;
  category: string;
  perishable: boolean;
  fulfilment_class: "quick" | "standard" | "any";
  reorder_qty: number;
  threshold_days: number;
  rate_per_day: number;
  stock_qty: number;
}): Promise<{ success: boolean; item_id: string; name: string }> {
  const res = await fetch(`${API_BASE}/api/items`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res, "Failed to create item");
}

export async function updateItemStock(
  itemId: string,
  mode: "absolute" | "delta" | "finished",
  qty: number,
  reason: string = "user_said"
): Promise<{
  success: boolean;
  item_id: string;
  item_name: string;
  stock_qty: number;
  days_of_cover: number;
  stock_confidence: number;
  triggered_order?: any;
}> {
  const res = await fetch(`${API_BASE}/api/items/${itemId}/stock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, qty, reason }),
  });
  return handleResponse(res, "Failed to update item stock");
}

export async function requestDirectPurchase(payload: {
  item_id?: string;
  item_name: string;
  qty: number;
  urgency_hint?: string;
}): Promise<any> {
  const res = await fetch(`${API_BASE}/api/orders/purchase`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ...payload,
      source: "chat",
    }),
  });
  return handleResponse(res, "Purchase request failed");
}

export async function fetchWallet(): Promise<WalletSummary> {
  const res = await fetch(`${API_BASE}/api/wallet`);
  return handleResponse(res, "Failed to fetch wallet");
}

export async function topUpWallet(amount: number, currency: string = "USD"): Promise<{
  success: boolean;
  top_up_amount: number;
  wallet: WalletSummary;
}> {
  const res = await fetch(`${API_BASE}/api/wallet/top-up`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount, currency, payment_method: "paypal_sandbox" }),
  });
  return handleResponse(res, "Failed to top up wallet");
}

export async function fetchOrders(): Promise<Order[]> {
  const res = await fetch(`${API_BASE}/api/orders`);
  return handleResponse(res, "Failed to fetch orders");
}

export async function fetchOrderDetail(orderId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/orders/${orderId}`);
  return handleResponse(res, "Failed to fetch order detail");
}

export async function fetchApprovals(): Promise<PendingApproval[]> {
  const res = await fetch(`${API_BASE}/api/approvals`);
  return handleResponse(res, "Failed to fetch approvals");
}

export async function actOnApproval(
  intentId: string,
  action: "approve" | "reject",
  reason?: string
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/orders/${intentId}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, reason }),
  });
  return handleResponse(res, "Failed to act on approval");
}

export async function fetchMandate(): Promise<{ version: number; mandate: MandateBody }> {
  const res = await fetch(`${API_BASE}/api/mandate`);
  return handleResponse(res, "Failed to fetch mandate");
}

export async function updateMandate(body: MandateBody): Promise<any> {
  const res = await fetch(`${API_BASE}/api/mandate`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(res, "Failed to save mandate");
}

export async function toggleKillSwitch(active: boolean, reason: string = "User dashboard control"): Promise<any> {
  const res = await fetch(`${API_BASE}/api/mandate/kill-switch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active, reason }),
  });
  return handleResponse(res, "Failed to toggle kill switch");
}

export async function fetchAuditTrail(): Promise<AuditEvent[]> {
  const res = await fetch(`${API_BASE}/api/audit?limit=100`);
  return handleResponse(res, "Failed to fetch audit trail");
}

export async function verifyAuditIntegrity(): Promise<{ is_valid: boolean; message: string; events_count: number }> {
  const res = await fetch(`${API_BASE}/api/audit/verify`);
  return handleResponse(res, "Audit verification failed");
}

export async function fetchClock(): Promise<ClockState> {
  const res = await fetch(`${API_BASE}/api/demo/clock`);
  return handleResponse(res, "Failed to fetch virtual clock");
}

export async function advanceClock(hours: number = 0, days: number = 0, minutes: number = 0): Promise<any> {
  const res = await fetch(
    `${API_BASE}/api/demo/clock/advance?hours=${hours}&days=${days}&minutes=${minutes}`,
    { method: "POST" }
  );
  return handleResponse(res, "Failed to advance virtual clock");
}

export async function resetDemoScenario(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/demo/reset`, { method: "POST" });
  return handleResponse(res, "Failed to reset scenario");
}

export async function fetchChaos(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/demo/chaos`);
  return handleResponse(res, "Failed to fetch chaos flags");
}

export async function toggleChaosFlag(body: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/demo/chaos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse(res, "Failed to toggle chaos flag");
}
