/** Visible label on every pre-written sample reply: never presented as live. */
export default function SampleBadge({ label, reason }: { label?: string | null; reason?: string | null }) {
  return (
    <div style={{ marginTop: "6px", fontSize: "11px", lineHeight: 1.4 }}>
      <span style={{
        display: "inline-block", padding: "1px 8px", borderRadius: "10px", fontWeight: 600,
        color: "#fbbf24", background: "rgba(251, 191, 36, 0.1)", border: "1px solid rgba(251, 191, 36, 0.3)",
      }}>
        {label ?? "Sample reply (pre-written, not live)"}
      </span>
      {reason && <div style={{ color: "var(--text-muted)", marginTop: "3px" }}>{reason}</div>}
    </div>
  );
}
