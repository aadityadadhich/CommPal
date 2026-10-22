export type UrgencyClass = "URGENT" | "ROUTINE" | "PLANNED";

export interface ItemSpec {
  brand_pref?: string;
  size?: string;
  min_rating: number;
  required_brand?: boolean;
}

export interface Item {
  id: string;
  name: string;
  unit: string;
  category: string;
  perishable: boolean;
  fulfilment_class: "quick" | "standard" | "any";
  spec: ItemSpec;
  reorder_qty: number;
  threshold_days: number;
  safety_days: number;
  rate_per_day: number;
  rate_source: string;
  stock_qty: number;
  stock_confidence: number;
  days_of_cover: number;
  needed_by: string;
  last_confirmed_at: string;
  created_at: string;
  active_rules_count: number;
}

export interface WalletSummary {
  available_balance: number;
  held_balance: number;
  spent_balance: number;
  total_balance: number;
  currency: string;
  daily_spent: number;
  monthly_spent: number;
  category_spent: Record<string, number>;
  daily_cap: number;
  monthly_cap: number;
  kill_switch: boolean;
}

export interface MandateLimits {
  per_txn_max: number;
  auto_approve_under: number;
  daily_cap: number;
  monthly_cap: number;
}

export interface MandateBody {
  version: number;
  currency: string;
  kill_switch: boolean;
  limits: MandateLimits;
  category_budgets: Record<string, number>;
  merchants: {
    allow: string[];
    block: string[];
  };
  items: {
    allow_untracked: boolean;
  };
  anomaly: {
    price_spike_pct: number;
    max_qty_multiple: number;
    duplicate_window_hours: number;
  };
  approval_expiry_minutes: number;
}

export interface ScoreBreakdown {
  offer_id: string;
  merchant_id: string;
  price_score: number;
  eta_score: number;
  rating_score: number;
  fit_score: number;
  total_score: number;
}

export interface Order {
  id: string;
  intent_id: string;
  merchant_id: string;
  merchant_name: string;
  item_name: string;
  qty: number;
  merchant_order_ref: string;
  amount: number;
  currency: string;
  paypal_auth_id?: string;
  paypal_capture_id?: string;
  state: string;
  eta_minutes: number;
  created_at: string;
  delivered_at?: string;
  explanation: string;
}

export interface PendingApproval {
  approval_id: string;
  intent_id: string;
  item_name: string;
  qty: number;
  requested_at: string;
  expires_at: string;
  explanation: string;
}

export interface CardPayload {
  card_type: "order_preview" | "rule_created" | "approval_needed" | "order_status" | "decision_explanation";
  title: string;
  subtitle?: string;
  data: any;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  cards?: CardPayload[];
  timestamp: string;
}

export interface AuditEvent {
  seq: number;
  id: string;
  ts: string;
  actor: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload: any;
  mandate_version: number;
  prev_hash: string;
  hash: string;
}

export interface ClockState {
  current_time: string;
  real_time: string;
  offset_seconds: number;
  is_frozen: boolean;
}
