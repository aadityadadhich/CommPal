"use client";

import React, { useState, useEffect } from "react";
import { 
  Sliders, FastForward, RotateCcw, AlertTriangle, 
  Flame, CheckCircle2, Video, Zap 
} from "lucide-react";
import { advanceClock, resetDemoScenario, fetchChaos, toggleChaosFlag } from "../lib/api";

interface DemoStudioTabProps {
  onRefresh: () => void;
}

export default function DemoStudioTab({ onRefresh }: DemoStudioTabProps) {
  const [chaos, setChaos] = useState<any>({
    out_of_stock_items: [],
    down_merchants: [],
    payment_failure: false,
  });
  const [advancing, setAdvancing] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  useEffect(() => {
    loadChaos();
  }, []);

  const loadChaos = async () => {
    try {
      const data = await fetchChaos();
      setChaos(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleAdvance = async (hours: number, days: number = 0) => {
    setAdvancing(true);
    try {
      const res = await advanceClock(hours, days);
      setNotification(
        `Advanced clock by ${days > 0 ? `${days} day(s)` : `${hours} hour(s)`}! ` +
        `Fired: ${res.tick_result.rules_fired} rule(s), ${res.tick_result.depletions_fired} depletion(s).`
      );
      setTimeout(() => setNotification(null), 4000);
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setAdvancing(false);
    }
  };

  const handleReset = async () => {
    try {
      await resetDemoScenario();
      setNotification("Reset complete: 'Week with Asha' scenario initialized ($200 wallet, 3 rules, clean audit log).");
      setTimeout(() => setNotification(null), 4000);
      await loadChaos();
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  const toggleChaos = async (key: string, value: any) => {
    try {
      const res = await toggleChaosFlag({ [key]: value });
      setChaos(res.chaos);
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6">
      {notification && (
        <div className="p-4 rounded-xl bg-blue-950/60 border border-blue-500/40 text-blue-200 text-xs font-semibold flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-blue-400" />
          <span>{notification}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Virtual Clock & Scenario Reset */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <FastForward className="w-5 h-5 text-amber-400" />
            Virtual Clock Time-Travel
          </h3>
          <p className="text-xs text-slate-400">
            Fast-forward simulated time to verify that recurring rules (daily milk, monthly protein) and depletion triggers fire autonomously.
          </p>

          <div className="grid grid-cols-3 gap-2 pt-2">
            <button
              disabled={advancing}
              onClick={() => handleAdvance(1)}
              className="py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-mono text-xs font-semibold border border-slate-700 transition-colors"
            >
              +1 Hour
            </button>
            <button
              disabled={advancing}
              onClick={() => handleAdvance(0, 1)}
              className="py-2.5 px-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-semibold shadow-lg shadow-blue-600/30 transition-colors"
            >
              +1 Day (Rule Fire)
            </button>
            <button
              disabled={advancing}
              onClick={() => handleAdvance(0, 7)}
              className="py-2.5 px-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-mono text-xs font-semibold shadow-lg shadow-indigo-600/30 transition-colors"
            >
              +1 Week
            </button>
          </div>

          <div className="pt-3 border-t border-slate-800 flex justify-between items-center">
            <span className="text-xs text-slate-400 font-medium">Re-seed Persona:</span>
            <button
              onClick={handleReset}
              className="py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset "Week with Asha"
            </button>
          </div>
        </div>

        {/* Chaos & Failure Injection */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Flame className="w-5 h-5 text-rose-400" />
            Failure & Chaos Injection
          </h3>
          <p className="text-xs text-slate-400">
            Inject real-world commerce anomalies to prove that CommPal safely handles merchant downtime and payment refusal.
          </p>

          <div className="space-y-3 pt-1 text-xs">
            {/* Payment failure */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <div>
                <div className="font-semibold text-slate-200">Simulate PayPal Decline</div>
                <div className="text-slate-500 text-[11px]">Forces authorization decline; confirms void & hold release</div>
              </div>
              <input
                type="checkbox"
                checked={chaos.payment_failure}
                onChange={(e) => toggleChaos("payment_failure", e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-rose-600 focus:ring-0"
              />
            </div>

            {/* Merchant Quick10 Down */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <div>
                <div className="font-semibold text-slate-200">Merchant Down: Quick10 (503 Error)</div>
                <div className="text-slate-500 text-[11px]">Router seamlessly falls back to ZipBasket</div>
              </div>
              <input
                type="checkbox"
                checked={chaos.down_merchants.includes("quick10")}
                onChange={() => toggleChaos("down_merchant", "quick10")}
                className="rounded border-slate-700 bg-slate-900 text-rose-600 focus:ring-0"
              />
            </div>

            {/* Out of stock paper */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800">
              <div>
                <div className="font-semibold text-slate-200">A4 Paper Stockout Across Quick-Stores</div>
                <div className="text-slate-500 text-[11px]">Demonstrates stock depletion filter</div>
              </div>
              <input
                type="checkbox"
                checked={chaos.out_of_stock_items.includes("a4 paper")}
                onChange={() => toggleChaos("out_of_stock_item", "a4 paper")}
                className="rounded border-slate-700 bg-slate-900 text-rose-600 focus:ring-0"
              />
            </div>
          </div>
        </div>
      </div>

      {/* 2:45 Demo Video Storyboard Cheat-Sheet */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-3">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <Video className="w-4 h-4 text-purple-400" />
          Judge Walkthrough & Video Script Outline (2m 45s)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
            <span className="font-mono text-purple-400 font-bold block mb-1">0:00 - 0:30</span>
            <span className="font-semibold text-white">The Trust Block</span>
            <p className="text-slate-400 mt-1">Users want shopping automated, but won't hand AI an open credit card. CommPal solution: The agent proposes, mandate decides, wallet pays.</p>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
            <span className="font-mono text-purple-400 font-bold block mb-1">0:30 - 1:15</span>
            <span className="font-semibold text-white">Rule Setup & Urgent Restock</span>
            <p className="text-slate-400 mt-1">Asha types "I need milk daily, protein monthly, paper when it runs out." Later, paper depletes &rarr; Quick10 selected for fast delivery.</p>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
            <span className="font-mono text-purple-400 font-bold block mb-1">1:15 - 2:00</span>
            <span className="font-semibold text-white">Time Travel & Depletion</span>
            <p className="text-slate-400 mt-1">Advance clock by 1 day. Scheduler automatically dispatches the daily milk order at 7:00 AM with zero user prompt.</p>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
            <span className="font-mono text-purple-400 font-bold block mb-1">2:00 - 2:45</span>
            <span className="font-semibold text-white">Kill Switch & Verification</span>
            <p className="text-slate-400 mt-1">Toggle Kill Switch &rarr; spending frozen. Inspect cryptographic hash-chained audit log with 1-click verification.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
