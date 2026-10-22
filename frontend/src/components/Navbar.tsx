"use client";

import React, { useState } from "react";
import { 
  ShieldCheck, ShieldAlert, Clock, RefreshCw, FastForward, 
  Wallet, Zap, Activity 
} from "lucide-react";
import { ClockState, WalletSummary } from "../lib/types";
import { toggleKillSwitch, advanceClock, resetDemoScenario } from "../lib/api";

interface NavbarProps {
  clockState?: ClockState;
  wallet?: WalletSummary;
  onRefresh: () => void;
}

export default function Navbar({ clockState, wallet, onRefresh }: NavbarProps) {
  const [loadingAction, setLoadingAction] = useState(false);

  const handleToggleKillSwitch = async () => {
    if (!wallet) return;
    setLoadingAction(true);
    try {
      await toggleKillSwitch(!wallet.kill_switch);
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingAction(false);
    }
  };

  const handleAdvance = async (hours: number, days: number = 0) => {
    setLoadingAction(true);
    try {
      await advanceClock(hours, days);
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingAction(false);
    }
  };

  const handleReset = async () => {
    if (!confirm("Reset demo environment to the 'Week with Asha' initial state?")) return;
    setLoadingAction(true);
    try {
      await resetDemoScenario();
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingAction(false);
    }
  };

  const formattedTime = clockState?.current_time
    ? new Date(clockState.current_time).toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true,
      })
    : "Simulating...";

  const isKillActive = wallet?.kill_switch;

  return (
    <header className="bg-slate-900 border-b border-slate-800 text-white sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Logo & Philosophy Badge */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-blue-200 bg-clip-text text-transparent">
                  CommPal
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  PayPal AI Hackathon
                </span>
              </div>
              <p className="text-xs text-slate-400">
                The agent proposes • The mandate decides • The wallet pays
              </p>
            </div>
          </div>

          {/* Controls: Clock + Sandbox Badge + Kill Switch */}
          <div className="flex items-center flex-wrap gap-2.5">
            {/* Virtual Clock Display */}
            <div className="flex items-center space-x-2 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700 text-xs">
              <Clock className="w-4 h-4 text-amber-400 animate-pulse" />
              <div className="flex flex-col">
                <span className="text-[10px] uppercase tracking-wider text-slate-400">Virtual Clock</span>
                <span className="font-mono font-medium text-slate-200">{formattedTime}</span>
              </div>
              <div className="flex items-center space-x-1 pl-2 border-l border-slate-700">
                <button
                  disabled={loadingAction}
                  onClick={() => handleAdvance(1)}
                  className="px-1.5 py-0.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 font-mono text-[11px] transition-colors"
                  title="Advance 1 Hour"
                >
                  +1h
                </button>
                <button
                  disabled={loadingAction}
                  onClick={() => handleAdvance(0, 1)}
                  className="px-1.5 py-0.5 rounded bg-slate-700 hover:bg-slate-600 text-slate-200 font-mono text-[11px] transition-colors"
                  title="Advance 1 Day (Triggers Daily Rules)"
                >
                  +1d
                </button>
                <button
                  disabled={loadingAction}
                  onClick={handleReset}
                  className="p-1 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors"
                  title="Reset Demo Scenario"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Sandbox Provider Chip */}
            <div className="hidden sm:flex items-center space-x-1.5 bg-blue-950/40 border border-blue-800/60 text-blue-300 px-3 py-1.5 rounded-lg text-xs">
              <Activity className="w-3.5 h-3.5 text-blue-400" />
              <span>PayPal Sandbox</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block"></span>
            </div>

            {/* Emergency Kill Switch */}
            <button
              onClick={handleToggleKillSwitch}
              disabled={loadingAction}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-xs font-semibold tracking-wide uppercase transition-all duration-200 ${
                isKillActive
                  ? "bg-rose-600 text-white shadow-lg shadow-rose-600/50 ring-2 ring-rose-400 animate-pulse"
                  : "bg-slate-800 text-slate-300 hover:bg-rose-950 hover:text-rose-300 border border-slate-700 hover:border-rose-800"
              }`}
            >
              {isKillActive ? (
                <>
                  <ShieldAlert className="w-4 h-4 text-white" />
                  <span>KILL SWITCH: FROZEN</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  <span>Kill Switch</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
