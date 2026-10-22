"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldCheck, ShieldAlert, Lock, Save, Sliders, 
  AlertTriangle, CheckCircle2, History 
} from "lucide-react";
import { MandateBody } from "../lib/types";
import { fetchMandate, updateMandate, toggleKillSwitch } from "../lib/api";

interface MandateTabProps {
  onRefresh: () => void;
}

export default function MandateTab({ onRefresh }: MandateTabProps) {
  const [mandate, setMandate] = useState<MandateBody | null>(null);
  const [version, setVersion] = useState(1);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    loadMandate();
  }, []);

  const loadMandate = async () => {
    try {
      const data = await fetchMandate();
      setMandate(data.mandate);
      setVersion(data.version);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mandate) return;
    setSaving(true);
    try {
      const res = await updateMandate(mandate);
      setVersion(res.version);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const handleKillSwitch = async () => {
    if (!mandate) return;
    const newStatus = !mandate.kill_switch;
    try {
      await toggleKillSwitch(newStatus);
      setMandate({ ...mandate, kill_switch: newStatus });
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  if (!mandate) {
    return <div className="text-slate-400 text-sm p-6">Loading spending mandate...</div>;
  }

  const allMerchants = ["quick10", "zipbasket", "cornerstore", "megamart", "bulkbarn"];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              User Spending Mandate & Deterministic Guardrails
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 text-xs font-mono border border-blue-500/20">
              Version {version}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Requirement GR-10: Only authenticated user actions in this UI can edit limits or toggle the kill switch. The LLM agent has ZERO write access to policy.
          </p>
        </div>

        {/* Big Kill Switch Toggle */}
        <button
          onClick={handleKillSwitch}
          className={`px-4 py-2 rounded-xl text-xs font-bold tracking-wider uppercase transition-all duration-200 flex items-center gap-2 ${
            mandate.kill_switch
              ? "bg-rose-600 text-white ring-4 ring-rose-500/40 shadow-xl shadow-rose-600/50 animate-pulse"
              : "bg-slate-800 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-700"
          }`}
        >
          {mandate.kill_switch ? (
            <>
              <ShieldAlert className="w-4 h-4 text-white" />
              <span>KILL SWITCH ACTIVE (FROZEN)</span>
            </>
          ) : (
            <>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Emergency Kill Switch</span>
            </>
          )}
        </button>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Spending Hard & Soft Ceilings */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Per-Txn Max ($)
            </label>
            <p className="text-[11px] text-slate-500 mb-2">Hard limit (Strict DENY)</p>
            <input
              type="number"
              value={mandate.limits.per_txn_max}
              onChange={(e) =>
                setMandate({
                  ...mandate,
                  limits: { ...mandate.limits, per_txn_max: parseFloat(e.target.value) || 0 },
                })
              }
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white font-mono text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Auto-Approve Under ($)
            </label>
            <p className="text-[11px] text-slate-500 mb-2">Soft limit (Pauses for tap)</p>
            <input
              type="number"
              value={mandate.limits.auto_approve_under}
              onChange={(e) =>
                setMandate({
                  ...mandate,
                  limits: { ...mandate.limits, auto_approve_under: parseFloat(e.target.value) || 0 },
                })
              }
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white font-mono text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Daily Spending Cap ($)
            </label>
            <p className="text-[11px] text-slate-500 mb-2">Maximum settled per day</p>
            <input
              type="number"
              value={mandate.limits.daily_cap}
              onChange={(e) =>
                setMandate({
                  ...mandate,
                  limits: { ...mandate.limits, daily_cap: parseFloat(e.target.value) || 0 },
                })
              }
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white font-mono text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-1">
              Monthly Cap ($)
            </label>
            <p className="text-[11px] text-slate-500 mb-2">Maximum settled per month</p>
            <input
              type="number"
              value={mandate.limits.monthly_cap}
              onChange={(e) =>
                setMandate({
                  ...mandate,
                  limits: { ...mandate.limits, monthly_cap: parseFloat(e.target.value) || 0 },
                })
              }
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-white font-mono text-sm focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        {/* Merchant Allowlist & Untracked Policy */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-slate-950/70 p-5 rounded-xl border border-slate-800 space-y-3">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Merchant Allowlist
            </h3>
            <p className="text-xs text-slate-500">
              Only checked merchants can receive autonomous orders.
            </p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {allMerchants.map((m) => {
                const isAllowed = mandate.merchants.allow.includes(m);
                return (
                  <label key={m} className="flex items-center space-x-2 text-slate-300 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isAllowed}
                      onChange={(e) => {
                        const newAllow = e.target.checked
                          ? [...mandate.merchants.allow, m]
                          : mandate.merchants.allow.filter((x) => x !== m);
                        setMandate({
                          ...mandate,
                          merchants: { ...mandate.merchants, allow: newAllow },
                        });
                      }}
                      className="rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0"
                    />
                    <span className="capitalize">{m}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="bg-slate-950/70 p-5 rounded-xl border border-slate-800 space-y-3">
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
              Safety & Anomaly Controls
            </h3>
            <div className="space-y-3 text-xs">
              <label className="flex items-center space-x-2 text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={mandate.items.allow_untracked}
                  onChange={(e) =>
                    setMandate({
                      ...mandate,
                      items: { ...mandate.items, allow_untracked: e.target.checked },
                    })
                  }
                  className="rounded border-slate-700 bg-slate-900 text-blue-600 focus:ring-0"
                />
                <span>Allow auto-approval on untracked new items</span>
              </label>

              <div className="flex items-center justify-between">
                <span className="text-slate-400">Price Spike Threshold:</span>
                <span className="font-mono text-white">{mandate.anomaly.price_spike_pct}% above 30d median</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Duplicate Suppression Window:</span>
                <span className="font-mono text-white">{mandate.anomaly.duplicate_window_hours} hours</span>
              </div>
            </div>
          </div>
        </div>

        {/* Save Bar */}
        <div className="flex items-center justify-end space-x-3 pt-2">
          {saveSuccess && (
            <span className="text-xs text-emerald-400 flex items-center gap-1 font-semibold">
              <CheckCircle2 className="w-4 h-4" />
              Mandate policy updated to Version {version}!
            </span>
          )}
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold shadow-lg shadow-blue-600/30 flex items-center gap-2 transition-colors"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? "Updating..." : "Save Mandate Policy"}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
