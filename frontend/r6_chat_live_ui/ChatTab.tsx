"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Send, Mic, MicOff, Bot, User, CheckCircle2, Clock, 
  AlertTriangle, ShieldCheck, ShoppingCart, Sparkles, ArrowRight 
} from "lucide-react";
import { ChatMessage, CardPayload } from "@/lib/types";
import { sendChatMessage, actOnApproval } from "@/lib/api";

interface ChatTabProps {
  onRefresh: () => void;
}

export default function ChatTab({ onRefresh }: ChatTabProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I am **CommPal**, your autonomous purchasing assistant. I help restock your home & office supplies while strictly enforcing your spending mandate and paying from your sandboxed PayPal e-wallet.\n\nTry telling me what you need, or click one of the quick scenarios below!",
      timestamp: "2026-10-22T00:00:00.000Z",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const toggleVoice = () => {
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
      alert("Speech recognition is not supported in this browser. Please use Google Chrome.");
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
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    const userMsg: ChatMessage = {
      id: "u-" + Date.now(),
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await sendChatMessage(text);
      setMessages((prev) => [...prev, response]);
      onRefresh();
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: "err-" + Date.now(),
          role: "assistant",
          content: "Sorry, I encountered an error connecting to the backend service.",
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAction = async (intentId: string, action: "approve" | "reject") => {
    try {
      const res = await actOnApproval(intentId, action);
      if (res.status === "ORDER_PLACED") {
        setMessages((prev) => [
          ...prev,
          {
            id: "act-" + Date.now(),
            role: "assistant",
            content: `Order approved! Payment of $${res.amount.toFixed(2)} authorized and captured via PayPal Sandbox. Merchant order placed with ${res.merchant} (ETA: ${res.eta_minutes} mins).`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: "act-" + Date.now(),
            role: "assistant",
            content: `Order was ${action}d.`,
            timestamp: new Date().toISOString(),
          },
        ]);
      }
      onRefresh();
    } catch (e) {
      console.error(e);
    }
  };

  const renderCard = (card: CardPayload, idx: number) => {
    switch (card.card_type) {
      case "rule_created":
        return (
          <div
            key={idx}
            className="mt-3 p-3.5 rounded-xl bg-slate-800/90 border border-slate-700/80 shadow-md text-xs text-slate-200"
          >
            <div className="flex items-center space-x-2 text-emerald-400 font-semibold mb-1">
              <CheckCircle2 className="w-4 h-4" />
              <span>{card.title}</span>
            </div>
            <p className="text-slate-400 text-[11px] mb-2">{card.subtitle}</p>
            <div className="grid grid-cols-2 gap-2 bg-slate-900/60 p-2 rounded-lg font-mono text-[11px]">
              <div>
                Item: <span className="text-white font-medium">{card.data?.item}</span>
              </div>
              <div>
                Schedule: <span className="text-emerald-300 font-medium">{card.data?.rule_type?.toUpperCase()}</span>
              </div>
            </div>
          </div>
        );

      case "order_status":
        return (
          <div
            key={idx}
            className="mt-3 p-3.5 rounded-xl bg-slate-800/90 border border-blue-500/30 shadow-md text-xs text-slate-200"
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center space-x-2 text-blue-400 font-semibold">
                <ShoppingCart className="w-4 h-4" />
                <span>{card.title}</span>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-300 text-[10px] font-mono border border-blue-500/20">
                IN TRANSIT
              </span>
            </div>
            <p className="text-slate-400 text-[11px] mb-2.5">{card.subtitle}</p>
            <div className="space-y-1.5 bg-slate-900/60 p-2.5 rounded-lg text-[11px] font-mono">
              <div className="flex justify-between">
                <span className="text-slate-400">Merchant:</span>
                <span className="text-white font-medium">{card.data?.merchant}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Total Billed:</span>
                <span className="text-emerald-400 font-semibold">${card.data?.amount?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">PayPal Auth ID:</span>
                <span className="text-blue-300 truncate max-w-[180px]">{card.data?.paypal_auth_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">PayPal Capture ID:</span>
                <span className="text-blue-300 truncate max-w-[180px]">{card.data?.paypal_capture_id}</span>
              </div>
            </div>
          </div>
        );

      case "approval_needed":
        return (
          <div
            key={idx}
            className="mt-3 p-3.5 rounded-xl bg-amber-950/30 border border-amber-600/40 shadow-lg text-xs text-slate-200"
          >
            <div className="flex items-center space-x-2 text-amber-400 font-semibold mb-1">
              <AlertTriangle className="w-4 h-4" />
              <span>{card.title}</span>
            </div>
            <p className="text-slate-300 text-[11px] mb-3">{card.subtitle}</p>
            <div className="flex space-x-2">
              <button
                onClick={() => handleApproveAction(card.data?.intent_id, "approve")}
                className="flex-1 py-1.5 px-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs shadow-md shadow-emerald-900/30 transition-colors"
              >
                Approve ($ {card.data?.decision?.chosen_offer?.landed_price?.toFixed(2)})
              </button>
              <button
                onClick={() => handleApproveAction(card.data?.intent_id, "reject")}
                className="py-1.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs border border-slate-700 transition-colors"
              >
                Reject
              </button>
            </div>
          </div>
        );

      case "order_preview":
        return (
          <div
            key={idx}
            className="mt-3 p-3.5 rounded-xl bg-slate-800/90 border border-slate-700 shadow-md text-xs"
          >
            <div className="flex items-center space-x-2 text-blue-400 font-semibold mb-2">
              <Sparkles className="w-4 h-4" />
              <span>{card.title}</span>
            </div>
            <div className="space-y-1.5">
              {card.data?.offers?.map((off: any, oIdx: number) => (
                <div
                  key={oIdx}
                  className="flex items-center justify-between p-2 rounded-lg bg-slate-900/60 border border-slate-800 text-[11px]"
                >
                  <div>
                    <span className="font-semibold text-slate-200">{off.merchant_name}</span>
                    <span className="text-slate-400 ml-2">ETA: {off.eta_minutes < 60 ? `${off.eta_minutes}m` : `${Math.round(off.eta_minutes/60)}h`}</span>
                  </div>
                  <div className="font-mono text-emerald-400 font-semibold">
                    ${off.landed_price?.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const samplePrompts = [
    "I need milk daily, protein powder monthly, and reorder A4 paper when it runs out",
    "We're out of A4 paper",
    "Order WD-40",
    "What is my wallet balance?",
    "Compare prices for whole milk",
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] max-h-[850px] bg-slate-900 rounded-2xl border border-slate-800 overflow-hidden shadow-2xl">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              className={`flex items-start gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-white ${
                  isUser
                    ? "bg-blue-600 shadow-md shadow-blue-600/30"
                    : "bg-gradient-to-tr from-indigo-600 to-purple-600 shadow-md shadow-indigo-600/30"
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div
                className={`max-w-[85%] sm:max-w-[70%] rounded-2xl p-4 shadow-sm text-sm ${
                  isUser
                    ? "bg-blue-600 text-white rounded-tr-none"
                    : "bg-slate-800/90 text-slate-200 border border-slate-700/70 rounded-tl-none"
                }`}
              >
                <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                {msg.cards && msg.cards.map((card, cIdx) => renderCard(card, cIdx))}
              </div>
            </div>
          );
        })}
        {loading && (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-600/80 flex items-center justify-center text-white shrink-0 animate-pulse">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-2xl p-3 text-xs text-slate-400 flex items-center space-x-2">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce"></div>
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0.2s]"></div>
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0.4s]"></div>
              <span>Evaluating mandate & querying merchants...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="px-4 py-2 bg-slate-950/60 border-t border-slate-800/60 flex items-center gap-2 overflow-x-auto text-xs no-scrollbar">
        <span className="text-slate-500 text-[11px] font-semibold uppercase tracking-wider shrink-0 flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-amber-400" />
          Try:
        </span>
        {samplePrompts.map((prompt, pIdx) => (
          <button
            key={pIdx}
            onClick={() => handleSend(prompt)}
            className="px-2.5 py-1 rounded-full bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/60 text-xs shrink-0 transition-colors"
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="p-3 bg-slate-950 border-t border-slate-800 flex items-center gap-2">
        <button
          onClick={toggleVoice}
          className={`p-2.5 rounded-xl border transition-colors ${
            isListening
              ? "bg-rose-600 text-white border-rose-500 animate-pulse"
              : "bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700"
          }`}
          title={isListening ? "Listening... Click to stop" : "Push-to-Talk (Chrome Web Speech)"}
        >
          {isListening ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5 text-slate-400" />}
        </button>

        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask CommPal: 'I need milk daily', 'We ran out of A4 paper'..."
          className="flex-1 bg-slate-900 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
        />

        <button
          disabled={!input.trim() || loading}
          onClick={() => handleSend()}
          className="p-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white shadow-lg shadow-blue-600/30 transition-colors"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
