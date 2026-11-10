"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  MessageSquare,
  LayoutDashboard,
  Package,
  ShoppingBag,
  ShieldCheck,
  Lock,
  Sliders,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  X,
} from "lucide-react";

import Navbar from "../components/Navbar";
import ChatTab from "../components/ChatTab";
import OverviewTab from "../components/OverviewTab";
import InventoryTab from "../components/InventoryTab";
import OrdersTab from "../components/OrdersTab";
import MandateTab from "../components/MandateTab";
import AuditTab from "../components/AuditTab";
import DemoStudioTab from "../components/DemoStudioTab";

import {
  fetchItems,
  fetchWallet,
  fetchOrders,
  fetchApprovals,
  fetchClock,
  fetchMandate,
} from "../lib/api";
import {
  Item,
  WalletSummary,
  Order,
  PendingApproval,
  ClockState,
  MandateBody,
} from "../lib/types";

export type TabType =
  | "chat"
  | "overview"
  | "inventory"
  | "orders"
  | "mandate"
  | "audit"
  | "demo";

interface ToastItem {
  id: string;
  message: string;
  tone: "success" | "warning" | "error" | "info";
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>("chat");
  const [items, setItems] = useState<Item[]>([]);
  const [wallet, setWallet] = useState<WalletSummary | undefined>();
  const [mandate, setMandate] = useState<MandateBody | undefined>();
  const [orders, setOrders] = useState<Order[]>([]);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [clockState, setClockState] = useState<ClockState | undefined>();
  const [backendOnline, setBackendOnline] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState(false);
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const notify = useCallback(
    (message: string, tone: "success" | "warning" | "error" | "info" = "info") => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      setToasts((prev) => [...prev.slice(-3), { id, message, tone }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4500);
    },
    []
  );

  const loadData = useCallback(async () => {
    try {
      setRefreshing(true);
      const [itData, walData, ordData, appData, clkData, manData] = await Promise.all([
        fetchItems(),
        fetchWallet(),
        fetchOrders(),
        fetchApprovals(),
        fetchClock(),
        fetchMandate(),
      ]);
      setItems(itData);
      setWallet(walData);
      setOrders(ordData);
      setApprovals(appData);
      setClockState(clkData);
      setMandate(manData.mandate);
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") {
        return;
      }
      loadData();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  const tabs: {
    id: TabType;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    count?: number;
    alertCount?: number;
  }[] = [
    { id: "chat", label: "Assistant", icon: MessageSquare },
    {
      id: "overview",
      label: "Treasury & Overview",
      icon: LayoutDashboard,
      alertCount: approvals.length > 0 ? approvals.length : undefined,
    },
    {
      id: "inventory",
      label: "Inventory",
      icon: Package,
      count: items.length,
    },
    {
      id: "orders",
      label: "Orders & Routing",
      icon: ShoppingBag,
      count: orders.length > 0 ? orders.length : undefined,
    },
    { id: "mandate", label: "Spending Mandate", icon: ShieldCheck },
    { id: "audit", label: "Audit Chain", icon: Lock },
    { id: "demo", label: "Simulation Studio", icon: Sliders },
  ];

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex flex-col font-sans">
      <Navbar
        clockState={clockState}
        wallet={wallet}
        backendOnline={backendOnline}
        onRefresh={loadData}
        onNotify={notify}
      />

      {/* Sub-header Navigation Bar */}
      <div className="border-b border-zinc-800/80 bg-[#09090b]">
        <div className="max-w-[1400px] w-full mx-auto px-4 sm:px-6 flex items-center justify-between gap-2 overflow-x-auto">
          <nav className="flex items-center gap-1 py-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors shrink-0 cursor-pointer ${
                    isActive
                      ? "bg-zinc-800/90 text-white border border-zinc-700/80"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 border border-transparent"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? "text-[#0070ba]" : "text-zinc-500"}`} />
                  <span>{tab.label}</span>
                  {tab.alertCount !== undefined && (
                    <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono text-[10px] font-semibold">
                      {tab.alertCount}
                    </span>
                  )}
                  {tab.count !== undefined && tab.alertCount === undefined && (
                    <span className="px-1.5 py-0.2 rounded bg-zinc-800 text-zinc-400 font-mono text-[10px]">
                      {tab.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          <button
            type="button"
            onClick={() => {
              loadData();
              notify("Synchronized state with backend ledger.", "info");
            }}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-zinc-900 hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-zinc-800 text-xs transition-colors shrink-0 cursor-pointer"
            title="Sync state"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Sync</span>
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 max-w-[1400px] w-full mx-auto px-4 sm:px-6 py-5">
        {!backendOnline && (
          <div className="mb-4 p-3.5 rounded-lg bg-rose-950/40 border border-rose-800/70 flex items-center justify-between text-xs text-rose-200">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>
                Backend API at <code className="font-mono text-rose-100">http://127.0.0.1:8000</code> is unreachable. Ensure FastAPI is running.
              </span>
            </div>
            <button
              type="button"
              onClick={loadData}
              className="px-2.5 py-1 rounded bg-rose-900/60 hover:bg-rose-800 text-white font-medium cursor-pointer"
            >
              Retry Connection
            </button>
          </div>
        )}

        {activeTab === "chat" && (
          <ChatTab
            wallet={wallet}
            items={items}
            approvals={approvals}
            onRefresh={loadData}
            onNotify={notify}
            onNavigate={(t) => setActiveTab(t)}
          />
        )}
        {activeTab === "overview" && (
          <OverviewTab
            wallet={wallet}
            mandate={mandate}
            approvals={approvals}
            orders={orders}
            onRefresh={loadData}
            onNotify={notify}
            onNavigate={(t) => setActiveTab(t)}
          />
        )}
        {activeTab === "inventory" && (
          <InventoryTab
            items={items}
            onRefresh={loadData}
            onNotify={notify}
            onNavigate={(t) => setActiveTab(t)}
          />
        )}
        {activeTab === "orders" && (
          <OrdersTab
            orders={orders}
            approvals={approvals}
            onRefresh={loadData}
            onNotify={notify}
          />
        )}
        {activeTab === "mandate" && (
          <MandateTab onRefresh={loadData} onNotify={notify} />
        )}
        {activeTab === "audit" && <AuditTab onNotify={notify} />}
        {activeTab === "demo" && (
          <DemoStudioTab
            onRefresh={loadData}
            onNotify={notify}
            onNavigate={(t) => setActiveTab(t)}
          />
        )}
      </main>

      {/* Global Toast Notification Stack */}
      {toasts.length > 0 && (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md w-full pointer-events-none px-4 sm:px-0">
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-start justify-between gap-3 p-3.5 rounded-lg border shadow-xl text-xs backdrop-blur-md ${
                t.tone === "success"
                  ? "bg-zinc-900/95 border-emerald-700/70 text-zinc-100"
                  : t.tone === "warning"
                  ? "bg-zinc-900/95 border-amber-700/70 text-zinc-100"
                  : t.tone === "error"
                  ? "bg-zinc-900/95 border-rose-700/70 text-zinc-100"
                  : "bg-zinc-900/95 border-zinc-700 text-zinc-100"
              }`}
            >
              <div className="flex items-start gap-2.5">
                {t.tone === "success" && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />}
                {t.tone === "warning" && <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />}
                {t.tone === "error" && <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />}
                {t.tone === "info" && <Info className="w-4 h-4 text-[#0070ba] shrink-0 mt-0.5" />}
                <span className="leading-relaxed">{t.message}</span>
              </div>
              <button
                type="button"
                onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
                className="text-zinc-500 hover:text-zinc-200 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
