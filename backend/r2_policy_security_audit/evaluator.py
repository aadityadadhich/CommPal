from typing import Dict, Any, List, Optional
from backend.app.contracts.mandate import MandateBody, Verdict, VerdictResult
from backend.app.contracts.wallet import WalletSummary

def evaluate_mandate(
    intent_item_name: str,
    intent_item_id: Optional[str],
    intent_qty: float,
    intent_source: str,
    chosen_merchant_id: str,
    landed_total: float,
    unit_price: float,
    category: str,
    wallet_summary: WalletSummary,
    mandate: MandateBody,
    recent_order_history: Optional[List[Dict[str, Any]]] = None
) -> Verdict:
    """
    Role 2 Deterministic Mandate Engine (SRDD 5.2).
    Pure function: evaluate(intent, decision, wallet_state, mandate) -> Verdict
    Makes zero network calls and never involves the LLM.
    """
    reasons: List[str] = []
    rule_ids: List[str] = []
    current_verdict: VerdictResult = "ALLOW"

    def set_verdict(new_v: VerdictResult, reason: str, rule_id: str):
        nonlocal current_verdict
        reasons.append(reason)
        rule_ids.append(rule_id)
        if new_v == "DENY":
            current_verdict = "DENY"
        elif new_v == "NEEDS_APPROVAL" and current_verdict != "DENY":
            current_verdict = "NEEDS_APPROVAL"

    # 1. Kill switch on: deny
    if mandate.kill_switch:
        set_verdict("DENY", "EMERGENCY_KILL_SWITCH: All autonomous spending is frozen.", "RULE_1_KILL_SWITCH")

    # 2. Merchant blocked or not on allowlist: deny
    merchant_lower = chosen_merchant_id.lower()
    if merchant_lower in [b.lower() for b in mandate.merchants.block]:
        set_verdict("DENY", f"MERCHANT_BLOCKED: Merchant '{chosen_merchant_id}' is on the blocklist.", "RULE_2_MERCHANT_BLOCK")
    if mandate.merchants.allow and merchant_lower not in [a.lower() for a in mandate.merchants.allow]:
        set_verdict("DENY", f"MERCHANT_NOT_ALLOWED: Merchant '{chosen_merchant_id}' is not in the allowlist {mandate.merchants.allow}.", "RULE_2_MERCHANT_ALLOW")

    # 3. Item untracked while allow_untracked is false: needs_approval
    if not intent_item_id and not mandate.items.allow_untracked:
        set_verdict("NEEDS_APPROVAL", f"UNTRACKED_ITEM: '{intent_item_name}' is not currently in tracked inventory.", "RULE_3_UNTRACKED_ITEM")

    # 4. Order total above per_txn_max: deny
    if landed_total > mandate.limits.per_txn_max:
        set_verdict("DENY", f"PER_TXN_MAX_EXCEEDED: Order total ${landed_total:.2f} exceeds per-transaction limit of ${mandate.limits.per_txn_max:.2f}.", "RULE_4_PER_TXN_MAX")

    # 5. Daily, monthly, or category cap exceeded: deny
    projected_daily = wallet_summary.daily_spent + landed_total
    if projected_daily > mandate.limits.daily_cap:
        set_verdict("DENY", f"DAILY_CAP_EXCEEDED: Projected daily spend ${projected_daily:.2f} exceeds daily cap ${mandate.limits.daily_cap:.2f}.", "RULE_5_DAILY_CAP")

    projected_monthly = wallet_summary.monthly_spent + landed_total
    if projected_monthly > mandate.limits.monthly_cap:
        set_verdict("DENY", f"MONTHLY_CAP_EXCEEDED: Projected monthly spend ${projected_monthly:.2f} exceeds monthly cap ${mandate.limits.monthly_cap:.2f}.", "RULE_5_MONTHLY_CAP")

    cat_budget = mandate.category_budgets.get(category.lower())
    if cat_budget is not None:
        cat_spent = wallet_summary.category_spent.get(category.lower(), 0.0)
        if cat_spent + landed_total > cat_budget:
            set_verdict("DENY", f"CATEGORY_BUDGET_EXCEEDED: Category '{category}' projected spend ${cat_spent + landed_total:.2f} exceeds budget ${cat_budget:.2f}.", "RULE_5_CAT_BUDGET")

    # 6. Wallet available balance below total: deny (insufficient funds)
    if wallet_summary.available_balance < landed_total:
        set_verdict("DENY", f"INSUFFICIENT_FUNDS: Available balance ${wallet_summary.available_balance:.2f} is insufficient for order total ${landed_total:.2f}.", "RULE_6_INSUFFICIENT_FUNDS")

    # 7. Anomaly checks: needs_approval
    if recent_order_history:
        historical_prices = [
            h.get("unit_price", 0.0) for h in recent_order_history 
            if h.get("item_name", "").lower() == intent_item_name.lower() and h.get("unit_price", 0.0) > 0
        ]
        if historical_prices:
            median_price = sorted(historical_prices)[len(historical_prices) // 2]
            spike_threshold = median_price * (1.0 + mandate.anomaly.price_spike_pct / 100.0)
            if unit_price > spike_threshold:
                set_verdict(
                    "NEEDS_APPROVAL",
                    f"PRICE_SPIKE_DETECTED: Current price ${unit_price:.2f} is >{mandate.anomaly.price_spike_pct}% above median ${median_price:.2f}.",
                    "RULE_7_PRICE_SPIKE"
                )

        duplicates = [
            h for h in recent_order_history 
            if h.get("item_name", "").lower() == intent_item_name.lower()
            and h.get("hours_ago", 999) < mandate.anomaly.duplicate_window_hours
        ]
        if duplicates:
            set_verdict(
                "NEEDS_APPROVAL",
                f"DUPLICATE_ORDER_WINDOW: An order for '{intent_item_name}' was placed within the last {mandate.anomaly.duplicate_window_hours} hours.",
                "RULE_7_DUPLICATE_WINDOW"
            )

    # 8. Total at or above auto_approve_under: needs_approval
    if landed_total >= mandate.limits.auto_approve_under:
        set_verdict(
            "NEEDS_APPROVAL",
            f"AUTO_APPROVE_THRESHOLD_REACHED: Order total ${landed_total:.2f} meets or exceeds soft threshold ${mandate.limits.auto_approve_under:.2f}.",
            "RULE_8_AUTO_APPROVE_THRESHOLD"
        )

    # 9. Otherwise allow
    if not reasons:
        reasons.append("All mandate checks passed within approved limits.")
        rule_ids.append("RULE_9_ALLOW_STANDARD")

    return Verdict(
        result=current_verdict,
        reasons=reasons,
        rule_ids=rule_ids,
        mandate_version=mandate.version
    )
