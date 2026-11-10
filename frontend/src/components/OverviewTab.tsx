"use client";

import React, { useState } from "react";
import {
  Wallet,
  AlertTriangle,
  ShoppingBag,
  Plus,
  ArrowUpRight,
  ShieldCheck,
  PieChart,
} from "lucide-react";
import {
  WalletSummary,
  PendingApproval,
  Order,
  MandateBody,
} from "@/lib/types";
import { actOnApproval, topUpWallet } from "@/lib/api";
import { TabType } from "@/app/page";

interface OverviewTabProps {
  wallet?: WalletSummary;
  mandate?: MandateBody;
  approvals: PendingApproval[];
  orders: Order[];
  onRefresh: () => Promise<void> | void;
  onNotify: (message: string, tone?: "success" | "warning" | "error" | "info") => void;
  onNavigate: (tab: TabType) => void;
}

export default function OverviewTab({
  wallet,
  mandate,
  approvals,
  orders,
  onRefresh,
  onNotify,
  onNavigate,
}: OverviewTabProps) {
  const [acting, setActing] = useState(false);
  const [topUpLoading, setTopUpLoading] = useState(false);
  const [customAmount, setCustomAmount] = useState("");

  const handleAction = async (intentId: string, action: "approve" | "reject") => {
    setActing(true);
    try {
      const res = await actOnApproval(intentId, action);
      await onRefresh();
      if (action === "approve" && res.status === "ORDER_PLACED") {
        onNotify(
          `Approved & settled $${res.amount.toFixed(2)} with ${res.merchant} (Capture: ${res.paypal_capture_id}).`,
          "success"
        );
      } else {
        onNotify(`Order intent ${intentId} ${action}d.`, "info");
      }
    } catch (e: any) {
      onNotify(e.message || "Failed to process approval", "error");
    } finally {
      setActing(false);
    }
  };

  const handleTopUp = async (amount: number) => {
    if (!amount || amount <= 0) return;
    setTopUpLoading(true);
    try {
      const res = await topUpWallet(amount);
      setCustomAmount("");
      await onRefresh();
      onNotify(
        `Added $${res.top_up_amount.toFixed(2)} via PayPal Sandbox. New available balance: $${res.wallet.available_balance.toFixed(2)}.`,
        "success"
      );
    } catch (e: any) {
      onNotify(e.message || "Wallet top-up failed", "error");
    } finally {
      setTopUpLoading(false);
    }
  };

  const dailyPct =
    wallet && wallet.daily_cap > 0
      ? Math.min(100, Math.round((wallet.daily_spent / wallet.daily_cap) * 100))
      : 0;

  const monthlyPct =
    wallet && wallet.monthly_cap > 0
      ? Math.min(100, Math.round((wallet.monthly_spent / wallet.monthly_cap) * 100))
      : 0;

  const categoryConfigs = [
    {
      name: "Grocery & Perishables",
      key: "grocery",
      cap: mandate?.category_budgets?.grocery ?? 250,
    },
    {
      name: "Office & Household Supplies",
      key: "supplies",
      cap: mandate?.category_budgets?.supplies ?? 80,
    },
    {
      name: "Health & Fitness",
      key: "fitness",
      cap: mandate?.category_budgets?.fitness ?? 100,
    },
  ];

  return (
    <div className="space-y-5">
      {/* Pending Approvals Queue */}
      {approvals.length > 0 && (
        <div className="bg-amber-950/20 border border-amber-700/60 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-amber-300 font-semibold text-sm">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span>Pending Human Mandate Approvals ({approvals.length})</span>
            </div>
            <span className="text-xs text-amber-400/80 font-mono">
              Paused by deterministic policy evaluator
            </span>
          </div>

          <div className="divide-y divide-zinc-800/80 border border-zinc-800 rounded-md bg-zinc-900/90">
            {approvals.map((app) => (
              <div
                key={app.approval_id}
                className="p-3.5 flex flex-wrap items-center justify-between gap-3"
              >
                <div className="space-y-0.5">
                  <div className="font-medium text-zinc-100 text-xs sm:text-sm">
                    {app.item_name}{" "}
                    <span className="font-mono text-xs text-zinc-400">
                      (Qty: {app.qty})
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400">{app.explanation}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={acting}
                    onClick={() => handleAction(app.intent_id, "approve")}
                    className="px-3.5 py-1.5 rounded-md bg-[#0070ba] hover:bg-[#005ea6] text-white text-xs font-medium transition-colors cursor-pointer"
                  >
                    Approve & Settle
                  </button>
                  <button
                    type="button"
                    disabled={acting}
                    onClick={() => handleAction(app.intent_id, "reject")}
                    className="px-3.5 py-1.5 rounded-md bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-medium border border-zinc-700 transition-colors cursor-pointer"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 3-Bucket Sandboxed Treasury + Top-Up Control */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7 bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                <Wallet className="w-4 h-4 text-[#0070ba]" />
                3-Bucket Sandboxed PayPal E-Wallet Ledger
              </h2>
              <p className="text-xs text-zinc-400 mt-0.5">
                Isolated agentic treasury: Available &rarr; Held (PayPal Auth) &rarr; Spent (PayPal Capture)
              </p>
            </div>
            <span className="font-mono text-xs text-zinc-400 tabular-nums">
              Total Allocated: ${wallet?.total_balance?.toFixed(2) ?? "0.00"} USD
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 tabular-nums">
            <div className="p-3.5 rounded-md bg-zinc-950 border border-zinc-800">
              <div className="text-[11px] text-zinc-400 uppercase font-mono">
                1. Available Balance
              </div>
              <div className="text-2xl font-mono font-bold text-zinc-100 mt-1">
                ${wallet?.available_balance?.toFixed(2) ?? "0.00"}
              </div>
              <div className="text-[11px] text-zinc-500 mt-1">
                Ready for mandate-approved orders
              </div>
            </div>

            <div className="p-3.5 rounded-md bg-zinc-950 border border-zinc-800">
              <div className="text-[11px] text-zinc-400 uppercase font-mono">
                2. Held in Escrow
              </div>
              <div className="text-2xl font-mono font-bold text-amber-400 mt-1">
                ${wallet?.held_balance?.toFixed(2) ?? "0.00"}
              </div>
              <div className="text-[11px] text-zinc-500 mt-1">
                Reserved during PayPal Authorize
              </div>
            </div>

            <div className="p-3.5 rounded-md bg-zinc-950 border border-zinc-800">
              <div className="text-[11px] text-zinc-400 uppercase font-mono">
                3. Settled Spend
              </div>
              <div className="text-2xl font-mono font-bold text-emerald-400 mt-1">
                ${wallet?.spent_balance?.toFixed(2) ?? "0.00"}
              </div>
              <div className="text-[11px] text-zinc-500 mt-1">
                Captured by confirmed merchants
              </div>
            </div>
          </div>

          {/* Instant Sandbox Top-Up Bar */}
          <div className="pt-3 border-t border-zinc-800 flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs text-zinc-400 font-medium">
              Fund Sandboxed Wallet via PayPal:
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {[25, 50, 100].map((amt) => (
                <button
                  key={amt}
                  type="button"
                  disabled={topUpLoading}
                  onClick={() => handleTopUp(amt)}
                  className="px-2.5 py-1.5 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 text-xs font-mono font-medium transition-colors cursor-pointer"
                >
                  +${amt}
                </button>
              ))}
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min="1"
                  step="10"
                  value={customAmount}
                  onChange={(e) => setCustomAmount(e.target.value)}
                  placeholder="Custom $"
                  className="w-24 bg-zinc-950 border border-zinc-800 rounded px-2.5 py-1.5 text-xs font-mono text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-[#0070ba]"
                />
                <button
                  type="button"
                  disabled={topUpLoading || !customAmount}
                  onClick={() => handleTopUp(parseFloat(customAmount))}
                  className="px-3 py-1.5 rounded bg-[#0070ba] hover:bg-[#005ea6] disabled:opacity-40 text-white text-xs font-medium flex items-center gap-1 transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Top Up</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Daily & Monthly Mandate Caps */}
        <div className="lg:col-span-5 bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 flex flex-col justify-between space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Mandate Cap Utilization
            </h2>
            <button
              type="button"
              onClick={() => onNavigate("mandate")}
              className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 cursor-pointer"
            >
              <span>Edit Limits</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="space-y-4 tabular-nums">
            <div className="p-3.5 rounded-md bg-zinc-950 border border-zinc-800 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-zinc-400 font-medium">Daily Spending Cap</span>
                <span className="font-mono text-zinc-200">
                  ${wallet?.daily_spent?.toFixed(2) ?? "0.00"} / ${wallet?.daily_cap?.toFixed(2) ?? "80.00"}
                </span>
              </div>
              <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    dailyPct > 85 ? "bg-rose-500" : dailyPct > 60 ? "bg-amber-400" : "bg-emerald-500"
                  }`}
                  style={{ width: `${dailyPct}%` }}
                />
              </div>
              <div className="flex justify-between text-[11px] text-zinc-500 font-mono">
                <span>{dailyPct}% utilized</span>
                <span>
                  ${Math.max(0, (wallet?.daily_cap ?? 80) - (wallet?.daily_spent ?? 0)).toFixed(2)} remaining today
                </span>
              </div>
            </div>

            <div className="p-3.5 rounded-md bg-zinc-950 border border-zinc-800 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-zinc-400 font-medium">Monthly Spending Cap</span>
                <span className="font-mono text-zinc-200">
                  ${wallet?.monthly_spent?.toFixed(2) ?? "0.00"} / ${wallet?.monthly_cap?.toFixed(2) ?? "400.00"}
                </span>
              </div>
              <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    monthlyPct > 85 ? "bg-rose-500" : monthlyPct > 60 ? "bg-amber-400" : "bg-[#0070ba]"
                  }`}
                  style={{ width: `${monthlyPct}%` }}
                />
              </div>
              <div className="flex justify-between text-[11px] text-zinc-500 font-mono">
                <span>{monthlyPct}% utilized</span>
                <span>
                  ${Math.max(0, (wallet?.monthly_cap ?? 400) - (wallet?.monthly_spent ?? 0)).toFixed(2)} remaining this month
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Category Budgets & Recent Orders */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <PieChart className="w-4 h-4 text-[#0070ba]" />
              Category Budget Allocation
            </h3>
            <span className="text-xs font-mono text-zinc-500">Enforced by RULE_5_CAT_BUDGET</span>
          </div>

          <div className="space-y-3 tabular-nums">
            {categoryConfigs.map((cat) => {
              const spent = wallet?.category_spent?.[cat.key] || 0;
              const pct = cat.cap > 0 ? Math.min(100, Math.round((spent / cat.cap) * 100)) : 0;
              return (
                <div
                  key={cat.key}
                  className="bg-zinc-950 p-3.5 rounded-md border border-zinc-800/80 space-y-1.5"
                >
                  <div className="flex justify-between text-xs">
                    <span className="font-medium text-zinc-200">{cat.name}</span>
                    <span className="font-mono text-zinc-400">
                      ${spent.toFixed(2)} / ${cat.cap.toFixed(2)}
                    </span>
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="h-full bg-[#0070ba] rounded-full transition-all duration-300"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Fulfilled Orders */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-emerald-400" />
              Recent Autonomous Settlements
            </h3>
            <button
              type="button"
              onClick={() => onNavigate("orders")}
              className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 cursor-pointer"
            >
              <span>All Orders ({orders.length})</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {orders.length === 0 ? (
            <div className="py-10 text-center border border-dashed border-zinc-800 rounded-md space-y-2">
              <p className="text-xs text-zinc-400">
                No orders settled yet in this session.
              </p>
              <button
                type="button"
                onClick={() => onNavigate("chat")}
                className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 font-medium cursor-pointer"
              >
                Open Procurement Assistant
              </button>
            </div>
          ) : (
            <div className="divide-y divide-zinc-800/80 border border-zinc-800 rounded-md bg-zinc-950 overflow-hidden">
              {orders.slice(0, 5).map((ord) => (
                <div
                  key={ord.id}
                  onClick={() => onNavigate("orders")}
                  className="p-3 hover:bg-zinc-900/80 flex items-center justify-between text-xs transition-colors cursor-pointer tabular-nums"
                >
                  <div>
                    <div className="font-medium text-zinc-100">
                      {ord.item_name}{" "}
                      <span className="text-zinc-500 font-mono">×{ord.qty}</span>
                    </div>
                    <div className="text-zinc-400 text-[11px] mt-0.5 font-mono">
                      {ord.merchant_name} · ETA {ord.eta_minutes}m · Capture {ord.paypal_capture_id?.slice(-8)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono font-semibold text-emerald-400">
                      ${ord.amount.toFixed(2)}
                    </div>
                    <span className="text-[10px] font-mono text-zinc-400 uppercase">
                      {ord.state}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
