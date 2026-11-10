"use client";

import React, { useState, useEffect } from "react";
import {
  FastForward,
  RotateCcw,
  Flame,
  Play,
} from "lucide-react";
import {
  advanceClock,
  resetDemoScenario,
  fetchChaos,
  toggleChaosFlag,
  sendChatMessage,
} from "@/lib/api";
import { TabType } from "@/app/page";

interface DemoStudioTabProps {
  onRefresh: () => Promise<void> | void;
  onNotify: (message: string, tone?: "success" | "warning" | "error" | "info") => void;
  onNavigate: (tab: TabType) => void;
}

export default function DemoStudioTab({
  onRefresh,
  onNotify,
  onNavigate,
}: DemoStudioTabProps) {
  const [chaos, setChaos] = useState<any>({
    out_of_stock_items: [],
    down_merchants: [],
    payment_failure: false,
  });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    loadChaos();
  }, []);

  const loadChaos = async () => {
    try {
      const data = await fetchChaos();
      setChaos(data);
    } catch {
      // ignore
    }
  };

  const handleAdvance = async (hours: number, days: number = 0) => {
    setBusy(true);
    try {
      const res = await advanceClock(hours, days);
      await onRefresh();
      const tr = res.tick_result || {};
      onNotify(
        `Advanced Virtual Clock +${days > 0 ? `${days}d` : `${hours}h`}: ` +
          `${tr.rules_fired || 0} rule(s) fired, ${tr.depletions_fired || 0} depletion(s), ${tr.orders_delivered || 0} delivered.`,
        "success"
      );
    } catch (e: any) {
      onNotify(e.message || "Clock advance failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    try {
      await resetDemoScenario();
      await loadChaos();
      await onRefresh();
      onNotify(
        "Reset complete: 'Week with Asha' initialized ($200.00 wallet, 3 items, Mandate v1).",
        "info"
      );
    } catch (e: any) {
      onNotify(e.message || "Reset failed", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleToggleChaos = async (key: string, value: any, label: string) => {
    setBusy(true);
    try {
      const res = await toggleChaosFlag({ [key]: value });
      setChaos(res.chaos);
      await onRefresh();
      onNotify(`Chaos state updated: ${label}`, "warning");
    } catch (e: any) {
      onNotify(e.message || "Failed to toggle chaos flag", "error");
    } finally {
      setBusy(false);
    }
  };

  const runLiveScenario = async (prompt: string, targetTab: TabType) => {
    setBusy(true);
    try {
      const msg = await sendChatMessage(prompt);
      await onRefresh();
      onNotify(msg.content.slice(0, 140), "success");
      onNavigate(targetTab);
    } catch (e: any) {
      onNotify(e.message || "Scenario execution failed", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5">
      {/* 1-Click Interactive Benchmark Scenarios */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
            <Play className="w-4 h-4 text-[#0070ba]" />
            1-Click End-to-End Hackathon Benchmark Scenarios
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Execute live end-to-end backend pipelines and navigate directly to the resulting state.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          <div className="p-4 rounded-md bg-zinc-950 border border-zinc-800 flex flex-col justify-between space-y-3">
            <div>
              <div className="font-mono text-[11px] text-[#0070ba] uppercase">
                Scenario A · Urgent Quick-Commerce
              </div>
              <div className="text-xs font-semibold text-zinc-100 mt-1">
                A4 Paper Stockout &rarr; Quick10 (18m ETA)
              </div>
              <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
                Sets A4 Paper stock to 0, derives URGENT SLA, filters out slow marketplaces (MegaMart 36h), and settles via PayPal Sandbox.
              </p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => runLiveScenario("We're out of A4 paper", "orders")}
              className="w-full py-2 px-3 rounded bg-[#0070ba] hover:bg-[#005ea6] disabled:opacity-50 text-white text-xs font-medium cursor-pointer"
            >
              Execute Urgent Paper Order
            </button>
          </div>

          <div className="p-4 rounded-md bg-zinc-950 border border-zinc-800 flex flex-col justify-between space-y-3">
            <div>
              <div className="font-mono text-[11px] text-amber-400 uppercase">
                Scenario B · Mandate Guardrail
              </div>
              <div className="text-xs font-semibold text-zinc-100 mt-1">
                Untracked WD-40 &rarr; Pauses for Human Approval
              </div>
              <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
                Proposes WD-40 purchase. Deterministic RULE_3_UNTRACKED_ITEM halts auto-settlement and queues human approval.
              </p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => runLiveScenario("Order WD-40", "overview")}
              className="w-full py-2 px-3 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-100 border border-zinc-700 text-xs font-medium cursor-pointer"
            >
              Trigger WD-40 Approval Gate
            </button>
          </div>

          <div className="p-4 rounded-md bg-zinc-950 border border-zinc-800 flex flex-col justify-between space-y-3">
            <div>
              <div className="font-mono text-[11px] text-emerald-400 uppercase">
                Scenario C · Planned Marketplace
              </div>
              <div className="text-xs font-semibold text-zinc-100 mt-1">
                Advance +1 Day &rarr; Scheduled Rules & Delivery
              </div>
              <p className="text-[11px] text-zinc-400 mt-1 leading-relaxed">
                Advances virtual clock by 24h, fires due recurring rules (daily milk / monthly protein), and delivers in-transit orders.
              </p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                await handleAdvance(0, 1);
                onNavigate("orders");
              }}
              className="w-full py-2 px-3 rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-medium cursor-pointer"
            >
              Advance +1 Day & View Orders
            </button>
          </div>
        </div>
      </div>

      {/* Time-Travel & Chaos Injection Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Virtual Clock Controls */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <FastForward className="w-4 h-4 text-[#0070ba]" />
              Virtual Time-Travel Controls
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Fast-forward the deterministic clock to test stock decay, approval expiration, and recurring schedules.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => handleAdvance(1, 0)}
              className="py-2 px-3 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 font-mono text-xs cursor-pointer"
            >
              +1 Hour
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => handleAdvance(6, 0)}
              className="py-2 px-3 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 font-mono text-xs cursor-pointer"
            >
              +6 Hours
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => handleAdvance(0, 1)}
              className="py-2 px-3 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 font-mono text-xs cursor-pointer"
            >
              +1 Day
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => handleAdvance(0, 7)}
              className="py-2 px-3 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 font-mono text-xs cursor-pointer"
            >
              +7 Days
            </button>
          </div>

          <div className="pt-3 border-t border-zinc-800 flex items-center justify-between">
            <span className="text-xs text-zinc-400">
              Restore clean initial state:
            </span>
            <button
              type="button"
              disabled={busy}
              onClick={handleReset}
              className="px-3 py-1.5 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 text-xs font-medium flex items-center gap-1.5 cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset &ldquo;Week with Asha&rdquo;</span>
            </button>
          </div>
        </div>

        {/* Chaos & Fault Injection */}
        <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <Flame className="w-4 h-4 text-rose-400" />
              Fault & Chaos Injection
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Inject payment declines and merchant outages to verify automatic ledger rollback and failover routing.
            </p>
          </div>

          <div className="space-y-2.5 text-xs">
            <label className="flex items-center justify-between p-3 rounded bg-zinc-950 border border-zinc-800 cursor-pointer">
              <div>
                <div className="font-medium text-zinc-200">
                  Simulate PayPal Authorization Decline
                </div>
                <div className="text-[11px] text-zinc-500">
                  Verifies Held reservation is automatically released back to Available
                </div>
              </div>
              <input
                type="checkbox"
                checked={Boolean(chaos.payment_failure)}
                onChange={(e) =>
                  handleToggleChaos(
                    "payment_failure",
                    e.target.checked,
                    `PayPal Decline = ${e.target.checked}`
                  )
                }
                className="rounded border-zinc-700 bg-zinc-900"
              />
            </label>

            <label className="flex items-center justify-between p-3 rounded bg-zinc-950 border border-zinc-800 cursor-pointer">
              <div>
                <div className="font-medium text-zinc-200">
                  Merchant Outage: Quick10 (HTTP 503)
                </div>
                <div className="text-[11px] text-zinc-500">
                  Router automatically fails over to ZipBasket
                </div>
              </div>
              <input
                type="checkbox"
                checked={Boolean(chaos.down_merchants?.includes("quick10"))}
                onChange={() =>
                  handleToggleChaos(
                    "down_merchant",
                    "quick10",
                    "Toggled Quick10 merchant availability"
                  )
                }
                className="rounded border-zinc-700 bg-zinc-900"
              />
            </label>

            <label className="flex items-center justify-between p-3 rounded bg-zinc-950 border border-zinc-800 cursor-pointer">
              <div>
                <div className="font-medium text-zinc-200">
                  Catalog Stockout: A4 Paper
                </div>
                <div className="text-[11px] text-zinc-500">
                  Forces zero merchant stock for A4 paper across catalogs
                </div>
              </div>
              <input
                type="checkbox"
                checked={Boolean(chaos.out_of_stock_items?.includes("a4 paper"))}
                onChange={() =>
                  handleToggleChaos(
                    "out_of_stock_item",
                    "a4 paper",
                    "Toggled A4 Paper catalog stockout"
                  )
                }
                className="rounded border-zinc-700 bg-zinc-900"
              />
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
