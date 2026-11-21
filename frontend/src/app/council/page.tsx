"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Send, Wifi, WifiOff, Loader2 } from "lucide-react";
import { WS_URL, api } from "@/lib/api";
import { format } from "date-fns";
import clsx from "clsx";

// Agent personas
const AGENTS = {
  freya:   { name: "Freya",   color: "#7c5cfc", emoji: "⚔️",  desc: "Direct & honest" },
  albedo:  { name: "Albedo",  color: "#f472b6", emoji: "🎉",  desc: "Celebrates wins" },
  anya:    { name: "Anya",    color: "#34d399", emoji: "🌸",  desc: "Warm & rest-aware" },
  zerotwo: { name: "Zero Two",color: "#818cf8", emoji: "🎯",  desc: "Analytical" },
  mohini:  { name: "Mohini", color: "#fbbf24", emoji: "🌿",  desc: "Calm & energy" },
  council: { name: "Council", color: "#e8e8f0", emoji: "🏛️",  desc: "All together" },
} as const;

type AgentKey = keyof typeof AGENTS;

interface ChatMessage {
  id: string;
  type: "user" | "agent" | "status" | "error";
  content: string;
  agentId?: string;
  displayName?: string;
  timestamp: Date;
  input_tokens?: number;
  output_tokens?: number;
  tokens_used?: number;
  model_used?: string;
  latency_ms?: number;
  debug?: {
    prompt_size: number;
    memory_count: number;
    retrieved_memories: string[];
    execution_time_ms: number;
  } | null;
}

function AgentBubble({ msg, devMode }: { msg: ChatMessage; devMode: boolean }) {
  const agent = AGENTS[msg.agentId as AgentKey] ?? AGENTS.freya;
  const [showDebug, setShowDebug] = useState(false);

  return (
    <div className="fade-in" style={{ display: "flex", gap: "10px", alignItems: "flex-start", marginBottom: "8px" }}>
      {/* Avatar */}
      <div style={{
        width: "36px", height: "36px", borderRadius: "10px", flexShrink: 0,
        background: `${agent.color}22`, border: `1px solid ${agent.color}44`,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "16px",
      }}>{agent.emoji}</div>
      
      {/* Bubble */}
      <div style={{ maxWidth: "78%", flex: 1 }}>
        <div style={{ fontSize: "11px", color: agent.color, marginBottom: "4px", fontWeight: 600 }}>
          {msg.displayName ?? agent.name}
        </div>
        <div style={{
          background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: "4px 14px 14px 14px", padding: "10px 14px",
          fontSize: "13px", lineHeight: 1.6, color: "var(--text)",
          whiteSpace: "pre-wrap",
        }}>{msg.content}</div>

        {/* Token usage per reply (always shown); breakdown + debug only in developer mode */}
        {msg.tokens_used !== undefined && msg.tokens_used > 0 && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "6px", flexWrap: "wrap" }}>
            <span style={{ fontSize: "10px", color: "var(--text-muted)", background: "rgba(255,255,255,0.03)", padding: "2px 6px", borderRadius: "4px", border: "1px solid rgba(255,255,255,0.02)" }}>
              <strong style={{ color: "var(--text)" }}>{msg.tokens_used}</strong> tokens
              {devMode && <> · Input: {msg.input_tokens} · Output: {msg.output_tokens} · {msg.latency_ms}ms · {msg.model_used?.split("/").pop()}</>}
            </span>
            {devMode && <button 
              onClick={() => setShowDebug(!showDebug)}
              style={{
                background: "transparent", border: "none", color: "var(--accent-2)", cursor: "pointer",
                fontSize: "10px", padding: 0, fontWeight: 600, outline: "none", textDecoration: "underline",
              }}
            >
              {showDebug ? "Hide Debug" : "Inspect Debug Panel"}
            </button>}
          </div>
        )}

        {/* Developer Debug Panel */}
        {devMode && showDebug && msg.debug && (
          <div className="glass fade-in" style={{
            marginTop: "8px", padding: "12px", fontSize: "11px", fontFamily: "monospace",
            background: "rgba(10, 10, 15, 0.95)", border: "1px solid rgba(124, 92, 252, 0.2)",
            borderRadius: "8px", display: "flex", flexDirection: "column", gap: "6px",
            color: "var(--text)", overflowX: "auto", boxShadow: "0 4px 20px rgba(0,0,0,0.4)"
          }}>
            <div style={{ fontWeight: 700, color: "var(--accent)", letterSpacing: "0.05em", borderBottom: "1px solid rgba(124, 92, 252, 0.2)", paddingBottom: "4px", marginBottom: "2px" }}>
              DEVELOPER DEBUG PANEL
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px" }}>
              <div>• Prompt Size: <span style={{ color: "var(--accent-2)" }}>{msg.debug.prompt_size.toLocaleString()} chars</span></div>
              <div>• Memory Size: <span style={{ color: "var(--accent-2)" }}>{msg.debug.memory_count} entries</span></div>
              <div>• Input Tokens: <span style={{ color: "var(--accent-2)" }}>{msg.input_tokens}</span></div>
              <div>• Output Tokens: <span style={{ color: "var(--accent-2)" }}>{msg.output_tokens}</span></div>
              <div style={{ gridColumn: "span 2" }}>• Model Path: <span style={{ color: "var(--accent-2)" }}>{msg.model_used}</span></div>
              <div style={{ gridColumn: "span 2" }}>• Execution Time: <span style={{ color: "var(--accent-2)" }}>{msg.debug.execution_time_ms} ms</span></div>
            </div>
            
            {msg.debug.retrieved_memories && msg.debug.retrieved_memories.length > 0 ? (
              <div style={{ marginTop: "6px", borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "6px" }}>
                <div style={{ fontWeight: 600, marginBottom: "4px", color: "var(--text-muted)" }}>Retrieved Memories ({msg.debug.retrieved_memories.length}):</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "120px", overflowY: "auto", paddingRight: "4px" }}>
                  {msg.debug.retrieved_memories.map((m, i) => (
                    <div key={i} style={{ padding: "4px 8px", background: "rgba(255,255,255,0.02)", borderLeft: "2px solid var(--accent)", color: "var(--text-muted)", fontSize: "10.5px" }}>
                      "{m}"
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ color: "var(--text-muted)", marginTop: "4px", borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "6px" }}>
                No episodic memories retrieved in context.
              </div>
            )}
          </div>
        )}

        <div style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "4px" }}>
          {format(msg.timestamp, "HH:mm")}
        </div>
      </div>
    </div>
  );
}

