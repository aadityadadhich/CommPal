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

export async function fetchHealth(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/health`);
  return res.json();
}

export async function sendChatMessage(message: string): Promise<ChatMessage> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}

export async function fetchItems(): Promise<Item[]> {
  const res = await fetch(`${API_BASE}/api/items`);
  if (!res.ok) throw new Error("Failed to fetch items");
  return res.json();
}

export async function updateItemStock(
  itemId: string,
  mode: "absolute" | "delta" | "finished",
  qty: number,
  reason: string = "user_said"
): Promise<any> {
  const res = await fetch(`${API_BASE}/api/items/${itemId}/stock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode, qty, reason }),
  });
  return res.json();
}

export async function fetchWallet(): Promise<WalletSummary> {
  const res = await fetch(`${API_BASE}/api/wallet`);
  if (!res.ok) throw new Error("Failed to fetch wallet");
  return res.json();
}

export async function fetchOrders(): Promise<Order[]> {
  const res = await fetch(`${API_BASE}/api/orders`);
  if (!res.ok) throw new Error("Failed to fetch orders");
  return res.json();
}

export async function fetchOrderDetail(orderId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/orders/${orderId}`);
  if (!res.ok) throw new Error("Failed to fetch order detail");
  return res.json();
}

export async function fetchApprovals(): Promise<PendingApproval[]> {
  const res = await fetch(`${API_BASE}/api/approvals`);
  if (!res.ok) throw new Error("Failed to fetch approvals");
  return res.json();
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
  return res.json();
}

export async function fetchMandate(): Promise<{ version: number; mandate: MandateBody }> {
  const res = await fetch(`${API_BASE}/api/mandate`);
  if (!res.ok) throw new Error("Failed to fetch mandate");
  return res.json();
}

export async function updateMandate(body: MandateBody): Promise<any> {
  const res = await fetch(`${API_BASE}/api/mandate`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function toggleKillSwitch(active: boolean): Promise<any> {
  const res = await fetch(`${API_BASE}/api/mandate/kill-switch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ active, reason: "User dashboard control" }),
  });
  return res.json();
}

export async function fetchAuditTrail(): Promise<AuditEvent[]> {
  const res = await fetch(`${API_BASE}/api/audit?limit=100`);
  if (!res.ok) throw new Error("Failed to fetch audit trail");
  return res.json();
}

export async function verifyAuditIntegrity(): Promise<{ is_valid: boolean; message: string; events_count: number }> {
  const res = await fetch(`${API_BASE}/api/audit/verify`);
  if (!res.ok) throw new Error("Audit verification failed");
  return res.json();
}

export async function fetchClock(): Promise<ClockState> {
  const res = await fetch(`${API_BASE}/api/demo/clock`);
  return res.json();
}

export async function advanceClock(hours: number = 0, days: number = 0): Promise<any> {
  const res = await fetch(`${API_BASE}/api/demo/clock/advance?hours=${hours}&days=${days}`, {
    method: "POST",
  });
  return res.json();
}

export async function resetDemoScenario(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/demo/reset`, { method: "POST" });
  return res.json();
}

export async function fetchChaos(): Promise<any> {
  const res = await fetch(`${API_BASE}/api/demo/chaos`);
  return res.json();
}

export async function toggleChaosFlag(body: any): Promise<any> {
  const res = await fetch(`${API_BASE}/api/demo/chaos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}
