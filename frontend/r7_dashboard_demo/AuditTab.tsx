"use client";

import React, { useState, useEffect } from "react";
import { 
  ShieldCheck, ShieldAlert, CheckCircle2, Lock, 
  RefreshCw, FileText, Key 
} from "lucide-react";
import { AuditEvent } from "@/lib/types";
import { fetchAuditTrail, verifyAuditIntegrity } from "@/lib/api";

export default function AuditTab() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [verification, setVerification] = useState<{
    is_valid: boolean;
    message: string;
    events_count: number;
  } | null>(null);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    loadAudit();
  }, []);

  const loadAudit = async () => {
    try {
      const data = await fetchAuditTrail();
      setEvents(data);
      handleVerify();
    } catch (e) {
      console.error(e);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    try {
      const res = await verifyAuditIntegrity();
      setVerification(res);
    } catch (e) {
      console.error(e);
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Lock className="w-5 h-5 text-indigo-400" />
            Cryptographic SHA-256 Hash-Chained Audit Trail
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Every user command, mandate verdict, PayPal authorization, and merchant order is appended to an immutable chain.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {verification && (
            <div
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-semibold border ${
                verification.is_valid
                  ? "bg-emerald-950/40 border-emerald-500/40 text-emerald-400"
                  : "bg-rose-950/40 border-rose-500/40 text-rose-400"
              }`}
            >
              {verification.is_valid ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <ShieldAlert className="w-4 h-4 text-rose-400" />
              )}
              <span>{verification.message}</span>
            </div>
          )}

          <button
            onClick={handleVerify}
            disabled={verifying}
            className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold border border-slate-700 flex items-center gap-2 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${verifying ? "animate-spin" : ""}`} />
            <span>Verify Integrity</span>
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider border-b border-slate-800">
            <tr>
              <th className="py-3 px-3">Seq</th>
              <th className="py-3 px-3">Timestamp</th>
              <th className="py-3 px-3">Actor</th>
              <th className="py-3 px-3">Event Type</th>
              <th className="py-3 px-3">Payload Summary</th>
              <th className="py-3 px-3">Current Hash (SHA-256)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {events.map((e) => (
              <tr key={e.seq} className="hover:bg-slate-800/40 transition-colors">
                <td className="py-3 px-3 text-slate-400">#{e.seq}</td>
                <td className="py-3 px-3 text-slate-400">
                  {new Date(e.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                </td>
                <td className="py-3 px-3">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      e.actor === "user"
                        ? "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                        : e.actor === "agent"
                        ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                        : "bg-slate-700/50 text-slate-300"
                    }`}
                  >
                    {e.actor}
                  </span>
                </td>
                <td className="py-3 px-3 font-semibold text-white">{e.event_type}</td>
                <td className="py-3 px-3 text-slate-300 max-w-xs truncate">
                  {JSON.stringify(e.payload)}
                </td>
                <td className="py-3 px-3 text-slate-400">
                  <span className="text-emerald-400 font-semibold">{e.hash.slice(0, 10)}</span>
                  <span className="text-slate-600">...{e.hash.slice(-6)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
