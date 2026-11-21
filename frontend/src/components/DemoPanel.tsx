"use client";

import { useState } from "react";
import { FlaskConical, ChevronDown, ChevronUp } from "lucide-react";
import { api, ApiError, type DemoTrigger } from "@/lib/api";

const CONTROLS: { kind: DemoTrigger; label: string; who: string }[] = [
  { kind: "missed-task", label: "Mark a task as missed", who: "Freya" },
  { kind: "complete-task", label: "Complete a task", who: "Albedo" },
  { kind: "end-of-day", label: "Simulate end of day", who: "Anya" },
  { kind: "check-in", label: "Trigger a check-in", who: "ZeroTwo" },
];

const btn: React.CSSProperties = {
  background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)", color: "var(--text)",
  padding: "8px 12px", borderRadius: "8px", fontSize: "12px", cursor: "pointer", textAlign: "left",
};

/**
 * Demo-mode panel: sample-data notice, the 3-minute evaluation guide and demo
 * controls that fire the real proactive event paths (cooldowns bypassed).
 */
export default function DemoPanel({ onChanged }: { onChanged: () => Promise<void> }) {
  const [open, setOpen] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const run = async (key: string, action: () => Promise<string>) => {
    setBusy(key);
    setResult(null);
    try {
      setResult(await action());
      await onChanged();
    } catch (e) {
      setResult(e instanceof ApiError ? e.message : "Couldn't reach the server. Please try again.");
    } finally {
      setBusy(null);
    }
  };

  const trigger = (kind: DemoTrigger) => run(kind, async () => {
    const r = await api.demo.trigger(kind);
    if (r.messages.length === 0) return `${r.detail} No coach reply: live AI isn't available right now.`;
    return `${r.detail} ${r.messages.map(m => m.display_name).join(", ")} replied (see Council nudges).`;
  });

  return (
    <div className="glass" style={{ padding: "16px 18px", marginBottom: "16px", border: "1px solid rgba(94, 234, 212, 0.25)" }}>
      <button onClick={() => setOpen(!open)} style={{
        display: "flex", width: "100%", alignItems: "center", gap: "8px", background: "transparent",
        border: "none", color: "var(--text)", cursor: "pointer", padding: 0, textAlign: "left",
      }}>
        <FlaskConical size={15} style={{ color: "var(--accent-2)" }} />
        <span style={{ fontSize: "13px", fontWeight: 600, flex: 1 }}>
          Demo mode · <span style={{ color: "var(--accent-2)" }}>Sample data</span> · How to evaluate in 3 minutes
        </span>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {open && (
        <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "14px", fontSize: "12.5px", lineHeight: 1.6 }}>
          <p style={{ color: "var(--text-muted)" }}>
            This browser has its own private copy of the app filled with <strong>sample data</strong>: about two
            weeks of made-up history so the charts and streak make sense. Nothing here is a real person&apos;s data.
            It lives in temporary storage and may reset when the server restarts.
          </p>
          <ol style={{ paddingLeft: "18px", display: "flex", flexDirection: "column", gap: "4px" }}>
            <li><strong>Track:</strong> open a block below and mark Start &amp; Sit, Complete and Be Attentive. Discipline, Alertness and Aura update.</li>
            <li><strong>Reflect:</strong> open Analytics (14-day charts and the workload signal) and the Daily Check-In.</li>
            <li><strong>Get nudged:</strong> use a demo control below. The coach&apos;s reply appears under Council nudges.</li>
            <li><strong>Chat:</strong> open the Council tab and message a coach.</li>
          </ol>
          <div>
            <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: "6px" }}>
              Demo controls (demo mode: cooldowns bypassed)
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "8px" }}>
              {CONTROLS.map(c => (
                <button key={c.kind} style={btn} disabled={busy !== null} onClick={() => trigger(c.kind)}>
                  {busy === c.kind ? "Working…" : c.label}
                  <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>→ {c.who}</div>
                </button>
              ))}
              <button style={btn} disabled={busy !== null}
                onClick={() => run("load", async () => { const r = await api.demo.loadSample(); return `Loaded ${r.loaded_days} days of sample history.`; })}>
                {busy === "load" ? "Working…" : "Load sample two-week history"}
                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Keeps today&apos;s plan</div>
              </button>
              <button style={btn} disabled={busy !== null}
                onClick={() => run("reset", async () => { await api.demo.reset(); return "Demo reset to the starting sample data."; })}>
                {busy === "reset" ? "Working…" : "Reset demo"}
                <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Back to the start</div>
              </button>
            </div>
            {result && <div role="status" style={{ marginTop: "8px", fontSize: "12px", color: "var(--text-muted)" }}>{result}</div>}
          </div>
        </div>
      )}
    </div>
  );
}
