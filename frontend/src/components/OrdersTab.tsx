"use client";

import React, { useState } from "react";
import {
  ShoppingBag,
  Eye,
  X,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from "lucide-react";
import { Order, PendingApproval } from "@/lib/types";
import { fetchOrderDetail, actOnApproval } from "@/lib/api";

interface OrdersTabProps {
  orders: Order[];
  approvals: PendingApproval[];
  onRefresh: () => Promise<void> | void;
  onNotify: (message: string, tone?: "success" | "warning" | "error" | "info") => void;
}

export default function OrdersTab({
  orders,
  approvals,
  onRefresh,
  onNotify,
}: OrdersTabProps) {
  const [selectedOrder, setSelectedOrder] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [stateFilter, setStateFilter] = useState<"ALL" | "IN_TRANSIT" | "DELIVERED">("ALL");

  const handleInspect = async (orderId: string) => {
    setDetailLoading(true);
    try {
      const data = await fetchOrderDetail(orderId);
      setSelectedOrder(data);
    } catch (e: any) {
      onNotify(e.message || "Failed to load routing breakdown", "error");
    } finally {
      setDetailLoading(false);
    }
  };

  const handleApproval = async (intentId: string, action: "approve" | "reject") => {
    try {
      const res = await actOnApproval(intentId, action);
      await onRefresh();
      if (action === "approve" && res.status === "ORDER_PLACED") {
        onNotify(
          `Approved! Order placed with ${res.merchant} ($${res.amount.toFixed(2)}, Capture: ${res.paypal_capture_id}).`,
          "success"
        );
      } else {
        onNotify(`Intent ${intentId} ${action}d.`, "info");
      }
    } catch (e: any) {
      onNotify(e.message || "Failed to process approval", "error");
    }
  };

  const filteredOrders = orders.filter((o) =>
    stateFilter === "ALL" ? true : o.state === stateFilter
  );

  return (
    <div className="space-y-5">
      {/* Pending Approvals Banner if any */}
      {approvals.length > 0 && (
        <div className="bg-amber-950/20 border border-amber-700/60 rounded-lg p-4 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-300">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Orders Awaiting Your Approval ({approvals.length})</span>
          </div>
          <div className="divide-y divide-zinc-800 border border-zinc-800 rounded bg-zinc-900">
            {approvals.map((a) => (
              <div
                key={a.approval_id}
                className="p-3 flex flex-wrap items-center justify-between gap-3 text-xs"
              >
                <div>
                  <span className="font-semibold text-zinc-100">
                    {a.item_name} (Qty: {a.qty})
                  </span>
                  <p className="text-zinc-400 text-[11px] mt-0.5">{a.explanation}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => handleApproval(a.intent_id, "approve")}
                    className="px-3 py-1 rounded bg-[#0070ba] hover:bg-[#005ea6] text-white font-medium cursor-pointer"
                  >
                    Approve & Settle
                  </button>
                  <button
                    type="button"
                    onClick={() => handleApproval(a.intent_id, "reject")}
                    className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 cursor-pointer"
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Orders Table Card */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-[#0070ba]" />
              Order Execution Stream & Multi-Merchant Routing Decisions
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Every order records its two-step PayPal Sandbox settlement (Authorize &rarr; Capture) and mathematical merchant scoring breakdown.
            </p>
          </div>

          <div className="flex items-center gap-1 bg-zinc-950 border border-zinc-800 rounded-md p-0.5 text-xs">
            {(["ALL", "IN_TRANSIT", "DELIVERED"] as const).map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStateFilter(st)}
                className={`px-2.5 py-1 rounded font-mono text-[11px] transition-colors cursor-pointer ${
                  stateFilter === st
                    ? "bg-zinc-800 text-white font-medium"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {st === "ALL" ? `All (${orders.length})` : st.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {filteredOrders.length === 0 ? (
          <div className="py-12 text-center border border-dashed border-zinc-800 rounded-md text-xs text-zinc-400">
            No matching orders found. Trigger a purchase from the Assistant or Inventory tab, or advance the Virtual Clock.
          </div>
        ) : (
          <div className="overflow-x-auto border border-zinc-800 rounded-md">
            <table className="w-full text-left text-xs tabular-nums">
              <thead className="bg-zinc-950 text-zinc-400 uppercase font-mono text-[11px] border-b border-zinc-800">
                <tr>
                  <th className="py-3 px-4">Order Ref</th>
                  <th className="py-3 px-4">Item & Qty</th>
                  <th className="py-3 px-4">Selected Merchant</th>
                  <th className="py-3 px-4">Landed Total</th>
                  <th className="py-3 px-4">Fulfilment State</th>
                  <th className="py-3 px-4">PayPal v2 Settlement IDs</th>
                  <th className="py-3 px-4 text-right">Routing Audit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/70 bg-zinc-900/30">
                {filteredOrders.map((ord) => (
                  <tr
                    key={ord.id}
                    className="hover:bg-zinc-900/90 transition-colors"
                  >
                    <td className="py-3.5 px-4 font-mono">
                      <div className="font-semibold text-zinc-200">{ord.id}</div>
                      <div className="text-[11px] text-zinc-500">
                        {new Date(ord.created_at).toLocaleString([], {
                          month: "short",
                          day: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="font-medium text-zinc-100">{ord.item_name}</div>
                      <div className="text-[11px] text-zinc-400 font-mono">
                        Qty: {ord.qty} · Ref: {ord.merchant_order_ref}
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-zinc-200">
                        {ord.merchant_name}
                      </div>
                      <div className="text-[11px] text-zinc-400 font-mono">
                        SLA ETA: {ord.eta_minutes} mins
                      </div>
                    </td>

                    <td className="py-3.5 px-4 font-mono font-semibold text-emerald-400 text-sm">
                      ${ord.amount.toFixed(2)}
                    </td>

                    <td className="py-3.5 px-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] font-medium border ${
                          ord.state === "DELIVERED"
                            ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                            : "bg-blue-950/60 text-blue-300 border-blue-800/60"
                        }`}
                      >
                        {ord.state}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 font-mono text-[11px] text-zinc-400">
                      <div>
                        Auth:{" "}
                        <span className="text-zinc-200">
                          {ord.paypal_auth_id || "—"}
                        </span>
                      </div>
                      <div>
                        Capt:{" "}
                        <span className="text-zinc-200">
                          {ord.paypal_capture_id || "—"}
                        </span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        disabled={detailLoading}
                        onClick={() => handleInspect(ord.id)}
                        className="px-2.5 py-1.5 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-200 border border-zinc-800 text-xs font-medium inline-flex items-center gap-1.5 transition-colors cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5 text-[#0070ba]" />
                        <span>Why this merchant?</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Decision Inspector Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg max-w-2xl w-full p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-zinc-100">
                  Routing & SLA Scoring Breakdown — Order {selectedOrder.order?.id}
                </h3>
                <p className="text-[11px] text-zinc-400 font-mono mt-0.5">
                  PayPal Auth: {selectedOrder.order?.paypal_auth_id} · Capture:{" "}
                  {selectedOrder.order?.paypal_capture_id}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                className="p-1 text-zinc-400 hover:text-white cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3.5 rounded bg-zinc-950 border border-zinc-800 text-xs text-zinc-200 leading-relaxed">
              <span className="font-semibold text-[#0070ba]">
                Router Explanation:{" "}
              </span>
              {selectedOrder.decision?.explanation ||
                "Selected optimal offer matching SLA and budget constraints."}
            </div>

            {/* Candidate Score Breakdown */}
            <div className="space-y-2">
              <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">
                Qualified Merchant Candidates (Weighted 0.00 – 1.00)
              </div>
              <div className="overflow-x-auto border border-zinc-800 rounded">
                <table className="w-full text-left text-xs font-mono tabular-nums">
                  <thead className="bg-zinc-950 text-zinc-400 border-b border-zinc-800">
                    <tr>
                      <th className="py-2 px-3">Merchant</th>
                      <th className="py-2 px-3">Price</th>
                      <th className="py-2 px-3">ETA</th>
                      <th className="py-2 px-3">Rating</th>
                      <th className="py-2 px-3">Spec Fit</th>
                      <th className="py-2 px-3 text-emerald-400">Total Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800">
                    {selectedOrder.decision?.score_breakdown?.map(
                      (b: any, bIdx: number) => (
                        <tr
                          key={bIdx}
                          className={bIdx === 0 ? "bg-emerald-950/20" : ""}
                        >
                          <td className="py-2 px-3 font-semibold text-zinc-100 flex items-center gap-1.5">
                            {bIdx === 0 && (
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                            )}
                            <span className="capitalize">{b.merchant_id}</span>
                            {bIdx === 0 && (
                              <span className="text-[10px] text-emerald-400 font-normal">
                                (Winner)
                              </span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-zinc-300">
                            {b.price_score.toFixed(2)}
                          </td>
                          <td className="py-2 px-3 text-zinc-300">
                            {b.eta_score.toFixed(2)}
                          </td>
                          <td className="py-2 px-3 text-zinc-300">
                            {b.rating_score.toFixed(2)}
                          </td>
                          <td className="py-2 px-3 text-zinc-300">
                            {b.fit_score.toFixed(2)}
                          </td>
                          <td className="py-2 px-3 font-bold text-emerald-400">
                            {b.total_score.toFixed(3)}
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Filtered Out Merchants */}
            {selectedOrder.decision?.filtered_out &&
              Object.keys(selectedOrder.decision.filtered_out).length > 0 && (
                <div className="space-y-2">
                  <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">
                    Disqualified / Filtered-Out Merchants (Hard SLA & Mandate Filters)
                  </div>
                  <div className="divide-y divide-zinc-800 border border-zinc-800 rounded bg-zinc-950 text-xs font-mono">
                    {Object.entries(selectedOrder.decision.filtered_out).map(
                      ([mId, reason]: [string, any]) => (
                        <div
                          key={mId}
                          className="p-2.5 flex items-center justify-between gap-4"
                        >
                          <span className="text-rose-400 flex items-center gap-1.5 capitalize">
                            <XCircle className="w-3.5 h-3.5 shrink-0" />
                            {mId}
                          </span>
                          <span className="text-zinc-400 text-[11px]">
                            {String(reason)}
                          </span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}

            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                className="px-4 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-100 text-xs font-medium cursor-pointer"
              >
                Close Breakdown
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
