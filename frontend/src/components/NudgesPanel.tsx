"use client";

import { useEffect, useState } from "react";
import { BellRing } from "lucide-react";
import { api, type Nudge } from "@/lib/api";
import { AGENTS, TRIGGER_LABELS, type AgentKey } from "@/lib/agents";
import SampleBadge from "./SampleBadge";

/** Latest unprompted coach messages (nudges) for this session. */
export default function NudgesPanel({ refreshKey }: { refreshKey: number }) {
  const [nudges, setNudges] = useState<Nudge[] | null>(null);

  useEffect(() => {
    let alive = true;
    const load = () => api.agents.nudges(3).then(r => { if (alive) setNudges(r.nudges); }).catch(() => {});
    load();
    const id = setInterval(load, 20000);
    return () => { alive = false; clearInterval(id); };
  }, [refreshKey]);

  return (
    <div className="glass" style={{ padding: "16px 18px", marginBottom: "16px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", fontWeight: 600, marginBottom: "10px" }}>
        <BellRing size={15} style={{ color: "var(--accent-2)" }} /> Council nudges
      </div>
      {nudges === null ? (
        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Loading…</div>
      ) : nudges.length === 0 ? (
        <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
          No nudges yet. Complete a task or use a demo control and a coach will respond here.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {nudges.map(n => {
            const a = AGENTS[n.agent_id as AgentKey] ?? AGENTS.freya;
            return (
              <div key={n.id} style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
                <div style={{ fontSize: "16px", lineHeight: 1 }}>{a.emoji}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: "11px", color: a.color, fontWeight: 600 }}>
                    {a.name} · <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>{TRIGGER_LABELS[n.triggered_by] ?? n.triggered_by}</span>
                  </div>
                  <div style={{ fontSize: "13px", lineHeight: 1.5, overflowWrap: "anywhere" }}>{n.content}</div>
                  {n.is_sample && <SampleBadge label={n.sample_label} reason={n.sample_reason} />}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
