"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CloudOff, RefreshCw } from "lucide-react";
import { API_BASE } from "@/lib/api";

const POLL_MS = 5000;
const MAX_TRIES = 18; // ~90 seconds: free hosts can take up to a minute to wake

/**
 * Shown when a page couldn't load data from the backend. Polls /health and
 * refreshes the page as soon as the server answers.
 */
export default function BackendStatus({ unreachable }: { unreachable: boolean }) {
  const router = useRouter();
  const [tries, setTries] = useState(0);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!unreachable || tries >= MAX_TRIES) return;
    const id = setTimeout(async () => {
      setChecking(true);
      try {
        const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        if (res.ok) {
          router.refresh();
          return;
        }
      } catch {
        // still unreachable
      } finally {
        setChecking(false);
      }
      setTries(t => t + 1);
    }, POLL_MS);
    return () => clearTimeout(id);
  }, [unreachable, tries, router]);

  if (!unreachable) return null;
  const gaveUp = tries >= MAX_TRIES;

  return (
    <div role="alert" className="glass" style={{
      padding: "14px 18px", marginBottom: "20px", display: "flex", gap: "12px", alignItems: "flex-start",
      border: "1px solid rgba(251, 191, 36, 0.35)", background: "rgba(251, 191, 36, 0.06)", borderRadius: "12px",
    }}>
      <CloudOff size={18} style={{ color: "#fbbf24", flexShrink: 0, marginTop: "2px" }} />
      <div style={{ flex: 1, fontSize: "13px", lineHeight: 1.5 }}>
        <strong>Can&apos;t reach the Feynlist server.</strong>{" "}
        {gaveUp
          ? "It's still not answering. Please try again in a few minutes."
          : "If it hasn't been used for a while, it may be waking up, which can take up to a minute. Retrying automatically…"}
        <div style={{ color: "var(--text-muted)", fontSize: "12px", marginTop: "2px" }}>
          Nothing shown on this page is your real data until the server responds.
        </div>
      </div>
      <button
        onClick={() => { setTries(0); router.refresh(); }}
        disabled={checking}
        style={{
          display: "flex", alignItems: "center", gap: "6px", background: "transparent",
          border: "1px solid rgba(251, 191, 36, 0.4)", color: "#fbbf24", borderRadius: "8px",
          padding: "6px 10px", fontSize: "12px", cursor: "pointer", flexShrink: 0,
        }}
      >
        <RefreshCw size={13} /> Retry now
      </button>
    </div>
  );
}
