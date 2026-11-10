"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  Lock,
  RefreshCw,
} from "lucide-react";
import { AuditEvent } from "@/lib/types";
import { fetchAuditTrail, verifyAuditIntegrity } from "@/lib/api";

interface AuditTabProps {
  onNotify: (message: string, tone?: "success" | "warning" | "error" | "info") => void;
}

export default function AuditTab({ onNotify }: AuditTabProps) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [verification, setVerification] = useState<{
    is_valid: boolean;
    message: string;
    events_count: number;
  } | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [actorFilter, setActorFilter] = useState<string>("ALL");

  useEffect(() => {
    loadAudit(false);
  }, []);

  const loadAudit = async (showToast: boolean = true) => {
    setVerifying(true);
    try {
      const [data, ver] = await Promise.all([
        fetchAuditTrail(),
        verifyAuditIntegrity(),
      ]);
      setEvents(data);
      setVerification(ver);
      if (showToast) {
        onNotify(
          `${ver.message} (${ver.events_count} cryptographic events verified).`,
          ver.is_valid ? "success" : "error"
        );
      }
    } catch (e: any) {
      onNotify(e.message || "Failed to verify audit trail", "error");
    } finally {
      setVerifying(false);
    }
  };

  const filteredEvents = events.filter((e) =>
    actorFilter === "ALL" ? true : e.actor === actorFilter
  );

  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
            <Lock className="w-4 h-4 text-[#0070ba]" />
            Cryptographic SHA-256 Hash-Chained Audit Ledger
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Every event digest commits to <code className="font-mono text-zinc-300">SHA256(prev_hash | seq | ts | actor | event_type | canonical_payload | mandate_version)</code>.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {verification && (
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono border ${
                verification.is_valid
                  ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-300"
                  : "bg-rose-950/40 border-rose-800/60 text-rose-300"
              }`}
            >
              {verification.is_valid ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              ) : (
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
              )}
              <span>
                {verification.message} ({verification.events_count} blocks)
              </span>
            </div>
          )}

          <button
            type="button"
            onClick={() => loadAudit(true)}
            disabled={verifying}
            className="px-3.5 py-1.5 rounded-md bg-[#0070ba] hover:bg-[#005ea6] text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${verifying ? "animate-spin" : ""}`} />
            <span>Verify Hash Chain</span>
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-800 rounded-md p-0.5 w-fit text-xs">
        {["ALL", "user", "agent", "scheduler", "system"].map((act) => (
          <button
            key={act}
            type="button"
            onClick={() => setActorFilter(act)}
            className={`px-2.5 py-1 rounded font-mono text-[11px] transition-colors cursor-pointer ${
              actorFilter === act
                ? "bg-zinc-800 text-white font-medium"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {act.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="overflow-x-auto border border-zinc-800 rounded-md">
        <table className="w-full text-left text-xs font-mono tabular-nums">
          <thead className="bg-zinc-950 text-zinc-400 uppercase text-[11px] border-b border-zinc-800">
            <tr>
              <th className="py-2.5 px-3">Seq</th>
              <th className="py-2.5 px-3">Timestamp</th>
              <th className="py-2.5 px-3">Actor</th>
              <th className="py-2.5 px-3">Event Type</th>
              <th className="py-2.5 px-3">Canonical Payload</th>
              <th className="py-2.5 px-3">Prev Hash &rarr; Current Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/70 bg-zinc-900/30">
            {filteredEvents.map((e) => (
              <tr key={e.seq} className="hover:bg-zinc-900/90 transition-colors">
                <td className="py-2.5 px-3 text-zinc-400">#{e.seq}</td>
                <td className="py-2.5 px-3 text-zinc-400">
                  {new Date(e.ts).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: false,
                  })}
                </td>
                <td className="py-2.5 px-3">
                  <span className="px-1.5 py-0.5 rounded bg-zinc-950 border border-zinc-800 text-[10px] text-zinc-300 uppercase">
                    {e.actor}
                  </span>
                </td>
                <td className="py-2.5 px-3 font-semibold text-zinc-100">
                  {e.event_type}
                </td>
                <td className="py-2.5 px-3 text-zinc-300 max-w-md truncate">
                  {JSON.stringify(e.payload)}
                </td>
                <td className="py-2.5 px-3 text-[11px] text-zinc-400">
                  <span className="text-zinc-500">{e.prev_hash.slice(0, 8)}</span>
                  <span className="mx-1 text-zinc-600">&rarr;</span>
                  <span className="text-emerald-400 font-semibold">
                    {e.hash.slice(0, 12)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
