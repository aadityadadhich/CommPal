"use client";

import React, { useState } from "react";
import { 
  ShoppingBag, CheckCircle2, Clock, AlertCircle, 
  ExternalLink, ChevronRight, Eye, Info 
} from "lucide-react";
import { Order } from "@/lib/types";
import { fetchOrderDetail } from "@/lib/api";

interface OrdersTabProps {
  orders: Order[];
}

export default function OrdersTab({ orders }: OrdersTabProps) {
  const [selectedOrder, setSelectedOrder] = useState<any | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const handleInspect = async (orderId: string) => {
    setDetailLoading(true);
    try {
      const data = await fetchOrderDetail(orderId);
      setSelectedOrder(data);
    } catch (e) {
      console.error(e);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <ShoppingBag className="w-5 h-5 text-emerald-400" />
              Autonomous Order Stream & PayPal Settlement
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Every order follows the state machine: Authorized &rarr; Placed &rarr; Captured, with cryptographic ledger records.
            </p>
          </div>
          <span className="font-mono text-xs text-slate-400">{orders.length} orders total</span>
        </div>

        {orders.length === 0 ? (
          <div className="text-center py-12 text-slate-500 text-sm">
            No orders placed yet. Chat with CommPal or trigger a schedule advance from the demo studio.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-950/70 text-slate-400 text-xs uppercase font-mono tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Order ID & Date</th>
                  <th className="py-3 px-4">Item & Qty</th>
                  <th className="py-3 px-4">Winning Merchant</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">State</th>
                  <th className="py-3 px-4">PayPal IDs</th>
                  <th className="py-3 px-4 text-right">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {orders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-mono text-xs">
                      <div className="font-semibold text-slate-200">#{ord.id.slice(-8)}</div>
                      <div className="text-[11px] text-slate-500">
                        {new Date(ord.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <div className="font-medium text-white">{ord.item_name}</div>
                      <div className="text-xs text-slate-400">Qty: {ord.qty}</div>
                    </td>

                    <td className="py-3.5 px-4">
                      <span className="font-semibold text-slate-200">{ord.merchant_name}</span>
                      <div className="text-xs text-slate-400">ETA: {ord.eta_minutes} mins</div>
                    </td>

                    <td className="py-3.5 px-4 font-mono font-bold text-emerald-400">
                      ${ord.amount.toFixed(2)}
                    </td>

                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {ord.state}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                      <div>Auth: <span className="text-blue-300">{ord.paypal_auth_id?.slice(-8) || "N/A"}</span></div>
                      <div>Capt: <span className="text-blue-300">{ord.paypal_capture_id?.slice(-8) || "N/A"}</span></div>
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => handleInspect(ord.id)}
                        className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-xs font-medium inline-flex items-center gap-1 transition-colors"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Decision Inspector Modal / Drawer */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Info className="w-5 h-5 text-blue-400" />
                Transparent Decision & Scoring Breakdown
              </h3>
              <button
                onClick={() => setSelectedOrder(null)}
                className="text-slate-400 hover:text-white text-lg font-bold"
              >
                ✕
              </button>
            </div>

            {/* Explanation box */}
            <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 text-sm text-slate-200 leading-relaxed">
              <span className="font-semibold text-blue-400">Router Explanation: </span>
              {selectedOrder.decision?.explanation}
            </div>

            {/* Mathematical Scores breakdown */}
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2 font-mono">
                Candidate Score Breakdown (0.0 to 1.0)
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="py-2 px-3">Merchant</th>
                      <th className="py-2 px-3">Price Score</th>
                      <th className="py-2 px-3">ETA Score</th>
                      <th className="py-2 px-3">Rating Score</th>
                      <th className="py-2 px-3">Fit Score</th>
                      <th className="py-2 px-3 font-bold text-emerald-400">Total Score</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {selectedOrder.decision?.score_breakdown?.map((b: any, bIdx: number) => (
                      <tr key={bIdx} className={bIdx === 0 ? "bg-emerald-950/20" : ""}>
                        <td className="py-2 px-3 font-semibold text-slate-200">
                          {b.merchant_id} {bIdx === 0 && "🏆 (Chosen)"}
                        </td>
                        <td className="py-2 px-3 text-slate-400">{b.price_score}</td>
                        <td className="py-2 px-3 text-slate-400">{b.eta_score}</td>
                        <td className="py-2 px-3 text-slate-400">{b.rating_score}</td>
                        <td className="py-2 px-3 text-slate-400">{b.fit_score}</td>
                        <td className="py-2 px-3 font-bold text-emerald-400">{b.total_score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedOrder(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
