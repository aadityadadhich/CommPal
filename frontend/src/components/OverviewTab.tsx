"use client";

import React, { useState } from "react";
import { 
  Wallet, ShieldCheck, AlertCircle, ShoppingBag, 
  ArrowUpRight, PlusCircle, CheckCircle2, DollarSign, PieChart 
} from "lucide-react";
import { WalletSummary, PendingApproval, Order } from "@/lib/types";
import { actOnApproval } from "@/lib/api";

interface OverviewTabProps {
  wallet?: WalletSummary;
  approvals: PendingApproval[];
  orders: Order[];
  onRefresh: () => void;
}

export default function OverviewTab({ wallet, approvals, orders, onRefresh }: OverviewTabProps) {
  const [acting, setActing] = useState(false);

  const handleAction = async (intentId: string, action: "approve" | "reject") => {
    setActing(true);
    try {
      await actOnApproval(intentId, action);
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setActing(false);
    }
  };

  const dailyPct = wallet && wallet.daily_cap > 0 
    ? Math.min(100, Math.round((wallet.daily_spent / wallet.daily_cap) * 100)) 
    : 0;

  const monthlyPct = wallet && wallet.monthly_cap > 0 
    ? Math.min(100, Math.round((wallet.monthly_spent / wallet.monthly_cap) * 100)) 
    : 0;

  return (
    <div className="space-y-6">
      {/* Pending Approvals Alert Banner */}
      {approvals.length > 0 && (
        <div className="bg-amber-950/40 border border-amber-600/50 rounded-2xl p-5 shadow-xl">
          <div className="flex items-center space-x-2 text-amber-400 font-semibold mb-2">
            <AlertCircle className="w-5 h-5" />
            <span className="text-base">Pending Mandate Approvals ({approvals.length})</span>
          </div>
          <p className="text-sm text-slate-300 mb-4">
            The autonomous agent proposed the following purchase, which exceeded your auto-approve soft threshold or involves an untracked product:
          </p>

          <div className="space-y-3">
            {approvals.map((app) => (
              <div
                key={app.approval_id}
                className="bg-slate-900/80 p-4 rounded-xl border border-slate-800 flex flex-wrap items-center justify-between gap-3"
              >
                <div>
                  <h4 className="font-semibold text-white text-sm">{app.item_name} (Qty: {app.qty})</h4>
                  <p className="text-xs text-slate-400 mt-0.5">{app.explanation}</p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    disabled={acting}
                    onClick={() => handleAction(app.intent_id, "approve")}
                    className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-md shadow-emerald-900/30 transition-colors"
                  >
                    Approve Order
                  </button>
                  <button
                    disabled={acting}
                    onClick={() => handleAction(app.intent_id, "reject")}
                    className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition-colors"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Stats Cards: E-Wallet Ledger */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Available Balance */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 right-0 p-6 opacity-10">
            <Wallet className="w-24 h-24 text-blue-400" />
          </div>
          <div className="flex items-center space-x-2 text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            <Wallet className="w-4 h-4 text-blue-400" />
            <span>Sandboxed E-Wallet</span>
          </div>
          <div className="text-3xl font-bold font-mono text-white mb-2">
            ${wallet?.available_balance?.toFixed(2) ?? "0.00"}
          </div>
          <p className="text-xs text-slate-400">
            Funds allocated for autonomous agent purchases. Agent cannot access your bank account.
          </p>
        </div>

        {/* Daily Spending Cap */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            <span>Daily Mandate Cap</span>
            <span className="font-mono text-slate-200">
              ${wallet?.daily_spent?.toFixed(2)} / ${wallet?.daily_cap?.toFixed(2)}
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-3 mb-3 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                dailyPct > 80 ? "bg-rose-500" : dailyPct > 50 ? "bg-amber-400" : "bg-emerald-500"
              }`}
              style={{ width: `${dailyPct}%` }}
            ></div>
          </div>
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-400">{dailyPct}% utilized</span>
            <span className="text-emerald-400 font-medium">
              ${((wallet?.daily_cap ?? 80) - (wallet?.daily_spent ?? 0)).toFixed(2)} remaining today
            </span>
          </div>
        </div>

        {/* Monthly Spending Cap */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
            <span>Monthly Mandate Cap</span>
            <span className="font-mono text-slate-200">
              ${wallet?.monthly_spent?.toFixed(2)} / ${wallet?.monthly_cap?.toFixed(2)}
            </span>
          </div>
          <div className="w-full bg-slate-800 rounded-full h-3 mb-3 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                monthlyPct > 80 ? "bg-rose-500" : monthlyPct > 50 ? "bg-amber-400" : "bg-blue-500"
              }`}
              style={{ width: `${monthlyPct}%` }}
            ></div>
          </div>
          <div className="flex justify-between items-center text-xs">
            <span className="text-slate-400">{monthlyPct}% utilized</span>
            <span className="text-blue-400 font-medium">
              ${((wallet?.monthly_cap ?? 400) - (wallet?.monthly_spent ?? 0)).toFixed(2)} remaining
            </span>
          </div>
        </div>
      </div>

      {/* Category Spending & Recent Orders */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category breakdown */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <PieChart className="w-4 h-4 text-indigo-400" />
              Category Budgets & Spend
            </h3>
          </div>
          <div className="space-y-3">
            {[
              { name: "Grocery (Milk, Eggs, Bread)", key: "grocery", cap: 250 },
              { name: "Supplies (Paper, WD-40, Batteries)", key: "supplies", cap: 80 },
              { name: "Fitness (Protein Powder)", key: "fitness", cap: 100 },
            ].map((cat) => {
              const spent = wallet?.category_spent?.[cat.key] || 0;
              const pct = Math.min(100, Math.round((spent / cat.cap) * 100));
              return (
                <div key={cat.key} className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800/80">
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="font-medium text-slate-200">{cat.name}</span>
                    <span className="font-mono text-slate-400">
                      ${spent.toFixed(2)} / ${cat.cap.toFixed(2)}
                    </span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${pct}%` }}></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Fulfilled Orders */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-emerald-400" />
              Recent Restock Orders
            </h3>
            <span className="text-xs text-slate-400 font-mono">{orders.length} total</span>
          </div>

          {orders.length === 0 ? (
            <div className="text-center py-10 text-slate-500 text-xs">
              No orders placed yet. Chat with CommPal or advance the clock to trigger recurring orders.
            </div>
          ) : (
            <div className="space-y-3">
              {orders.slice(0, 4).map((ord) => (
                <div
                  key={ord.id}
                  className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800/80 flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="font-semibold text-white">{ord.item_name}</div>
                    <div className="text-slate-400 text-[11px] mt-0.5">
                      {ord.merchant_name} • ETA {ord.eta_minutes}m
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono font-bold text-emerald-400">${ord.amount.toFixed(2)}</div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300 font-mono">
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
