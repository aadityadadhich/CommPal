"use client";

import React, { useState, useEffect } from "react";
import { 
  MessageSquare, LayoutDashboard, Package, ShoppingBag, 
  ShieldCheck, Lock, Sliders, RefreshCw, AlertCircle 
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
  fetchItems, fetchWallet, fetchOrders, 
  fetchApprovals, fetchClock 
} from "../lib/api";
import { Item, WalletSummary, Order, PendingApproval, ClockState } from "../lib/types";

type TabType = "chat" | "overview" | "inventory" | "orders" | "mandate" | "audit" | "demo";

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>("chat");
  const [items, setItems] = useState<Item[]>([]);
  const [wallet, setWallet] = useState<WalletSummary | undefined>();
  const [orders, setOrders] = useState<Order[]>([]);
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [clockState, setClockState] = useState<ClockState | undefined>();
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      setRefreshing(true);
      const [itData, walData, ordData, appData, clkData] = await Promise.all([
        fetchItems().catch(() => []),
        fetchWallet().catch(() => undefined),
        fetchOrders().catch(() => []),
        fetchApprovals().catch(() => []),
        fetchClock().catch(() => undefined),
      ]);
      setItems(itData);
      setWallet(walData);
      setOrders(ordData);
      setApprovals(appData);
      setClockState(clkData);
    } catch (e) {
      console.error(e);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
    // Periodic poll every 5s for live simulation updates
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const tabs = [
    { id: "chat", label: "Assistant", icon: MessageSquare },
    { 
      id: "overview", 
      label: "Overview & Wallet", 
      icon: LayoutDashboard,
      badge: approvals.length > 0 ? approvals.length : undefined
    },
    { id: "inventory", label: "Inventory", icon: Package },
    { id: "orders", label: "Orders & Routing", icon: ShoppingBag },
    { id: "mandate", label: "Mandate Policy", icon: ShieldCheck },
    { id: "audit", label: "Audit Ledger", icon: Lock },
    { id: "demo", label: "Demo Studio", icon: Sliders },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-500 selection:text-white">
      {/* Top Navbar */}
      <Navbar
        clockState={clockState}
        wallet={wallet}
        onRefresh={loadData}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col space-y-6">
        {/* Navigation Tabs Bar */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3 overflow-x-auto no-scrollbar gap-2">
          <div className="flex items-center gap-1 sm:gap-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl text-xs font-semibold tracking-wide transition-all duration-150 shrink-0 ${
                    isActive
                      ? "bg-blue-600 text-white shadow-lg shadow-blue-600/30"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                  {tab.badge && (
                    <span className="w-4 h-4 rounded-full bg-amber-500 text-slate-950 text-[10px] font-bold flex items-center justify-center animate-bounce">
                      {tab.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <button
            onClick={loadData}
            disabled={refreshing}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white border border-slate-800 transition-colors shrink-0"
            title="Refresh All State"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          </button>
        </div>

        {/* Tab Content Display */}
        <div className="flex-1">
          {activeTab === "chat" && <ChatTab onRefresh={loadData} />}
          {activeTab === "overview" && (
            <OverviewTab
              wallet={wallet}
              approvals={approvals}
              orders={orders}
              onRefresh={loadData}
            />
          )}
          {activeTab === "inventory" && <InventoryTab items={items} onRefresh={loadData} />}
          {activeTab === "orders" && <OrdersTab orders={orders} />}
          {activeTab === "mandate" && <MandateTab onRefresh={loadData} />}
          {activeTab === "audit" && <AuditTab />}
          {activeTab === "demo" && <DemoStudioTab onRefresh={loadData} />}
        </div>
      </main>
    </div>
  );
}
