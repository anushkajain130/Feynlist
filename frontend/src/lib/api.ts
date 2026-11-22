/**
 * Feynlist API Client
 * Typed wrappers for every backend endpoint.
 */

import { getSessionId, getTimeZone, sessionHeaders } from "./session";

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
export const API_BASE = BASE;

/** Error carrying the server's friendly `detail` message (never raw provider text). */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function handle<T>(res: Response, label: string): Promise<T> {
  if (!res.ok) {
    let detail = `${label} → ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch { /* not JSON */ }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", headers: sessionHeaders() });
  return handle<T>(res, `GET ${path}`);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...sessionHeaders() },
    body: JSON.stringify(body ?? {}),
  });
  return handle<T>(res, `POST ${path}`);
}

// ─── Types ───────────────────────────────────────────────────────────────────

export interface Task {
  id: string;
  date: string;
  task: string;
  start_time: string;
  end_time: string;
  points: number;
  completed: boolean;
  task_class: string;
  sub_class: string | null;
  start_and_sit: boolean;
  complete_task: boolean;
  be_attentive: boolean;
  slider_val: number;
  ps_var: number;
}

export interface TaskListResponse {
  date: string;
  tasks: Task[];
  total: number;
  completed: number;
  completion_pct: number;
}

export interface DailyMetrics {
  date: string;
  alertness: number;
  discipline: number;
  ps_hrs: number;
  aura: number;
  retention_streak: number;
  total_points: number;
  tasks_completed: number;
  tasks_total: number;
  completion_rate: number;
  has_data: boolean;
  /** Daily check-in: null = not answered, true = kept commitment, false = "not today" */
  kept_commitment: boolean | null;
}

export interface TrendResponse {
  metric: string;
  direction: "improving" | "declining" | "stable";
  data_points: { date: string; value: number }[];
  avg_7day: number;
}

export interface WeeklySummary {
  week_start: string;
  avg_discipline: number;
  avg_alertness: number;
  total_ps_hrs: number;
  avg_aura: number;
  best_day: string | null;
  worst_day: string | null;
  streak_delta: number;
}

export interface BurnoutSignal {
  detected: boolean;
  severity: string;
  factors: string[];
  recommendation: string;
}

export interface AgentMessage {
  id: string;
  agent_id: string;
  display_name: string;
  content: string;
  timestamp: string;
  triggered_by: string | null;
  tool_used: string | null;
  is_sample: boolean;
  sample_label: string | null;
  sample_reason: string | null;
}

export interface CouncilResponse {
  messages: AgentMessage[];
  total_agents: number;
}

export interface AgentStatus {
  agents: Record<string, { ready: boolean; seconds_until_ready: number }>;
  ai_configured: boolean;
}

export interface HealthResponse {
  status: string;
  db_ok: boolean;
  scheduler_running: boolean;
  agents_ready: number;
}

// ─── Task endpoints ───────────────────────────────────────────────────────────

export const api = {
  tasks: {
    today: () => get<TaskListResponse>("/api/tasks/today"),
    forDate: (date: string) => get<TaskListResponse>(`/api/tasks/${date}`),
    current: () => get<Task | null>("/api/tasks/today/current"),
    toggleSubtask: (taskId: string, subtaskName: string, value: boolean, sliderVal?: number) =>
      post<{ success: boolean; task: Task }>("/api/tasks/toggle-subtask", {
        task_id: taskId,
        subtask_name: subtaskName,
        value,
        slider_val: sliderVal,
      }),
    toggleComplete: (taskId: string, completed: boolean, sliderVal?: number) =>
      post<{ success: boolean; task: Task }>("/api/tasks/toggle-complete", {
        task_id: taskId,
        completed,
        slider_val: sliderVal,
      }),
    schedule: (body: { date?: string; tasks: { name: string; start_time: string; end_time: string; task_class: string; sub_class?: string | null }[] }) =>
      post<{ date: string; tasks_created: number }>("/api/tasks/schedule", body),
  },
  analytics: {
    today: () => get<DailyMetrics>("/api/analytics/today"),
    history: (days = 7) => get<DailyMetrics[]>(`/api/analytics/history?days=${days}`),
    trend: (metric: string, days = 7) =>
      get<TrendResponse>(`/api/analytics/trends/${metric}?days=${days}`),
    weekly: () => get<WeeklySummary>("/api/analytics/summary/week"),
    burnout: () => get<BurnoutSignal>("/api/analytics/burnout"),
    checkIn: (keptCommitment: boolean, date?: string) =>
      post<DailyMetrics>("/api/analytics/check-in", { kept_commitment: keptCommitment, date }),
  },
  agents: {
    sendMessage: (message: string, agentId?: string) =>
      post<CouncilResponse>("/api/agents/message", { message, agent_id: agentId }),
    status: () => get<AgentStatus>("/api/agents/status"),
    tokensToday: () => get<{ total_tokens_today: number }>("/api/agents/tokens/today"),
    nudges: (limit = 5) => get<{ nudges: Nudge[] }>(`/api/agents/nudges?limit=${limit}`),
    budget: () => get<AIBudget>("/api/agents/budget"),
  },
  demo: {
    status: () => get<DemoStatus>("/api/demo/status"),
    reset: () => post<{ reset: boolean }>("/api/demo/reset", {}),
    loadSample: () => post<{ loaded_days: number }>("/api/demo/load-sample", {}),
    trigger: (kind: DemoTrigger) => post<DemoTriggerResult>(`/api/demo/trigger/${kind}`, {}),
  },
  health: () => get<HealthResponse>("/health"),
};

// ─── Demo ─────────────────────────────────────────────────────────────────────

export interface Nudge {
  id: string;
  agent_id: string;
  content: string;
  triggered_by: string;
  model_used: string;
  timestamp: string;
  is_sample: boolean;
  sample_label: string | null;
  sample_reason: string | null;
}

export interface AIBudget {
  ai_configured: boolean;
  live_limit: number | null;   // null = no per-session limit (single-user mode)
  live_left: number | null;
  daily_cap_reached: boolean;
  mode: "live" | "sample";
  council_live: boolean;
  notice: string;
}

export interface DemoStatus {
  demo_mode: boolean;
  sample_data: boolean;
  today: string;
  notice: string | null;
}

export type DemoTrigger = "missed-task" | "complete-task" | "end-of-day" | "check-in";

export interface DemoTriggerResult {
  kind: DemoTrigger;
  detail: string;
  cooldowns_bypassed?: boolean;
  messages: { id: string; agent_id: string; display_name: string; content: string; triggered_by: string | null; is_sample: boolean }[];
}

// ─── WebSocket ────────────────────────────────────────────────────────────────

/** Websocket URL carrying the session id and time zone (headers can't be set on a browser websocket). */
export function wsUrl(): string {
  const base = BASE.replace(/^http/, "ws");
  const q = new URLSearchParams({ session: getSessionId(), tz: getTimeZone() });
  return `${base}/api/agents/ws?${q.toString()}`;
}
