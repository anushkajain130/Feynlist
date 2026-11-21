/**
 * Feynlist API Client
 * Typed wrappers for every backend endpoint.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json();
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
  relapsed: boolean;
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
}

export interface CouncilResponse {
  messages: AgentMessage[];
  total_agents: number;
}

export interface AgentStatus {
  agents: Record<string, { ready: boolean; seconds_until_ready: number }>;
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
    checkIn: (relapsed: boolean, date?: string) =>
      post<DailyMetrics>("/api/analytics/check-in", { relapsed, date }),
  },
  agents: {
    sendMessage: (message: string, agentId?: string) =>
      post<CouncilResponse>("/api/agents/message", { message, agent_id: agentId }),
    status: () => get<AgentStatus>("/api/agents/status"),
    tokensToday: () => get<{ total_tokens_today: number }>("/api/agents/tokens/today"),
  },
  health: () => get<HealthResponse>("/health"),
};

// ─── WebSocket ────────────────────────────────────────────────────────────────

export const WS_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
  .replace("http", "ws") + "/api/agents/ws";