function UserBubble({ msg }: { msg: ChatMessage }) {
  return (
    <div className="fade-in" style={{ display: "flex", justifyContent: "flex-end", marginBottom: "8px" }}>
      <div style={{
        maxWidth: "70%", background: "rgba(124,92,252,0.15)",
        border: "1px solid rgba(124,92,252,0.3)", borderRadius: "14px 4px 14px 14px",
        padding: "10px 14px", fontSize: "13px", lineHeight: 1.6, color: "var(--text)",
      }}>{msg.content}</div>
    </div>
  );
}

export default function CouncilPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([{
    id: "welcome",
    type: "status",
    content: "Connecting to The Council...",
    timestamp: new Date(),
  }]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentKey>("freya");
  const [tokensToday, setTokensToday] = useState(0);
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);
  const [devMode, setDevMode] = useState(false); // developer details hidden by default
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const addMsg = useCallback((msg: Omit<ChatMessage, "id">) => {
    setMessages(prev => [...prev, { ...msg, id: `${Date.now()}-${Math.random()}` }]);
  }, []);

  const fetchTokensToday = useCallback(async () => {
    try {
      const res = await api.agents.tokensToday();
      setTokensToday(res.total_tokens_today);
    } catch (e) {
      console.error("Failed to fetch today's token usage", e);
    }
  }, []);

  // Is live AI set up on the server? (Socket "connected" alone doesn't mean agents can reply.)
  useEffect(() => {
    api.agents.status()
      .then(s => setAiConfigured(s.ai_configured))
      .catch(() => setAiConfigured(null));
  }, [connected]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // WebSocket connection
  useEffect(() => {
    fetchTokensToday();
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setMessages([{
        id: "connected",
        type: "status",
        content: "Connected to The Council. Say something...",
        timestamp: new Date(),
      }]);
    };

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setLoading(false);

      if (data.type === "agent_message") {
        addMsg({
          type: "agent",
          content: data.content,
          agentId: data.agent_id,
          displayName: data.display_name,
          timestamp: new Date(data.timestamp || Date.now()),
          input_tokens: data.input_tokens || 0,
          output_tokens: data.output_tokens || 0,
          tokens_used: data.tokens_used || 0,
          model_used: data.model_used || "",
          latency_ms: data.latency_ms || 0,
          debug: data.debug || null,
        });
        fetchTokensToday();
      } else if (data.type === "error") {
        addMsg({ type: "error", content: data.message, timestamp: new Date() });
      }
    };

    ws.onclose = () => {
      setConnected(false);
      addMsg({ type: "status", content: "Disconnected. Refresh to reconnect.", timestamp: new Date() });
    };

    ws.onerror = () => {
      setConnected(false);
      addMsg({ type: "status", content: "Can't reach the Feynlist server. If it was idle it may be waking up (up to a minute); refresh to reconnect.", timestamp: new Date() });
    };

    return () => ws.close();
  }, [addMsg, fetchTokensToday]);

  const send = useCallback(() => {
    const text = input.trim();
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    addMsg({ type: "user", content: text, timestamp: new Date() });
    setInput("");
    setLoading(true);

    const agentId = selectedAgent === "council" ? null : selectedAgent;
    wsRef.current.send(JSON.stringify({ message: text, agent_id: agentId }));
  }, [input, selectedAgent, addMsg]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  // Compute session metrics dynamically
  const sessionTotalTokens = messages.reduce((acc, m) => acc + (m.tokens_used || 0), 0);
  
  const agentStats = (Object.keys(AGENTS) as AgentKey[]).reduce((acc, key) => {
    if (key === "council") return acc;
    const agentMsgs = messages.filter(m => m.type === "agent" && m.agentId === key);
    const calls = agentMsgs.length;
    const totalTokens = agentMsgs.reduce((sum, m) => sum + (m.tokens_used || 0), 0);
    const avgTokens = calls > 0 ? Math.round(totalTokens / calls) : 0;
    acc[key] = { calls, totalTokens, avgTokens };
    return acc;
  }, {} as Record<string, { calls: number; totalTokens: number; avgTokens: number }>);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", padding: "24px", gap: "16px", maxWidth: "1500px", margin: "0 auto", width: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em" }}>The</div>
          <h1 style={{ fontSize: "28px", fontWeight: 700 }} className="gradient-text">Council</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "14px", flexWrap: "wrap", justifyContent: "flex-end" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", color: "var(--text-muted)", cursor: "pointer" }}>
            <input type="checkbox" checked={devMode} onChange={e => setDevMode(e.target.checked)} />
            Developer details
          </label>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px",
            color: !connected ? "#6b6b80" : aiConfigured === false ? "#fbbf24" : "#34d399" }}>
            {connected ? <Wifi size={14} /> : <WifiOff size={14} />}
            {!connected ? "Offline" : aiConfigured === false ? "Connected · AI replies unavailable" : "Connected"}
          </div>
        </div>
      </div>

      {/* Agent selector */}
      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
        {(Object.keys(AGENTS) as AgentKey[]).map(key => {
          const a = AGENTS[key];
          const active = selectedAgent === key;
          return (
            <button
              key={key}
              onClick={() => setSelectedAgent(key)}
              style={{
                padding: "6px 14px", borderRadius: "20px", cursor: "pointer",
                background: active ? `${a.color}22` : "rgba(255,255,255,0.04)",
                color: active ? a.color : "var(--text-muted)",
                border: active ? `1px solid ${a.color}55` : "1px solid transparent",
                fontSize: "12px", fontWeight: active ? 600 : 400,
                transition: "all 0.15s",
              }}
            >
              {a.emoji} {a.name}
            </button>
          );
        })}
      </div>

      {/* Split layout: Chat Area + Audit Dashboard */}
      <div style={{ display: "flex", flex: 1, gap: "16px", overflow: "hidden", minHeight: 0 }}>
        {/* Main Chat Area */}
        <div className="glass" style={{ flex: 3, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div style={{ flex: 1, overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
            {messages.map(msg => {
              if (msg.type === "user") return <UserBubble key={msg.id} msg={msg} />;
              if (msg.type === "agent") return <AgentBubble key={msg.id} msg={msg} devMode={devMode} />;
              return (
                <div key={msg.id} style={{ textAlign: "center", fontSize: "11px", color: "var(--text-muted)", padding: "4px" }}>
                  {msg.content}
                </div>
              );
            })}
            {loading && (
              <div style={{ display: "flex", gap: "8px", alignItems: "center", color: "var(--text-muted)", fontSize: "12px" }}>
                <Loader2 size={14} className="animate-spin" style={{ animation: "spin 1s linear infinite" }} />
                The Council is thinking...
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div style={{
            padding: "12px 16px", borderTop: "1px solid var(--border)",
            display: "flex", gap: "10px", alignItems: "flex-end",
            background: "rgba(10, 10, 15, 0.2)",
          }}>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={`Message ${AGENTS[selectedAgent].name}... (Enter to send)`}
              rows={1}
              style={{
                flex: 1, background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)",
                borderRadius: "10px", padding: "10px 14px", color: "var(--text)",
                fontSize: "13px", resize: "none", outline: "none", fontFamily: "inherit",
                lineHeight: 1.5,
              }}
            />
            <button
              onClick={send}
              disabled={!connected || !input.trim()}
              style={{
                width: "40px", height: "40px", borderRadius: "10px", border: "none",
                background: connected && input.trim() ? "var(--accent)" : "rgba(255,255,255,0.06)",
                color: "white", cursor: connected && input.trim() ? "pointer" : "not-allowed",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.15s", flexShrink: 0,
              }}
            >
              <Send size={16} />
            </button>
          </div>
        </div>

        {/* Token Auditing Dashboard (Right Column) */}
        <div className="glass" style={{
          flex: 1, padding: "16px", display: "flex", flexDirection: "column", gap: "20px",
          background: "rgba(17,17,24,0.7)", border: "1px solid var(--border)",
          overflowY: "auto", minWidth: "280px"
        }}>
          <div>
            <h2 style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "10px" }}>
              Session Usage Auditing
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <div className="glass" style={{ padding: "10px 12px", background: "rgba(255,255,255,0.015)" }}>
                <div style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Session Consumption</div>
                <div style={{ fontSize: "20px", fontWeight: 700, color: "var(--accent)", marginTop: "2px" }}>{sessionTotalTokens.toLocaleString()} <span style={{ fontSize: "11px", fontWeight: 400, color: "var(--text-muted)" }}>t</span></div>
              </div>
              <div className="glass" style={{ padding: "10px 12px", background: "rgba(255,255,255,0.015)" }}>
                <div style={{ fontSize: "9px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Today's Accumulated Total</div>
                <div style={{ fontSize: "20px", fontWeight: 700, color: "var(--accent-2)", marginTop: "2px" }}>{tokensToday.toLocaleString()} <span style={{ fontSize: "11px", fontWeight: 400, color: "var(--text-muted)" }}>t</span></div>
              </div>
            </div>
          </div>

          <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
            <h2 style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "10px" }}>
              Agent Consumption Logs
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", overflowY: "auto", flex: 1, paddingRight: "4px" }}>
              {(Object.keys(AGENTS) as AgentKey[]).map(key => {
                if (key === "council") return null;
                const a = AGENTS[key];
                const stats = agentStats[key] || { calls: 0, totalTokens: 0, avgTokens: 0 };
                return (
                  <div key={key} style={{
                    display: "flex", flexDirection: "column", padding: "10px",
                    background: "rgba(255,255,255,0.01)", borderRadius: "8px",
                    border: "1px solid rgba(255,255,255,0.03)", gap: "4px"
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "12px", fontWeight: 600, color: a.color }}>
                        {a.emoji} {a.name}
                      </span>
                      <span style={{ fontSize: "9px", background: `${a.color}22`, color: a.color, padding: "1px 6px", borderRadius: "10px", fontWeight: 600 }}>
                        {stats.calls} call{stats.calls !== 1 ? "s" : ""}
                      </span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "var(--text-muted)", marginTop: "2px" }}>
                      <span>Total Consumed:</span>
                      <span style={{ color: "var(--text)", fontWeight: 500 }}>{stats.totalTokens.toLocaleString()} t</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", color: "var(--text-muted)" }}>
                      <span>Avg/Interaction:</span>
                      <span style={{ color: "var(--text)", fontWeight: 500 }}>{stats.avgTokens.toLocaleString()} t</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
