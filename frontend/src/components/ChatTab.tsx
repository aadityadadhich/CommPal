"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Mic,
  MicOff,
  CheckCircle2,
  AlertTriangle,
  ShoppingCart,
  ArrowUpRight,
  Package,
  Wallet,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import {
  ChatMessage,
  CardPayload,
  WalletSummary,
  Item,
  PendingApproval,
} from "@/lib/types";
import { sendChatMessage, actOnApproval } from "@/lib/api";
import { TabType } from "@/app/page";

interface ChatTabProps {
  wallet?: WalletSummary;
  items: Item[];
  approvals: PendingApproval[];
  onRefresh: () => Promise<void> | void;
  onNotify: (message: string, tone?: "success" | "warning" | "error" | "info") => void;
  onNavigate: (tab: TabType) => void;
}

export default function ChatTab({
  wallet,
  items,
  approvals,
  onRefresh,
  onNotify,
  onNavigate,
}: ChatTabProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "CommPal Autonomous Procurement Agent ready.\n\nAll purchase proposals are evaluated deterministically against your Spending Mandate and settled via your sandboxed PayPal e-wallet. Select a scenario below or enter a natural language command.",
      timestamp: "2026-11-10T00:00:00.000Z",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [resolvedIntents, setResolvedIntents] = useState<
    Record<string, { status: "APPROVED" | "REJECTED"; detail?: string }>
  >({});
  const [actingIntentId, setActingIntentId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const toggleVoice = () => {
    if (
      typeof window === "undefined" ||
      !("webkitSpeechRecognition" in window || "SpeechRecognition" in window)
    ) {
      onNotify("Web Speech API requires Google Chrome or Microsoft Edge.", "warning");
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
      handleSend(transcript);
    };

    recognition.start();
  };

  const handleSend = async (textToSend?: string) => {
    const text = (textToSend ?? input).trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: "u-" + Date.now(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput("");
    setLoading(true);

    try {
      const response = await sendChatMessage(text);
      setMessages((prev) => [...prev, response]);
      await onRefresh();
    } catch (e: any) {
      onNotify(e.message || "Failed to reach CommPal backend", "error");
      setMessages((prev) => [
        ...prev,
        {
          id: "err-" + Date.now(),
          role: "assistant",
          content: `Request failed: ${e.message || "Backend service unreachable."}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAction = async (
    intentId: string,
    action: "approve" | "reject"
  ) => {
    if (!intentId) return;
    setActingIntentId(intentId);
    try {
      const res = await actOnApproval(intentId, action);
      if (action === "approve" && res.status === "ORDER_PLACED") {
        const summary = `Settled $${res.amount.toFixed(2)} with ${res.merchant} (PayPal Capture: ${res.paypal_capture_id})`;
        setResolvedIntents((prev) => ({
          ...prev,
          [intentId]: { status: "APPROVED", detail: summary },
        }));
        onNotify(summary, "success");
        setMessages((prev) => [
          ...prev,
          {
            id: "act-" + Date.now(),
            role: "assistant",
            content: `Approved. Authorized (\`${res.paypal_auth_id}\`) and captured (\`${res.paypal_capture_id}\`) **$${res.amount.toFixed(2)}** via PayPal Sandbox. Order dispatched with **${res.merchant}** (ETA: ${res.eta_minutes}m).`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } else if (action === "reject" || res.status === "REJECTED") {
        setResolvedIntents((prev) => ({
          ...prev,
          [intentId]: { status: "REJECTED", detail: "Rejected by user — no funds deducted." },
        }));
        onNotify("Order proposal rejected.", "info");
        setMessages((prev) => [
          ...prev,
          {
            id: "act-" + Date.now(),
            role: "assistant",
            content: `Order proposal \`${intentId}\` was rejected. Your wallet balance remains unchanged.`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } else {
        onNotify(res.message || `Order status: ${res.status}`, "warning");
      }
      await onRefresh();
    } catch (e: any) {
      onNotify(e.message || "Failed to process approval action", "error");
    } finally {
      setActingIntentId(null);
    }
  };

  const formatText = (content: string) => {
    // Simple bold & code formatter for clean display
    const parts = content.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={i} className="font-semibold text-white">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code
            key={i}
            className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-700/80 font-mono text-[11px] text-zinc-200"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  const renderCard = (card: CardPayload, idx: number) => {
    switch (card.card_type) {
      case "rule_created":
        return (
          <div
            key={idx}
            className="mt-2.5 p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {card.title}
              </span>
              <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 font-mono text-[10px] text-zinc-400 uppercase">
                {card.data?.rule_type}
              </span>
            </div>
            <p className="text-zinc-400 text-[11px]">{card.subtitle}</p>
          </div>
        );

      case "order_status":
        return (
          <div
            key={idx}
            className="mt-2.5 p-3.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs space-y-2.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 font-semibold text-zinc-100">
                <ShoppingCart className="w-3.5 h-3.5 text-[#0070ba]" />
                <span>{card.title}</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 font-mono text-[10px]">
                SETTLED • IN TRANSIT
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-2.5 rounded bg-zinc-900/90 border border-zinc-800/80 font-mono text-[11px] tabular-nums">
              <div>
                <div className="text-[10px] text-zinc-500 uppercase">Merchant</div>
                <div className="text-zinc-100 font-semibold">{card.data?.merchant}</div>
              </div>
              <div>
                <div className="text-[10px] text-zinc-500 uppercase">Landed Total</div>
                <div className="text-emerald-400 font-semibold">
                  ${card.data?.amount?.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-zinc-500 uppercase">PayPal Auth</div>
                <div className="text-zinc-300 truncate">{card.data?.paypal_auth_id}</div>
              </div>
              <div>
                <div className="text-[10px] text-zinc-500 uppercase">PayPal Capture</div>
                <div className="text-zinc-300 truncate">{card.data?.paypal_capture_id}</div>
              </div>
            </div>
            {card.data?.explanation && (
              <div className="text-[11px] text-zinc-400 leading-relaxed">
                <span className="text-zinc-300 font-medium">Routing rationale: </span>
                {card.data.explanation}
              </div>
            )}
          </div>
        );

      case "approval_needed": {
        const intentId = card.data?.intent_id;
        const resolved = intentId ? resolvedIntents[intentId] : undefined;
        const isStillPending = approvals.some((a) => a.intent_id === intentId);
        const price = card.data?.decision?.chosen_offer?.landed_price;
        const merchant = card.data?.decision?.chosen_offer?.merchant_name;

        return (
          <div
            key={idx}
            className="mt-2.5 p-3.5 rounded-lg bg-zinc-950 border border-amber-700/60 text-xs space-y-2.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-amber-400 font-semibold">
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>{card.title}</span>
              </div>
              <span className="font-mono text-[10px] text-zinc-400">
                {intentId}
              </span>
            </div>
            <p className="text-zinc-300 text-[11px] leading-relaxed">{card.subtitle}</p>
            {merchant && price !== undefined && (
              <div className="flex items-center justify-between p-2 rounded bg-zinc-900 border border-zinc-800 font-mono text-[11px]">
                <span className="text-zinc-400">
                  Selected Offer: <strong className="text-zinc-200">{merchant}</strong>
                </span>
                <span className="text-zinc-100 font-semibold">${price.toFixed(2)}</span>
              </div>
            )}

            {resolved ? (
              <div
                className={`p-2 rounded border font-mono text-[11px] flex items-center gap-1.5 ${
                  resolved.status === "APPROVED"
                    ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-300"
                    : "bg-zinc-900 border-zinc-800 text-zinc-400"
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                <span>
                  {resolved.status}: {resolved.detail}
                </span>
              </div>
            ) : !isStillPending && intentId ? (
              <div className="p-2 rounded bg-zinc-900 border border-zinc-800 font-mono text-[11px] text-zinc-400">
                Resolved in Treasury / Approvals queue.
              </div>
            ) : (
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  disabled={actingIntentId === intentId}
                  onClick={() => handleApproveAction(intentId, "approve")}
                  className="px-3.5 py-1.5 rounded-md bg-[#0070ba] hover:bg-[#005ea6] disabled:opacity-50 text-white font-medium text-xs transition-colors cursor-pointer"
                >
                  {actingIntentId === intentId
                    ? "Authorizing PayPal..."
                    : `Approve & Settle${price ? ` ($${price.toFixed(2)})` : ""}`}
                </button>
                <button
                  type="button"
                  disabled={actingIntentId === intentId}
                  onClick={() => handleApproveAction(intentId, "reject")}
                  className="px-3.5 py-1.5 rounded-md bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-medium text-xs border border-zinc-700 transition-colors cursor-pointer"
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        );
      }

      case "order_preview":
        return (
          <div
            key={idx}
            className="mt-2.5 p-3.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="font-semibold text-zinc-200">{card.title}</span>
              <span className="text-[11px] text-zinc-500 font-mono">{card.subtitle}</span>
            </div>
            <div className="divide-y divide-zinc-800/80 border border-zinc-800 rounded-md overflow-hidden">
              {card.data?.offers?.map((off: any, oIdx: number) => (
                <div
                  key={oIdx}
                  className="flex items-center justify-between px-3 py-2 bg-zinc-900/60 text-[11px] tabular-nums"
                >
                  <div>
                    <span className="font-medium text-zinc-100">{off.merchant_name}</span>
                    <span className="text-zinc-500 ml-2">{off.title}</span>
                  </div>
                  <div className="flex items-center gap-3 font-mono">
                    <span className="text-zinc-400">
                      ETA:{" "}
                      {off.eta_minutes < 60
                        ? `${off.eta_minutes}m`
                        : `${Math.round(off.eta_minutes / 60)}h`}
                    </span>
                    <span className="text-emerald-400 font-semibold">
                      ${off.landed_price?.toFixed(2)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case "decision_explanation":
        return (
          <div
            key={idx}
            className="mt-2.5 p-3 rounded-lg bg-zinc-950 border border-zinc-800 text-xs space-y-1"
          >
            <div className="font-semibold text-zinc-200">{card.title}</div>
            <div className="text-zinc-400 text-[11px] leading-relaxed">
              {card.data?.explanation}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const quickCommands = [
    {
      label: "1. Configure 3 Rules",
      prompt: "I need milk daily, protein powder monthly, and reorder A4 paper when it runs out",
    },
    {
      label: "2. Urgent Paper Depletion",
      prompt: "We're out of A4 paper",
    },
    {
      label: "3. Untracked WD-40 (Needs Approval)",
      prompt: "Order WD-40",
    },
    {
      label: "4. Compare Milk Quotes",
      prompt: "Compare prices for whole milk",
    },
    {
      label: "5. Order Coffee",
      prompt: "Order coffee now",
    },
    {
      label: "6. Check Wallet & Caps",
      prompt: "What is my wallet balance?",
    },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
      {/* Left 8 cols: Conversational Procurement Terminal */}
      <div className="lg:col-span-8 flex flex-col h-[calc(100vh-155px)] min-h-[560px] bg-zinc-900/60 rounded-lg border border-zinc-800 overflow-hidden">
        {/* Terminal Header */}
        <div className="px-4 py-2.5 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-[#0070ba]" />
            <span className="font-medium text-zinc-200">
              Procurement Agent Console
            </span>
          </div>
          <span className="text-[11px] font-mono text-zinc-500">
            Policy: Deterministic Mandate v{wallet ? "Active" : "1"}
          </span>
        </div>

        {/* Message Stream */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
              >
                <div className="flex items-center gap-2 mb-1 px-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                    {isUser ? "You (Authorized User)" : "CommPal Agent"}
                  </span>
                </div>
                <div
                  className={`max-w-[92%] sm:max-w-[82%] rounded-lg px-4 py-3 text-xs sm:text-sm leading-relaxed ${
                    isUser
                      ? "bg-[#0070ba] text-white"
                      : "bg-zinc-900 text-zinc-200 border border-zinc-800"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{formatText(msg.content)}</div>
                  {msg.cards && msg.cards.map((card, cIdx) => renderCard(card, cIdx))}
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono px-2">
              <span className="w-2 h-2 rounded-full bg-[#0070ba] animate-ping" />
              <span>Querying 5 merchant catalogs & evaluating spending mandate...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Scenario Strip */}
        <div className="px-3 py-2 bg-zinc-950/80 border-t border-zinc-800/80 flex items-center gap-1.5 overflow-x-auto">
          {quickCommands.map((cmd, idx) => (
            <button
              key={idx}
              type="button"
              disabled={loading}
              onClick={() => handleSend(cmd.prompt)}
              className="px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-800 text-[11px] font-medium shrink-0 transition-colors cursor-pointer"
            >
              {cmd.label}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-3 bg-zinc-900 border-t border-zinc-800 flex items-center gap-2">
          <button
            type="button"
            onClick={toggleVoice}
            className={`p-2 rounded-md border transition-colors cursor-pointer ${
              isListening
                ? "bg-rose-600 text-white border-rose-500"
                : "bg-zinc-950 hover:bg-zinc-800 text-zinc-400 border-zinc-800"
            }`}
            title={isListening ? "Stop voice input" : "Voice command (Chrome/Edge)"}
          >
            {isListening ? <Mic className="w-4 h-4" /> : <MicOff className="w-4 h-4" />}
          </button>

          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Type a command (e.g., 'We're out of A4 paper', 'Order coffee', 'Compare milk prices')..."
            className="flex-1 bg-zinc-950 border border-zinc-800 rounded-md px-3.5 py-2 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-[#0070ba]"
          />

          <button
            type="button"
            disabled={!input.trim() || loading}
            onClick={() => handleSend()}
            className="px-3.5 py-2 rounded-md bg-[#0070ba] hover:bg-[#005ea6] disabled:opacity-40 text-white text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <span>Execute</span>
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Right 4 cols: Live Operational Telemetry Sidebar */}
      <div className="lg:col-span-4 space-y-4">
        {/* Pending Approvals Box */}
        {approvals.length > 0 && (
          <div className="p-4 rounded-lg bg-amber-950/20 border border-amber-700/60 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                Action Required ({approvals.length})
              </span>
              <button
                type="button"
                onClick={() => onNavigate("overview")}
                className="text-[11px] text-amber-400 hover:underline cursor-pointer"
              >
                View All
              </button>
            </div>
            <div className="space-y-2">
              {approvals.map((app) => (
                <div
                  key={app.approval_id}
                  className="p-3 rounded bg-zinc-900 border border-zinc-800 text-xs space-y-2"
                >
                  <div className="flex justify-between font-medium text-zinc-100">
                    <span>{app.item_name}</span>
                    <span className="font-mono text-zinc-400">Qty: {app.qty}</span>
                  </div>
                  <p className="text-[11px] text-zinc-400 line-clamp-2">{app.explanation}</p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={actingIntentId === app.intent_id}
                      onClick={() => handleApproveAction(app.intent_id, "approve")}
                      className="flex-1 py-1.5 rounded bg-[#0070ba] hover:bg-[#005ea6] text-white font-medium text-[11px] cursor-pointer"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      disabled={actingIntentId === app.intent_id}
                      onClick={() => handleApproveAction(app.intent_id, "reject")}
                      className="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[11px] cursor-pointer"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sandboxed Wallet Card */}
        <div className="p-4 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
              <Wallet className="w-3.5 h-3.5 text-[#0070ba]" />
              PayPal Sandboxed E-Wallet
            </span>
            <button
              type="button"
              onClick={() => onNavigate("overview")}
              className="text-[11px] text-zinc-400 hover:text-zinc-200 flex items-center gap-0.5 cursor-pointer"
            >
              <span>Treasury</span>
              <ArrowUpRight className="w-3 h-3" />
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2 pt-1 tabular-nums">
            <div className="p-2.5 rounded bg-zinc-950 border border-zinc-800/80">
              <div className="text-[10px] text-zinc-500 uppercase">Available</div>
              <div className="text-sm font-mono font-semibold text-zinc-100 mt-0.5">
                ${wallet?.available_balance?.toFixed(2) ?? "0.00"}
              </div>
            </div>
            <div className="p-2.5 rounded bg-zinc-950 border border-zinc-800/80">
              <div className="text-[10px] text-zinc-500 uppercase">Held</div>
              <div className="text-sm font-mono font-semibold text-amber-400 mt-0.5">
                ${wallet?.held_balance?.toFixed(2) ?? "0.00"}
              </div>
            </div>
            <div className="p-2.5 rounded bg-zinc-950 border border-zinc-800/80">
              <div className="text-[10px] text-zinc-500 uppercase">Spent</div>
              <div className="text-sm font-mono font-semibold text-emerald-400 mt-0.5">
                ${wallet?.spent_balance?.toFixed(2) ?? "0.00"}
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between text-[11px] text-zinc-400 pt-1 border-t border-zinc-800/80 font-mono tabular-nums">
            <span>Daily Cap Used:</span>
            <span className="text-zinc-200">
              ${wallet?.daily_spent?.toFixed(2) ?? "0.00"} / ${wallet?.daily_cap?.toFixed(2) ?? "80.00"}
            </span>
          </div>
        </div>

        {/* Tracked Inventory Snapshot */}
        <div className="p-4 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-400 flex items-center gap-1.5">
              <Package className="w-3.5 h-3.5 text-zinc-400" />
              Tracked Inventory Status
            </span>
            <button
              type="button"
              onClick={() => onNavigate("inventory")}
              className="text-[11px] text-zinc-400 hover:text-zinc-200 flex items-center gap-0.5 cursor-pointer"
            >
              <span>Manage</span>
              <ArrowUpRight className="w-3 h-3" />
            </button>
          </div>

          <div className="divide-y divide-zinc-800/70">
            {items.map((it) => {
              const isDepleted = it.stock_qty <= 0 || it.days_of_cover <= 1.0;
              return (
                <div
                  key={it.id}
                  className="py-2.5 first:pt-0 last:pb-0 flex items-center justify-between gap-2 text-xs"
                >
                  <div className="min-w-0">
                    <div className="font-medium text-zinc-200 truncate">{it.name}</div>
                    <div className="text-[11px] text-zinc-500 font-mono tabular-nums">
                      Stock: {it.stock_qty.toFixed(1)} {it.unit} · {it.days_of_cover}d cover
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => handleSend(`We're out of ${it.name}`)}
                    className={`px-2 py-1 rounded text-[11px] font-medium border shrink-0 transition-colors cursor-pointer ${
                      isDepleted
                        ? "bg-rose-950/60 text-rose-300 border-rose-800/60 hover:bg-rose-900/60"
                        : "bg-zinc-950 text-zinc-300 border-zinc-800 hover:bg-zinc-800"
                    }`}
                    title="Simulate stockout and trigger autonomous restock"
                  >
                    Trigger Restock
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Security Architecture Note */}
        <div className="p-3.5 rounded-lg bg-zinc-900/40 border border-zinc-800/80 flex items-start gap-2.5 text-[11px] text-zinc-400 leading-relaxed">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
          <div>
            <strong className="text-zinc-200">Zero-Trust Execution:</strong> The AI agent can only propose intents. Your deterministic mandate verifies limits, merchants, and anomalies before PayPal authorization.
          </div>
        </div>
      </div>
    </div>
  );
}
