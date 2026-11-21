"use client";

import { useState } from "react";
import { Key, Server, Cpu } from "lucide-react";

export default function SettingsPage() {
  const [apiUrl, setApiUrl] = useState(
    typeof window !== "undefined"
      ? localStorage.getItem("api_url") ?? "http://localhost:8000"
      : "http://localhost:8000"
  );
  const [saved, setSaved] = useState(false);

  const save = () => {
    localStorage.setItem("api_url", apiUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div style={{ padding: "32px", maxWidth: "600px" }}>
      <div style={{ marginBottom: "32px" }}>
        <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Configuration
        </div>
        <h1 style={{ fontSize: "28px", fontWeight: 700 }} className="gradient-text">Settings</h1>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {/* API URL */}
        <div className="glass" style={{ padding: "20px" }}>
          <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "12px" }}>
            <Server size={16} style={{ color: "var(--accent)" }} />
            <span style={{ fontSize: "14px", fontWeight: 600 }}>Backend URL</span>
          </div>
          <input
            value={apiUrl}
            onChange={e => setApiUrl(e.target.value)}
            style={{
              width: "100%", background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)",
              borderRadius: "8px", padding: "10px 14px", color: "var(--text)", fontSize: "13px",
              outline: "none", fontFamily: "inherit",
            }}
          />
          <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "8px" }}>
            Default: http://localhost:8000 — start the API with{" "}
            <code style={{ color: "var(--accent)", fontSize: "11px" }}>uvicorn api.main:app --reload</code>
          </div>
        </div>

        {/* How to start */}
        <div className="glass" style={{ padding: "20px" }}>
          <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "12px" }}>
            <Cpu size={16} style={{ color: "var(--accent-2)" }} />
            <span style={{ fontSize: "14px", fontWeight: 600 }}>Quick Start</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {[
              "cd d:\\feynlistV1",
              ".venv\\Scripts\\uvicorn api.main:app --reload",
              "# Then open http://localhost:8000/docs",
            ].map((cmd, i) => (
              <code key={i} style={{
                display: "block", background: "rgba(255,255,255,0.04)", border: "1px solid var(--border)",
                borderRadius: "6px", padding: "8px 12px", fontSize: "12px",
                color: cmd.startsWith("#") ? "var(--text-muted)" : "#c084fc",
                fontFamily: "monospace",
              }}>{cmd}</code>
            ))}
          </div>
        </div>

        <button
          onClick={save}
          style={{
            padding: "12px 24px", borderRadius: "10px", border: "none",
            background: saved ? "#34d399" : "var(--accent)",
            color: "white", fontWeight: 600, fontSize: "14px",
            cursor: "pointer", transition: "background 0.2s",
          }}
        >
          {saved ? "Saved ✓" : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
