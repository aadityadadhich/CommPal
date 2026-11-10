"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Save,
} from "lucide-react";
import { MandateBody } from "@/lib/types";
import { fetchMandate, updateMandate, toggleKillSwitch } from "@/lib/api";

interface MandateTabProps {
  onRefresh: () => Promise<void> | void;
  onNotify: (message: string, tone?: "success" | "warning" | "error" | "info") => void;
}

export default function MandateTab({ onRefresh, onNotify }: MandateTabProps) {
  const [mandate, setMandate] = useState<MandateBody | null>(null);
  const [version, setVersion] = useState(1);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadMandate();
  }, []);

  const loadMandate = async () => {
    try {
      const data = await fetchMandate();
      setMandate(data.mandate);
      setVersion(data.version);
    } catch (e: any) {
      onNotify(e.message || "Failed to load mandate policy", "error");
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mandate) return;
    setSaving(true);
    try {
      const res = await updateMandate(mandate);
      setVersion(res.version);
      await onRefresh();
      onNotify(
        `Saved immutable Mandate Policy v${res.version} and appended event to SHA-256 audit log.`,
        "success"
      );
    } catch (e: any) {
      onNotify(e.message || "Failed to save mandate policy", "error");
    } finally {
      setSaving(false);
    }
  };

  const handleKillSwitch = async () => {
    if (!mandate) return;
    const nextState = !mandate.kill_switch;
    try {
      await toggleKillSwitch(nextState);
      setMandate({ ...mandate, kill_switch: nextState });
      await onRefresh();
      onNotify(
        nextState
          ? "Emergency Kill Switch activated — all autonomous spending frozen."
          : "Kill Switch released — autonomous spending resumed.",
        nextState ? "warning" : "success"
      );
    } catch (e: any) {
      onNotify(e.message || "Failed to toggle Kill Switch", "error");
    }
  };

  if (!mandate) {
    return (
      <div className="p-6 text-xs text-zinc-400 font-mono">
        Loading deterministic mandate policy...
      </div>
    );
  }

  const allMerchants = [
    { id: "quick10", label: "Quick10 (15m Quick Commerce)" },
    { id: "zipbasket", label: "ZipBasket (30m Quick Commerce)" },
    { id: "cornerstore", label: "CornerStore (75m Local Store)" },
    { id: "megamart", label: "MegaMart (Next-Day Marketplace)" },
    { id: "bulkbarn", label: "BulkBarn (2-Day Wholesale)" },
    { id: "channel3", label: "Channel3 Live Catalog" },
  ];

  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#0070ba]" />
              Deterministic Spending Mandate Policy
            </h2>
            <span className="px-2 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-zinc-300 text-[11px] font-mono">
              Version {version}
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-0.5">
            Evaluated by pure deterministic rules (<code className="font-mono text-zinc-300">RULE_1</code> – <code className="font-mono text-zinc-300">RULE_9</code>). The AI agent has zero write access to this policy.
          </p>
        </div>

        <button
          type="button"
          onClick={handleKillSwitch}
          className={`px-3.5 py-2 rounded-md text-xs font-medium border flex items-center gap-2 transition-colors cursor-pointer ${
            mandate.kill_switch
              ? "bg-rose-600 text-white border-rose-500 hover:bg-rose-500"
              : "bg-zinc-950 text-zinc-200 border-zinc-800 hover:border-rose-800 hover:text-rose-300"
          }`}
        >
          {mandate.kill_switch ? (
            <>
              <ShieldAlert className="w-4 h-4" />
              <span>Kill Switch Active (Click to Unfreeze)</span>
            </>
          ) : (
            <>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Activate Emergency Kill Switch</span>
            </>
          )}
        </button>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Section 1: Transaction & Period Ceilings */}
        <div className="space-y-2.5">
          <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-400">
            1. Transaction & Period Ceilings (USD)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
            <div className="bg-zinc-950 p-3.5 rounded-md border border-zinc-800">
              <label className="text-xs font-medium text-zinc-200 block">
                Per-Transaction Max ($)
              </label>
              <p className="text-[11px] text-zinc-500 mb-2">
                Hard ceiling (RULE_4_PER_TXN_MAX &rarr; DENY)
              </p>
              <input
                type="number"
                step="1"
                value={mandate.limits.per_txn_max}
                onChange={(e) =>
                  setMandate({
                    ...mandate,
                    limits: {
                      ...mandate.limits,
                      per_txn_max: parseFloat(e.target.value) || 0,
                    },
                  })
                }
                className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 font-mono text-sm focus:outline-none focus:border-[#0070ba]"
              />
            </div>

            <div className="bg-zinc-950 p-3.5 rounded-md border border-zinc-800">
              <label className="text-xs font-medium text-zinc-200 block">
                Auto-Approve Under ($)
              </label>
              <p className="text-[11px] text-zinc-500 mb-2">
                Soft ceiling (RULE_8 &rarr; NEEDS_APPROVAL)
              </p>
              <input
                type="number"
                step="1"
                value={mandate.limits.auto_approve_under}
                onChange={(e) =>
                  setMandate({
                    ...mandate,
                    limits: {
                      ...mandate.limits,
                      auto_approve_under: parseFloat(e.target.value) || 0,
                    },
                  })
                }
                className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 font-mono text-sm focus:outline-none focus:border-[#0070ba]"
              />
            </div>

            <div className="bg-zinc-950 p-3.5 rounded-md border border-zinc-800">
              <label className="text-xs font-medium text-zinc-200 block">
                Daily Spending Cap ($)
              </label>
              <p className="text-[11px] text-zinc-500 mb-2">
                Max settled per 24h (RULE_5_DAILY_CAP)
              </p>
              <input
                type="number"
                step="5"
                value={mandate.limits.daily_cap}
                onChange={(e) =>
                  setMandate({
                    ...mandate,
                    limits: {
                      ...mandate.limits,
                      daily_cap: parseFloat(e.target.value) || 0,
                    },
                  })
                }
                className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 font-mono text-sm focus:outline-none focus:border-[#0070ba]"
              />
            </div>

            <div className="bg-zinc-950 p-3.5 rounded-md border border-zinc-800">
              <label className="text-xs font-medium text-zinc-200 block">
                Monthly Spending Cap ($)
              </label>
              <p className="text-[11px] text-zinc-500 mb-2">
                Max settled per 30d (RULE_5_MONTHLY_CAP)
              </p>
              <input
                type="number"
                step="10"
                value={mandate.limits.monthly_cap}
                onChange={(e) =>
                  setMandate({
                    ...mandate,
                    limits: {
                      ...mandate.limits,
                      monthly_cap: parseFloat(e.target.value) || 0,
                    },
                  })
                }
                className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 font-mono text-sm focus:outline-none focus:border-[#0070ba]"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Category Budgets */}
        <div className="space-y-2.5">
          <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-400">
            2. Category Budget Caps (RULE_5_CAT_BUDGET)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
            {(["grocery", "supplies", "fitness"] as const).map((cat) => (
              <div
                key={cat}
                className="bg-zinc-950 p-3.5 rounded-md border border-zinc-800"
              >
                <label className="text-xs font-medium text-zinc-200 capitalize block mb-1.5">
                  {cat} Budget ($)
                </label>
                <input
                  type="number"
                  step="5"
                  value={mandate.category_budgets[cat] ?? 100}
                  onChange={(e) =>
                    setMandate({
                      ...mandate,
                      category_budgets: {
                        ...mandate.category_budgets,
                        [cat]: parseFloat(e.target.value) || 0,
                      },
                    })
                  }
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 font-mono text-sm focus:outline-none focus:border-[#0070ba]"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Section 3: Merchant Allowlist & Anomaly Guardrails */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <div className="bg-zinc-950 p-4 rounded-md border border-zinc-800 space-y-3">
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-300">
                3. Authorized Merchant Allowlist (RULE_2)
              </h3>
              <p className="text-[11px] text-zinc-500 mt-0.5">
                Unchecked merchants are blocked at both router and mandate layers.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
              {allMerchants.map((m) => {
                const isAllowed = mandate.merchants.allow.includes(m.id);
                return (
                  <label
                    key={m.id}
                    className="flex items-center gap-2 text-zinc-200 cursor-pointer p-2 rounded bg-zinc-900/60 border border-zinc-800/80"
                  >
                    <input
                      type="checkbox"
                      checked={isAllowed}
                      onChange={(e) => {
                        const newAllow = e.target.checked
                          ? [...mandate.merchants.allow, m.id]
                          : mandate.merchants.allow.filter((x) => x !== m.id);
                        setMandate({
                          ...mandate,
                          merchants: { ...mandate.merchants, allow: newAllow },
                        });
                      }}
                      className="rounded border-zinc-700 bg-zinc-900"
                    />
                    <span>{m.label}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="bg-zinc-950 p-4 rounded-md border border-zinc-800 space-y-3.5">
            <div>
              <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-300">
                4. Untracked Items & Anomaly Guardrails (RULE_3 & RULE_7)
              </h3>
              <p className="text-[11px] text-zinc-500 mt-0.5">
                Controls when unusual orders pause for human approval.
              </p>
            </div>

            <label className="flex items-center gap-2.5 text-xs text-zinc-200 cursor-pointer p-2.5 rounded bg-zinc-900/60 border border-zinc-800/80">
              <input
                type="checkbox"
                checked={mandate.items.allow_untracked}
                onChange={(e) =>
                  setMandate({
                    ...mandate,
                    items: {
                      ...mandate.items,
                      allow_untracked: e.target.checked,
                    },
                  })
                }
                className="rounded border-zinc-700 bg-zinc-900"
              />
              <span>
                Allow auto-approval on untracked items (when unchecked, items like WD-40 require human tap)
              </span>
            </label>

            <div className="grid grid-cols-3 gap-2.5 text-xs">
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Price Spike (%)
                </label>
                <input
                  type="number"
                  value={mandate.anomaly.price_spike_pct}
                  onChange={(e) =>
                    setMandate({
                      ...mandate,
                      anomaly: {
                        ...mandate.anomaly,
                        price_spike_pct: parseFloat(e.target.value) || 0,
                      },
                    })
                  }
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1.5 font-mono text-zinc-100"
                />
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Max Qty Multiple
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={mandate.anomaly.max_qty_multiple}
                  onChange={(e) =>
                    setMandate({
                      ...mandate,
                      anomaly: {
                        ...mandate.anomaly,
                        max_qty_multiple: parseFloat(e.target.value) || 1,
                      },
                    })
                  }
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1.5 font-mono text-zinc-100"
                />
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Dup. Window (h)
                </label>
                <input
                  type="number"
                  value={mandate.anomaly.duplicate_window_hours}
                  onChange={(e) =>
                    setMandate({
                      ...mandate,
                      anomaly: {
                        ...mandate.anomaly,
                        duplicate_window_hours: parseInt(e.target.value, 10) || 1,
                      },
                    })
                  }
                  className="w-full bg-zinc-900 border border-zinc-800 rounded px-2.5 py-1.5 font-mono text-zinc-100"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-2 border-t border-zinc-800">
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 rounded-md bg-[#0070ba] hover:bg-[#005ea6] disabled:opacity-50 text-white text-xs font-medium flex items-center gap-2 transition-colors cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{saving ? "Committing Version..." : "Commit New Mandate Version"}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
