export const AGENTS = {
  freya:   { name: "Freya",    color: "#7c5cfc", emoji: "⚔️",  desc: "Direct & honest" },
  albedo:  { name: "Albedo",   color: "#f472b6", emoji: "🎉",  desc: "Celebrates wins" },
  anya:    { name: "Anya",     color: "#34d399", emoji: "🌸",  desc: "Warm & rest-aware" },
  zerotwo: { name: "Zero Two", color: "#818cf8", emoji: "🎯",  desc: "Analytical" },
  mohini:  { name: "Mohini",   color: "#fbbf24", emoji: "🌿",  desc: "Calm & energy" },
  council: { name: "Council",  color: "#e8e8f0", emoji: "🏛️",  desc: "All together" },
} as const;

export type AgentKey = keyof typeof AGENTS;

export const TRIGGER_LABELS: Record<string, string> = {
  task_missed: "Missed task",
  task_completed: "Task completed",
  day_start: "Day start",
  day_end_review: "End of day",
  scheduled_checkin: "Check-in",
  burnout_detected: "Workload signal",
  streak_broken: "Streak reset",
  streak_milestone: "Streak milestone",
};
