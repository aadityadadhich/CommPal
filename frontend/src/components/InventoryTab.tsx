"use client";

import React, { useState } from "react";
import {
  Package,
  Plus,
  Minus,
  ShoppingCart,
  AlertTriangle,
  X,
} from "lucide-react";
import { Item } from "@/lib/types";
import {
  updateItemStock,
  createItem,
  requestDirectPurchase,
} from "@/lib/api";
import { TabType } from "@/app/page";

interface InventoryTabProps {
  items: Item[];
  onRefresh: () => Promise<void> | void;
  onNotify: (message: string, tone?: "success" | "warning" | "error" | "info") => void;
  onNavigate: (tab: TabType) => void;
}

export default function InventoryTab({
  items,
  onRefresh,
  onNotify,
  onNavigate,
}: InventoryTabProps) {
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [creating, setCreating] = useState(false);

  const [newName, setNewName] = useState("Coffee 500g");
  const [newUnit, setNewUnit] = useState("bag");
  const [newCategory, setNewCategory] = useState("grocery");
  const [newPerishable, setNewPerishable] = useState(false);
  const [newFulfilment, setNewFulfilment] = useState<"quick" | "standard" | "any">("any");
  const [newStock, setNewStock] = useState("2");
  const [newRate, setNewRate] = useState("0.2");
  const [newThreshold, setNewThreshold] = useState("3");
  const [newReorderQty, setNewReorderQty] = useState("1");

  const applyPreset = (preset: {
    name: string;
    unit: string;
    category: string;
    perishable: boolean;
    stock: string;
    rate: string;
  }) => {
    setNewName(preset.name);
    setNewUnit(preset.unit);
    setNewCategory(preset.category);
    setNewPerishable(preset.perishable);
    setNewStock(preset.stock);
    setNewRate(preset.rate);
  };

  const handleCreateItem = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const res = await createItem({
        name: newName.trim(),
        unit: newUnit.trim() || "unit",
        category: newCategory,
        perishable: newPerishable,
        fulfilment_class: newFulfilment,
        reorder_qty: parseFloat(newReorderQty) || 1,
        threshold_days: parseFloat(newThreshold) || 3,
        rate_per_day: parseFloat(newRate) || 0.2,
        stock_qty: parseFloat(newStock) || 1,
      });
      await onRefresh();
      setShowAddForm(false);
      onNotify(
        `Added '${res.name}' to tracked inventory with automatic depletion monitoring.`,
        "success"
      );
    } catch (err: any) {
      onNotify(err.message || "Failed to create item", "error");
    } finally {
      setCreating(false);
    }
  };

  const handleStockUpdate = async (
    item: Item,
    mode: "absolute" | "delta" | "finished",
    qty: number
  ) => {
    setLoadingId(item.id);
    try {
      const res = await updateItemStock(item.id, mode, qty);
      await onRefresh();

      const trig = res.triggered_order;
      if (trig) {
        if (trig.status === "ORDER_PLACED") {
          onNotify(
            `Depletion triggered! Ordered ${item.name} via ${trig.merchant} ($${trig.amount.toFixed(2)}, ETA ${trig.eta_minutes}m, Capture ${trig.paypal_capture_id}).`,
            "success"
          );
        } else if (trig.status === "PENDING_APPROVAL") {
          onNotify(
            `Depletion triggered for ${item.name}: Order paused for human approval (${trig.message}).`,
            "warning"
          );
        } else if (trig.status === "SUPPRESSED") {
          onNotify(
            `Stock updated to ${res.stock_qty} ${item.unit}. (${trig.message})`,
            "info"
          );
        } else {
          onNotify(
            `Stock updated to ${res.stock_qty} ${item.unit}. Mandate status: ${trig.status} (${trig.message || ""})`,
            "warning"
          );
        }
      } else {
        onNotify(
          `Updated ${item.name} stock to ${res.stock_qty.toFixed(1)} ${item.unit} (${res.days_of_cover} days of cover).`,
          "info"
        );
      }
    } catch (e: any) {
      onNotify(e.message || "Failed to update stock", "error");
    } finally {
      setLoadingId(null);
    }
  };

  const handleDirectOrder = async (item: Item) => {
    setLoadingId(item.id);
    try {
      const res = await requestDirectPurchase({
        item_id: item.id,
        item_name: item.name,
        qty: item.reorder_qty || 1,
        urgency_hint: item.stock_qty <= 0 ? "urgent" : "routine",
      });
      await onRefresh();

      if (res.status === "ORDER_PLACED") {
        onNotify(
          `Order placed: ${item.name} with ${res.merchant} ($${res.amount.toFixed(2)}, PayPal Capture: ${res.paypal_capture_id}).`,
          "success"
        );
      } else if (res.status === "PENDING_APPROVAL") {
        onNotify(
          `Order for ${item.name} requires your approval in the Treasury/Assistant tab.`,
          "warning"
        );
      } else {
        onNotify(res.message || `Order status: ${res.status}`, "error");
      }
    } catch (e: any) {
      onNotify(e.message || "Direct purchase failed", "error");
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="space-y-5">
      {/* Header Card */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
              <Package className="w-4 h-4 text-[#0070ba]" />
              Tracked Inventory & Autonomous Depletion Telemetry
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Stock decays linearly by consumption rate. Clicking{" "}
              <strong className="text-zinc-200">Deplete (0)</strong> immediately triggers an urgent quick-commerce restock through your mandate.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowAddForm((prev) => !prev)}
            className="px-3.5 py-1.5 rounded-md bg-[#0070ba] hover:bg-[#005ea6] text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            {showAddForm ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            <span>{showAddForm ? "Cancel" : "Track New Item"}</span>
          </button>
        </div>

        {/* Add Item Drawer */}
        {showAddForm && (
          <form
            onSubmit={handleCreateItem}
            className="mt-4 pt-4 border-t border-zinc-800 space-y-4"
          >
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-zinc-400">Quick Catalog Presets:</span>
              {[
                {
                  name: "Coffee 500g",
                  unit: "bag",
                  category: "grocery",
                  perishable: false,
                  stock: "2",
                  rate: "0.2",
                },
                {
                  name: "Eggs 12ct",
                  unit: "carton",
                  category: "grocery",
                  perishable: true,
                  stock: "1",
                  rate: "0.5",
                },
                {
                  name: "AA Batteries 8-Pack",
                  unit: "pack",
                  category: "supplies",
                  perishable: false,
                  stock: "3",
                  rate: "0.1",
                },
                {
                  name: "Laundry Detergent 2L",
                  unit: "bottle",
                  category: "supplies",
                  perishable: false,
                  stock: "2",
                  rate: "0.1",
                },
              ].map((p) => (
                <button
                  key={p.name}
                  type="button"
                  onClick={() => applyPreset(p)}
                  className="px-2.5 py-1 rounded bg-zinc-950 hover:bg-zinc-800 text-zinc-300 border border-zinc-800 text-[11px] cursor-pointer"
                >
                  {p.name}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 text-xs">
              <div className="lg:col-span-2">
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Item Name (Catalog Match)
                </label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 focus:outline-none focus:border-[#0070ba]"
                />
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">Unit</label>
                <input
                  type="text"
                  value={newUnit}
                  onChange={(e) => setNewUnit(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 focus:outline-none focus:border-[#0070ba]"
                />
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">Category</label>
                <select
                  value={newCategory}
                  onChange={(e) => setNewCategory(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 text-zinc-100 focus:outline-none focus:border-[#0070ba]"
                >
                  <option value="grocery">grocery</option>
                  <option value="supplies">supplies</option>
                  <option value="fitness">fitness</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Initial Stock
                </label>
                <input
                  type="number"
                  step="0.5"
                  value={newStock}
                  onChange={(e) => setNewStock(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 font-mono text-zinc-100 focus:outline-none focus:border-[#0070ba]"
                />
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Use Rate / Day
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={newRate}
                  onChange={(e) => setNewRate(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-1.5 font-mono text-zinc-100 focus:outline-none focus:border-[#0070ba]"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-1">
              <label className="flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newPerishable}
                  onChange={(e) => setNewPerishable(e.target.checked)}
                  className="rounded border-zinc-700 bg-zinc-950"
                />
                <span>Perishable item (requires rapid delivery SLA)</span>
              </label>
              <button
                type="submit"
                disabled={creating}
                className="px-4 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium cursor-pointer"
              >
                {creating ? "Saving..." : "Save Tracked Item"}
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Inventory Table */}
      <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs tabular-nums">
            <thead className="bg-zinc-950/90 text-zinc-400 uppercase font-mono text-[11px] border-b border-zinc-800">
              <tr>
                <th className="py-3 px-4">Item & Specification</th>
                <th className="py-3 px-4">Current Stock</th>
                <th className="py-3 px-4">Days of Cover</th>
                <th className="py-3 px-4">Est. Confidence</th>
                <th className="py-3 px-4">Automation</th>
                <th className="py-3 px-4 text-right">Stock & Order Controls</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/70">
              {items.map((it) => {
                const isUrgent = it.days_of_cover < 2.0 || it.stock_qty <= 0;
                const isLow = it.days_of_cover <= it.threshold_days;
                const busy = loadingId === it.id;

                return (
                  <tr
                    key={it.id}
                    className="hover:bg-zinc-900/80 transition-colors"
                  >
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-zinc-100 text-sm">
                        {it.name}
                      </div>
                      <div className="text-[11px] text-zinc-400 flex items-center gap-2 mt-0.5">
                        <span className="uppercase font-mono text-[10px] px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-300">
                          {it.category}
                        </span>
                        <span>
                          {it.perishable ? "Perishable (Quick SLA)" : "Shelf-stable"}
                        </span>
                        {it.spec?.brand_pref && (
                          <span className="text-zinc-500">
                            · Pref: {it.spec.brand_pref}
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="py-3.5 px-4 font-mono">
                      <div className="text-sm font-semibold text-zinc-100">
                        {it.stock_qty.toFixed(1)}{" "}
                        <span className="text-xs text-zinc-400 font-normal">
                          {it.unit}
                        </span>
                      </div>
                      <div className="text-[11px] text-zinc-500">
                        Burn: {it.rate_per_day}/day
                      </div>
                    </td>

                    <td className="py-3.5 px-4 w-52">
                      <div className="flex items-center justify-between font-mono text-[11px] mb-1.5">
                        <span
                          className={`font-semibold ${
                            isUrgent
                              ? "text-rose-400"
                              : isLow
                              ? "text-amber-400"
                              : "text-emerald-400"
                          }`}
                        >
                          {it.days_of_cover}d cover
                        </span>
                        <span className="text-zinc-500 text-[10px]">
                          Trigger &le; {it.threshold_days}d
                        </span>
                      </div>
                      <div className="w-full bg-zinc-800 rounded-full h-1.5 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-300 ${
                            isUrgent
                              ? "bg-rose-500"
                              : isLow
                              ? "bg-amber-400"
                              : "bg-emerald-500"
                          }`}
                          style={{
                            width: `${Math.min(100, (it.days_of_cover / 14) * 100)}%`,
                          }}
                        />
                      </div>
                    </td>

                    <td className="py-3.5 px-4 font-mono">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`w-2 h-2 rounded-full ${
                            it.stock_confidence > 0.7
                              ? "bg-emerald-400"
                              : it.stock_confidence > 0.4
                              ? "bg-amber-400"
                              : "bg-rose-400"
                          }`}
                        />
                        <span className="text-zinc-200">
                          {Math.round(it.stock_confidence * 100)}%
                        </span>
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-0.5">
                        Sensor / time model
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      {it.active_rules_count > 0 ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-950/60 text-emerald-400 border border-emerald-800/60">
                          {it.active_rules_count} Active Rule(s)
                        </span>
                      ) : (
                        <span className="text-zinc-500 font-mono text-[11px]">
                          Manual
                        </span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          type="button"
                          disabled={busy || it.stock_qty <= 0}
                          onClick={() => handleStockUpdate(it, "delta", -1)}
                          className="p-1.5 rounded bg-zinc-950 hover:bg-zinc-800 disabled:opacity-40 text-zinc-300 border border-zinc-800 transition-colors cursor-pointer"
                          title="Subtract 1 unit"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleStockUpdate(it, "delta", 1)}
                          className="p-1.5 rounded bg-zinc-950 hover:bg-zinc-800 disabled:opacity-40 text-zinc-300 border border-zinc-800 transition-colors cursor-pointer"
                          title="Add 1 unit"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleStockUpdate(it, "finished", 0)}
                          className="px-2.5 py-1.5 rounded bg-rose-950/60 hover:bg-rose-900 disabled:opacity-40 text-rose-300 hover:text-white border border-rose-800/60 text-[11px] font-medium transition-colors cursor-pointer"
                          title="Set stock to 0 and immediately trigger autonomous depletion order"
                        >
                          Deplete (0)
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleDirectOrder(it)}
                          className="px-2.5 py-1.5 rounded bg-[#0070ba] hover:bg-[#005ea6] disabled:opacity-40 text-white text-[11px] font-medium inline-flex items-center gap-1 transition-colors cursor-pointer"
                          title="Run multi-merchant router & mandate to order now"
                        >
                          <ShoppingCart className="w-3 h-3" />
                          <span>Order Now</span>
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
    </div>
  );
}
