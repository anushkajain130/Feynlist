"use client";

import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, CartesianGrid,
} from "recharts";
import { format, parseISO } from "date-fns";
import { TrendingUp, TrendingDown, Minus, AlertTriangle, CheckCircle } from "lucide-react";
import { DailyMetrics, WeeklySummary, BurnoutSignal } from "@/lib/api";

interface Props {
  history: DailyMetrics[] | null;
  weekly: WeeklySummary | null;
  burnout: BurnoutSignal | null;
}

const TOOLTIP_STYLE = {
  background: "#18181f",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: "8px",
  color: "#e8e8f0",
  fontSize: "12px",
};

function TrendChip({ direction }: { direction: string }) {
  if (direction === "improving") return (
    <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "#34d399", fontSize: "12px" }}>
      <TrendingUp size={13} /> Improving
    </span>
  );
  if (direction === "declining") return (
    <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "#f87171", fontSize: "12px" }}>
      <TrendingDown size={13} /> Declining
    </span>
  );
  return (
    <span style={{ display: "flex", alignItems: "center", gap: "4px", color: "#6b6b80", fontSize: "12px" }}>
      <Minus size={13} /> Stable
    </span>
  );
}

function ChartCard({ title, children, trend }: { title: string; children: React.ReactNode; trend?: string }) {
  return (
    <div className="glass" style={{ padding: "20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
        <span style={{ fontSize: "14px", fontWeight: 600 }}>{title}</span>
        {trend && <TrendChip direction={trend} />}
      </div>
      {children}
    </div>
  );
}

export default function AnalyticsClient({ history, weekly, burnout }: Props) {
  const chartData = (history ?? []).map(d => ({
    date: format(parseISO(d.date), "MMM d"),
    discipline: d.discipline,
    alertness: d.alertness,
    aura: d.aura,
    ps_hrs: d.ps_hrs,
    points: d.total_points,
  }));

  const emptyState = (
    <div style={{ height: "140px", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "13px" }}>
      No data yet — complete some tasks first
    </div>
  );

  return (
    <div className="page">
      {/* Header */}
      <div style={{ marginBottom: "32px" }}>
        <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Performance
        </div>
        <h1 style={{ fontSize: "28px", fontWeight: 700 }} className="gradient-text">Analytics</h1>
      </div>

      {/* Weekly summary cards */}
      {weekly && (
        <div className="grid-stats" style={{ marginBottom: "24px" }}>
          {[
            { label: "7-Day Discipline", value: `${weekly.avg_discipline.toFixed(0)}%`, color: "#7c5cfc" },
            { label: "7-Day Alertness", value: `${weekly.avg_alertness.toFixed(0)}%`, color: "#818cf8" },
            { label: "Total Study Hours", value: `${weekly.total_ps_hrs.toFixed(1)}h`, color: "#34d399" },
            { label: "Avg Aura", value: weekly.avg_aura.toFixed(3), color: "#f472b6" },
          ].map(({ label, value, color }) => (
            <div key={label} className="glass" style={{ padding: "16px 20px" }}>
              <div style={{ fontSize: "22px", fontWeight: 700, color }}>{value}</div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Charts grid */}
      <div className="grid-2" style={{ marginBottom: "16px" }}>
        <ChartCard title="Discipline (14 days)" trend={chartData.length > 3 ? (chartData[chartData.length - 1].discipline > chartData[0].discipline ? "improving" : "declining") : "stable"}>
          {chartData.length === 0 ? emptyState : (
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="gDisc" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7c5cfc" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#7c5cfc" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: "#6b6b80", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "#6b6b80", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="discipline" stroke="#7c5cfc" fill="url(#gDisc)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Alertness (14 days)">
          {chartData.length === 0 ? emptyState : (
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="gAlert" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#818cf8" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: "#6b6b80", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: "#6b6b80", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="alertness" stroke="#818cf8" fill="url(#gAlert)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Aura Score (14 days)">
          {chartData.length === 0 ? emptyState : (
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="gAura" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f472b6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#f472b6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: "#6b6b80", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#6b6b80", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="aura" stroke="#f472b6" fill="url(#gAura)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        <ChartCard title="Study Hours (14 days)">
          {chartData.length === 0 ? emptyState : (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={chartData}>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "#6b6b80", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#6b6b80", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="ps_hrs" fill="#34d399" radius={[4, 4, 0, 0]} opacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* Burnout card */}
      {burnout && (
        <div className="glass" style={{
          padding: "20px",
          border: burnout.detected ? "1px solid rgba(248,113,113,0.3)" : "1px solid rgba(52,211,153,0.2)",
        }}>
          <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
            <div style={{
              color: burnout.detected ? "#f87171" : "#34d399",
              paddingTop: "2px",
            }}>
              {burnout.detected ? <AlertTriangle size={20} /> : <CheckCircle size={20} />}
            </div>
            <div>
              <div style={{ fontWeight: 600, marginBottom: "4px" }}>
                Burnout Signal — <span style={{ color: burnout.detected ? "#f87171" : "#34d399" }}>
                  {burnout.severity.toUpperCase()}
                </span>
              </div>
              <div style={{ fontSize: "13px", color: "var(--text-muted)", marginBottom: "8px" }}>
                {burnout.recommendation}
              </div>
              {burnout.factors.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
                  {burnout.factors.map((f, i) => (
                    <span key={i} style={{
                      fontSize: "11px", padding: "3px 10px", borderRadius: "20px",
                      background: "rgba(248,113,113,0.1)", color: "#f87171",
                    }}>{f}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
