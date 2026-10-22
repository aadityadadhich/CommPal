"use client";

import React, { useState } from "react";
import { 
  Package, AlertTriangle, CheckCircle2, Clock, 
  RotateCcw, Sparkles, TrendingDown, Plus 
} from "lucide-react";
import { Item } from "@/lib/types";
import { updateItemStock } from "@/lib/api";

interface InventoryTabProps {
  items: Item[];
  onRefresh: () => void;
}

export default function InventoryTab({ items, onRefresh }: InventoryTabProps) {
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const handleStockUpdate = async (itemId: string, mode: "absolute" | "delta" | "finished", qty: number) => {
    setLoadingId(itemId);
    try {
      await updateItemStock(itemId, mode, qty);
      onRefresh();
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Package className="w-5 h-5 text-blue-400" />
            Tracked Household & Office Inventory
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Dynamic depletion monitoring: stock is calculated from consumption rates, and days of cover drive urgency routing.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-950/70 text-slate-400 text-xs uppercase font-mono tracking-wider border-b border-slate-800">
            <tr>
              <th className="py-3 px-4">Item & Category</th>
              <th className="py-3 px-4">Current Stock</th>
              <th className="py-3 px-4">Days of Cover</th>
              <th className="py-3 px-4">Confidence</th>
              <th className="py-3 px-4">Active Rules</th>
              <th className="py-3 px-4 text-right">Quick Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-sans">
            {items.map((it) => {
              const isUrgent = it.days_of_cover < 2.0 || it.stock_qty <= 0;
              const isLow = it.days_of_cover <= it.threshold_days;

              return (
                <tr key={it.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-4 px-4">
                    <div className="font-semibold text-white">{it.name}</div>
                    <div className="text-xs text-slate-400 flex items-center gap-2 mt-0.5">
                      <span className="capitalize">{it.category}</span>
                      <span>•</span>
                      <span>{it.perishable ? "Perishable (Morning slot)" : "Shelf-stable"}</span>
                    </div>
                  </td>

                  <td className="py-4 px-4 font-mono font-medium text-slate-200">
                    <div className="text-base font-bold">
                      {it.stock_qty.toFixed(1)} <span className="text-xs text-slate-400 font-normal">{it.unit}</span>
                    </div>
                    <div className="text-[11px] text-slate-400">Rate: {it.rate_per_day}/day</div>
                  </td>

                  <td className="py-4 px-4 w-48">
                    <div className="flex items-center justify-between text-xs font-mono mb-1.5">
                      <span
                        className={`font-semibold ${
                          isUrgent ? "text-rose-400" : isLow ? "text-amber-400" : "text-emerald-400"
                        }`}
                      >
                        {it.days_of_cover} days
                      </span>
                      <span className="text-slate-500 text-[10px]">Thresh: {it.threshold_days}d</span>
                    </div>
                    <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-300 ${
                          isUrgent ? "bg-rose-500" : isLow ? "bg-amber-400" : "bg-emerald-500"
                        }`}
                        style={{ width: `${Math.min(100, (it.days_of_cover / 14) * 100)}%` }}
                      ></div>
                    </div>
                  </td>

                  <td className="py-4 px-4">
                    <div className="flex items-center gap-1.5 text-xs font-mono">
                      <div
                        className={`w-2 h-2 rounded-full ${
                          it.stock_confidence > 0.7
                            ? "bg-emerald-400"
                            : it.stock_confidence > 0.4
                            ? "bg-amber-400"
                            : "bg-rose-400"
                        }`}
                      ></div>
                      <span className="text-slate-300">{Math.round(it.stock_confidence * 100)}%</span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">Linear decay</div>
                  </td>

                  <td className="py-4 px-4">
                    {it.active_rules_count > 0 ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {it.active_rules_count} Scheduled
                      </span>
                    ) : (
                      <span className="text-xs text-slate-500 font-mono">None</span>
                    )}
                  </td>

                  <td className="py-4 px-4 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <button
                        disabled={loadingId === it.id}
                        onClick={() => handleStockUpdate(it.id, "finished", 0)}
                        className="px-2.5 py-1 rounded bg-rose-950/60 hover:bg-rose-900 text-rose-300 hover:text-white border border-rose-800/60 text-xs font-medium transition-colors"
                        title="Simulate immediate stockout (Forces urgent quick-commerce order)"
                      >
                        Out of Stock
                      </button>
                      <button
                        disabled={loadingId === it.id}
                        onClick={() => handleStockUpdate(it.id, "delta", 1)}
                        className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs border border-slate-700"
                        title="Add 1 unit"
                      >
                        +1
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
