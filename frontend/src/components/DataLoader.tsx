"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { CloudOff, Loader2, RefreshCw } from "lucide-react";
import { API_BASE, ApiError } from "@/lib/api";

const POLL_MS = 5000;
const MAX_TRIES = 18; // ~90 s: a sleeping free host can take up to a minute to wake

type State<T> =
  | { kind: "loading" }
  | { kind: "waking"; tries: number }
  | { kind: "down" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: T };

/**
 * Loads a page's data in the browser (so the session id and time zone go with it).
 * If the server doesn't answer, shows "Waking the server…" and polls /health,
 * then loads again; never shows an empty account while the server is asleep.
 */
export default function DataLoader<T>({
  load,
  children,
}: {
  load: () => Promise<T>;
  children: (data: T, reload: () => Promise<void>) => ReactNode;
}) {
  const [state, setState] = useState<State<T>>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0); // bump to retry from scratch

  useEffect(() => {
    let cancelled = false;
    (async () => {
      for (let tries = 0; tries <= MAX_TRIES; tries++) {
        try {
          const data = await load();
          if (!cancelled) setState({ kind: "ready", data });
          return;
        } catch (e) {
          if (cancelled) return;
          if (e instanceof ApiError) {
            setState({ kind: "error", message: e.message });
            return;
          }
          // Network error: the server is asleep or down. Wait, then try again.
          setState({ kind: "waking", tries });
          await new Promise(r => setTimeout(r, POLL_MS));
          if (cancelled) return;
          try { await fetch(`${API_BASE}/health`, { cache: "no-store" }); } catch { /* still asleep */ }
        }
      }
      if (!cancelled) setState({ kind: "down" });
    })();
    return () => { cancelled = true; };
  }, [load, attempt]);

  const reload = useCallback(async () => {
    try {
      const data = await load();
      setState({ kind: "ready", data });
    } catch (e) {
      setState(e instanceof ApiError ? { kind: "error", message: e.message } : { kind: "down" });
    }
  }, [load]);

  if (state.kind === "ready") return <>{children(state.data, reload)}</>;

  const box = (icon: ReactNode, title: string, body: string, retry: boolean) => (
    <div className="page">
      <div role="alert" className="glass" style={{
        padding: "18px 20px", display: "flex", gap: "12px", alignItems: "flex-start",
        border: "1px solid rgba(251, 191, 36, 0.35)", background: "rgba(251, 191, 36, 0.06)",
      }}>
        {icon}
        <div style={{ flex: 1, fontSize: "13px", lineHeight: 1.6 }}>
          <strong>{title}</strong>
          <div style={{ color: "var(--text-muted)" }}>{body}</div>
        </div>
        {retry && (
          <button onClick={() => { setState({ kind: "loading" }); setAttempt(a => a + 1); }} style={{
            display: "flex", alignItems: "center", gap: "6px", background: "transparent",
            border: "1px solid rgba(251, 191, 36, 0.4)", color: "#fbbf24", borderRadius: "8px",
            padding: "6px 10px", fontSize: "12px", cursor: "pointer", flexShrink: 0,
          }}>
            <RefreshCw size={13} /> Retry
          </button>
        )}
      </div>
    </div>
  );

  if (state.kind === "loading") {
    return (
      <div className="page" style={{ color: "var(--text-muted)", fontSize: "13px", display: "flex", gap: "8px", alignItems: "center" }}>
        <Loader2 size={16} className="spin" /> Loading…
      </div>
    );
  }
  if (state.kind === "waking") {
    return box(<Loader2 size={18} className="spin" style={{ color: "#fbbf24", flexShrink: 0 }} />,
      "Waking the server, this can take up to a minute…",
      "The free host sleeps when nobody is using it. This page will load by itself as soon as it answers.",
      false);
  }
  if (state.kind === "down") {
    return box(<CloudOff size={18} style={{ color: "#fbbf24", flexShrink: 0 }} />,
      "Can't reach the Feynlist server.",
      "It's still not answering after about a minute and a half. Please try again in a few minutes.",
      true);
  }
  return box(<CloudOff size={18} style={{ color: "#fbbf24", flexShrink: 0 }} />,
    "Something went wrong loading this page.", state.message, true);
}
