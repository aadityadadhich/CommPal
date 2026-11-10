"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Clock,
  RotateCcw,
  Wallet,
  CircleDot,
} from "lucide-react";
import { ClockState, WalletSummary } from "@/lib/types";
import { toggleKillSwitch, advanceClock, resetDemoScenario } from "@/lib/api";

interface NavbarProps {
  clockState?: ClockState;
  wallet?: WalletSummary;
  backendOnline: boolean;
  onRefresh: () => Promise<void> | void;
  onNotify: (message: string, tone?: "success" | "warning" | "error" | "info") => void;
}

export default function Navbar({
  clockState,
  wallet,
  backendOnline,
  onRefresh,
  onNotify,
}: NavbarProps) {
  const [busy, setBusy] = useState(false);

  const handleToggleKillSwitch = async () => {
    const nextState = !(wallet?.kill_switch ?? false);
    setBusy(true);
    try {
      await toggleKillSwitch(nextState);
      await onRefresh();
      onNotify(
        nextState
          ? "Emergency Kill Switch activated — all autonomous spending is now frozen."
          : "Kill Switch released — autonomous mandate execution resumed.",
        nextState ? "warning" : "success"
      );
    } catch (e: any) {
      onNotify(e.message || "Failed to toggle Kill Switch", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleAdvance = async (hours: number, days: number = 0) => {
    setBusy(true);
    try {
      const res = await advanceClock(hours, days);
      await onRefresh();
      const tr = res?.tick_result || {};
      const parts: string[] = [];
      if (tr.rules_fired) parts.push(`${tr.rules_fired} scheduled rule(s) executed`);
      if (tr.depletions_fired) parts.push(`${tr.depletions_fired} depletion restock(s) triggered`);
      if (tr.orders_delivered) parts.push(`${tr.orders_delivered} order(s) delivered to inventory`);
      if (tr.approvals_expired) parts.push(`${tr.approvals_expired} approval(s) expired`);

      const summary = parts.length > 0 ? parts.join(" · ") : "Stock decay & SLA timers updated";
      onNotify(
        `Virtual clock advanced +${days > 0 ? `${days}d` : `${hours}h`}: ${summary}.`,
        parts.length > 0 ? "success" : "info"
      );
    } catch (e: any) {
      onNotify(e.message || "Failed to advance virtual clock", "error");
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    setBusy(true);
    try {
      await resetDemoScenario();
      await onRefresh();
      onNotify(
        "Scenario reset to initial state ($200.00 PayPal Sandbox balance, 3 tracked items, Mandate v1).",
        "info"
      );
    } catch (e: any) {
      onNotify(e.message || "Failed to reset demo scenario", "error");
    } finally {
      setBusy(false);
    }
  };

  const formattedTime = clockState?.current_time
    ? new Date(clockState.current_time).toLocaleString("en-US", {
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";

  const isKillActive = Boolean(wallet?.kill_switch);

  return (
    <header className="bg-[#09090b]/95 backdrop-blur border-b border-zinc-800/90 sticky top-0 z-40">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        {/* Left: Brand Identity */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-[#0070ba] flex items-center justify-center text-white font-bold text-sm tracking-tight shrink-0">
            CP
          </div>
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="font-semibold text-sm tracking-tight text-zinc-100">
              CommPal
            </span>
            <span className="text-zinc-600">/</span>
            <span className="text-xs text-zinc-400 truncate hidden sm:inline">
              Autonomous Treasury & Procurement
            </span>
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium border ${
                backendOnline
                  ? "bg-emerald-950/50 text-emerald-400 border-emerald-800/60"
                  : "bg-rose-950/60 text-rose-400 border-rose-800/60"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  backendOnline ? "bg-emerald-400" : "bg-rose-400"
                }`}
              />
              {backendOnline ? "PayPal Sandbox Live" : "API Offline"}
            </span>
          </div>
        </div>

        {/* Right: Operational Controls */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Live Wallet Balance Pill */}
          <div className="hidden lg:flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-md px-2.5 py-1 text-xs tabular-nums">
            <Wallet className="w-3.5 h-3.5 text-[#0070ba]" />
            <span className="text-zinc-400">Available:</span>
            <span className="font-mono font-semibold text-zinc-100">
              ${wallet?.available_balance?.toFixed(2) ?? "0.00"}
            </span>
            {wallet && wallet.held_balance > 0 && (
              <span className="text-[11px] font-mono text-amber-400">
                (${wallet.held_balance.toFixed(2)} held)
              </span>
            )}
          </div>

          {/* Virtual Clock Bar */}
          <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-md p-0.5 text-xs">
            <div className="flex items-center gap-1.5 px-2.5 py-1 text-zinc-300 font-mono tabular-nums">
              <Clock className="w-3.5 h-3.5 text-zinc-400" />
              <span>{formattedTime}</span>
            </div>
            <div className="flex items-center border-l border-zinc-800 pl-1 gap-0.5">
              <button
                type="button"
                disabled={busy}
                onClick={() => handleAdvance(1, 0)}
                className="px-2 py-1 rounded text-[11px] font-mono font-medium text-zinc-300 hover:text-white hover:bg-zinc-800 disabled:opacity-40 transition-colors cursor-pointer"
                title="Advance virtual clock by 1 hour"
              >
                +1h
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => handleAdvance(0, 1)}
                className="px-2 py-1 rounded text-[11px] font-mono font-medium text-zinc-300 hover:text-white hover:bg-zinc-800 disabled:opacity-40 transition-colors cursor-pointer"
                title="Advance virtual clock by 1 day (executes daily rules & deliveries)"
              >
                +1d
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={handleReset}
                className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 disabled:opacity-40 transition-colors cursor-pointer"
                title="Reset scenario to initial state"
              >
                <RotateCcw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Emergency Kill Switch */}
          <button
            type="button"
            onClick={handleToggleKillSwitch}
            disabled={busy}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors cursor-pointer ${
              isKillActive
                ? "bg-rose-600 text-white border-rose-500 hover:bg-rose-500"
                : "bg-zinc-900 text-zinc-300 border-zinc-800 hover:border-rose-800 hover:text-rose-300"
            }`}
          >
            {isKillActive ? (
              <>
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Frozen (Unfreeze)</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>Kill Switch</span>
              </>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
