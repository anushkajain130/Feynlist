"use client";

import { useState, useCallback } from "react";
import { format } from "date-fns";
import { CheckCircle2, Circle, Clock, Zap, Brain, Target, Flame, Plus, Trash2, Calendar, Sparkles, Check, X, ChevronDown, ChevronUp } from "lucide-react";
import { api, Task, TaskListResponse, DailyMetrics } from "@/lib/api";
import clsx from "clsx";

interface Props {
  initialTasks: TaskListResponse | null;
  initialMetrics: DailyMetrics | null;
}

interface EditableTask {
  name: string;
  start_time: string;
  end_time: string;
  task_class: string;
  sub_class: string | null;
}

const SUBTASKS = [
  { key: "start_and_sit", label: "Start & Sit", apiName: "Start_and_Sit_for_5_mins", pct: "50%" },
  { key: "complete_task", label: "Complete", apiName: "Complete_the_task", pct: "30%" },
  { key: "be_attentive", label: "Be Attentive", apiName: "Be_attentive", pct: "20%" },
] as const;

const CLASS_COLORS: Record<string, string> = {
  Academics_Selfstudy: "#818cf8",
  Academic_Classes: "#6ee7b7",
  Project: "#fbbf24",
  Work: "#f472b6",
  Yoga_and_Wellness: "#34d399",
  Side_Business: "#a78bfa",
  Book_Reading: "#60a5fa",
  Social: "#f97316",
  Break: "#6b7280",
  Sleep: "#4b5563",
  Deviated: "#ef4444",
  revived: "#10b981",
  Unspecified: "#9ca3af",
};

const DEFAULT_CLASSES = [
  { value: "Yoga_and_Wellness", label: "Yoga & Wellness" },
  { value: "Academics_Selfstudy", label: "Academics Selfstudy" },
  { value: "Academic_Classes", label: "Academic Classes" },
  { value: "Project", label: "Project" },
  { value: "Work", label: "Work" },
  { value: "Side_Business", label: "Side Business" },
  { value: "Book_Reading", label: "Book Reading" },
  { value: "Social", label: "Social" },
  { value: "Break", label: "Break" },
  { value: "Sleep", label: "Sleep" },
  { value: "Self_Growth", label: "Self Growth" },
  { value: "ExtraActi", label: "Extra Activity" },
  { value: "Unspecified", label: "Unspecified" },
];

const GUIDELINE_SCHEDULE: EditableTask[] = [
  { name: "Yoga and Wellness", start_time: "06:00", end_time: "07:00", task_class: "Yoga_and_Wellness", sub_class: null },
  { name: "Academics Selfstudy", start_time: "07:00", end_time: "09:00", task_class: "Academics_Selfstudy", sub_class: null },
  { name: "Project Development", start_time: "09:00", end_time: "10:00", task_class: "Project", sub_class: null },
  { name: "Academics Classes", start_time: "10:00", end_time: "12:00", task_class: "Academic_Classes", sub_class: null },
  { name: "Midday Break & Lunch", start_time: "12:00", end_time: "13:00", task_class: "Break", sub_class: null },
  { name: "Side Business Focus", start_time: "13:00", end_time: "15:00", task_class: "Side_Business", sub_class: null },
  { name: "Afternoon Deep Work", start_time: "15:00", end_time: "17:00", task_class: "Academics_Selfstudy", sub_class: null },
  { name: "Evening Social & Wellness", start_time: "17:00", end_time: "19:00", task_class: "Yoga_and_Wellness", sub_class: null },
  { name: "Dinner & Winding Down", start_time: "19:00", end_time: "21:00", task_class: "Break", sub_class: null },
  { name: "Book Reading & Self Reflection", start_time: "21:00", end_time: "22:00", task_class: "Book_Reading", sub_class: null },
  { name: "Sleep & Regeneration", start_time: "22:00", end_time: "06:00", task_class: "Sleep", sub_class: null },
];

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; color: string;
}) {
  return (
    <div className="glass" style={{ padding: "20px", display: "flex", gap: "16px", alignItems: "flex-start" }}>
      <div style={{
        width: "40px", height: "40px", borderRadius: "10px",
        background: `${color}22`, display: "flex", alignItems: "center",
        justifyContent: "center", color, flexShrink: 0,
      }}>
        <Icon size={18} />
      </div>
      <div>
        <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--text)", lineHeight: 1 }}>{value}</div>
        <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>{label}</div>
        {sub && <div style={{ fontSize: "11px", color, marginTop: "2px" }}>{sub}</div>}
      </div>
    </div>
  );
}

function TaskRow({ 
  task, 
  onToggle, 
  onToggleComplete, 
  onAttentionChange 
}: { 
  task: Task; 
  onToggle: (t: Task) => void;
  onToggleComplete: (t: Task, completed: boolean) => void;
  onAttentionChange: (t: Task, attention: number) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const color = CLASS_COLORS[task.task_class] ?? "#6b6b80";
  const isActive = (() => {
    const now = new Date();
    const [sh, sm] = task.start_time.split(":").map(Number);
    const [eh, em] = task.end_time.split(":").map(Number);
    const start = sh * 60 + sm;
    const end = eh * 60 + em;
    const cur = now.getHours() * 60 + now.getMinutes();
    return cur >= start && cur <= end;
  })();

  return (
    <div
      className="fade-in"
      style={{
        display: "flex", flexDirection: "column", gap: "10px",
        padding: "14px 16px", borderRadius: "12px",
        background: isActive ? "rgba(124,92,252,0.07)" : "rgba(255,255,255,0.02)",
        border: isActive ? "1px solid rgba(124,92,252,0.3)" : "1px solid rgba(255,255,255,0.03)",
        transition: "all 0.15s",
      }}
    >
      {/* Collapsed Header / Row */}
      <div 
        style={{ display: "flex", gap: "12px", alignItems: "center", cursor: "pointer", width: "100%" }}
        onClick={(e) => {
          const target = e.target as HTMLElement;
          if (target.closest("button") || target.closest("input")) return;
          setIsExpanded(!isExpanded);
        }}
      >
        {/* Overall Completion Checkbox Shortcut */}
        <button
          onClick={() => onToggleComplete(task, !task.completed)}
          style={{
            background: "transparent", border: "none", padding: 0, margin: 0,
            cursor: "pointer", display: "flex", alignItems: "center",
            color: task.completed ? "var(--accent-2)" : "var(--text-muted)",
            transition: "color 0.15s",
          }}
        >
          {task.completed ? <CheckCircle2 size={18} /> : <Circle size={18} />}
        </button>

        {/* Time */}
        <div style={{ minWidth: "80px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", fontVariantNumeric: "tabular-nums" }}>
            {task.start_time}
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)", opacity: 0.6 }}>{task.end_time}</div>
        </div>

        {/* Color stripe */}
        <div style={{ width: "3px", height: "24px", borderRadius: "2px", background: color, flexShrink: 0 }} />

        {/* Main Info */}
        <div style={{ flex: 1, display: "flex", gap: "8px", alignItems: "center" }}>
          {isActive && <span className="pulse" style={{
            width: "6px", height: "6px", borderRadius: "50%",
            background: "var(--accent)", display: "inline-block",
          }} />}
          <span style={{
            fontSize: "13px", fontWeight: 500,
            color: task.completed ? "var(--text-muted)" : "var(--text)",
            textDecoration: task.completed ? "line-through" : "none",
          }}>{task.task}</span>
          <span style={{
            fontSize: "10px", padding: "2px 8px", borderRadius: "20px",
            background: `${color}22`, color, fontWeight: 500,
          }}>{task.task_class.replace(/_/g, " ")}</span>
          <span style={{ marginLeft: "auto", fontSize: "12px", color: "var(--text-muted)" }}>
            {task.points}pts
          </span>
        </div>

        {/* Expand Indicator */}
        <div style={{ color: "var(--text-muted)", display: "flex", alignItems: "center" }}>
          {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      {/* Expanded View */}
      {isExpanded && (
        <div 
          className="fade-in"
          style={{ 
            marginTop: "8px", paddingTop: "12px", 
            borderTop: "1px solid rgba(255,255,255,0.05)",
            display: "flex", flexDirection: "column", gap: "14px"
          }}
        >
          {/* Attention Level Slider */}
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "12px", fontWeight: 500, display: "flex", alignItems: "center", gap: "6px" }}>
                <Brain size={14} style={{ color: "#818cf8" }} /> Attention Level
              </span>
              <span style={{ fontSize: "12px", fontWeight: 600, color: "#818cf8" }}>
                {task.slider_val}%
              </span>
            </div>
            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <input 
                type="range" 
                min="0" 
                max="100" 
                value={task.slider_val} 
                onChange={(e) => onAttentionChange(task, Number(e.target.value))}
                style={{ 
                  flex: 1, 
                  height: "4px", 
                  borderRadius: "2px", 
                  background: "rgba(255,255,255,0.1)",
                  outline: "none",
                  cursor: "pointer",
                  accentColor: "#818cf8"
                }}
              />
              <span style={{ fontSize: "10px", color: "var(--text-muted)", width: "30px", textAlign: "right" }}>
                {task.slider_val >= 90 ? "Peak" : task.slider_val >= 70 ? "High" : task.slider_val >= 40 ? "Medium" : "Low"}
              </span>
            </div>
          </div>

          {/* Individual Subtasks Toggle */}
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <span style={{ fontSize: "11px", color: "var(--text-muted)", fontWeight: 500 }}>
              Milestones & Subtasks
            </span>
            <div style={{ display: "flex", gap: "8px" }}>
              {SUBTASKS.map(({ key, label, apiName }) => {
                const done = task[key as keyof Task] as boolean;
                return (
                  <button
                    key={key}
                    onClick={() => onToggle({ ...task, [key]: !done })}
                    style={{
                      display: "flex", alignItems: "center", gap: "4px",
                      padding: "4px 10px", borderRadius: "6px", border: "none",
                      background: done ? "rgba(94,234,212,0.12)" : "rgba(255,255,255,0.05)",
                      color: done ? "var(--accent-2)" : "var(--text-muted)",
                      cursor: "pointer", fontSize: "11px", transition: "all 0.15s",
                    }}
                  >
                    {done ? <CheckCircle2 size={12} /> : <Circle size={12} />}
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DashboardClient({ initialTasks, initialMetrics }: Props) {
  const [taskData, setTaskData] = useState(initialTasks);
  const [metrics, setMetrics] = useState(initialMetrics);
  const [isPlanning, setIsPlanning] = useState(false);
  const [planTasks, setPlanTasks] = useState<EditableTask[]>([]);
  const [planError, setPlanError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [showAuraInfo, setShowAuraInfo] = useState(false);
  const [showPSInfo, setShowPSInfo] = useState(false);
  const [showCheckInModal, setShowCheckInModal] = useState(false);
  const today = format(new Date(), "EEEE, MMMM d");

  const handleToggle = useCallback(async (task: Task) => {
    // Find which subtask changed
    const original = taskData?.tasks.find(t => t.id === task.id);
    if (!original) return;

    for (const { key, apiName } of SUBTASKS) {
      const wasTrue = original[key as keyof Task] as boolean;
      const isNow = task[key as keyof Task] as boolean;
      if (wasTrue !== isNow) {
        try {
          const res = await api.tasks.toggleSubtask(task.id, apiName, isNow);
          setTaskData(prev => {
            if (!prev) return prev;
            const updatedTasks = prev.tasks.map(t => t.id === task.id ? res.task : t);
            const completedCount = updatedTasks.filter(t => t.completed).length;
            const totalCount = updatedTasks.length;
            const completion_pct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
            return {
              ...prev,
              tasks: updatedTasks,
              completed: completedCount,
              completion_pct,
            };
          });
          
          // Trigger a quick metrics refresh after update
          const newMetrics = await api.analytics.today();
          setMetrics(newMetrics);
        } catch (e) {
          console.error("Toggle failed", e);
        }
        break;
      }
    }
  }, [taskData]);

  const handleToggleComplete = useCallback(async (task: Task, completed: boolean) => {
    try {
      const res = await api.tasks.toggleComplete(task.id, completed, task.slider_val || 100);
      setTaskData(prev => {
        if (!prev) return prev;
        const updatedTasks = prev.tasks.map(t => t.id === task.id ? res.task : t);
        const completedCount = updatedTasks.filter(t => t.completed).length;
        const totalCount = updatedTasks.length;
        const completion_pct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
        return {
          ...prev,
          tasks: updatedTasks,
          completed: completedCount,
          completion_pct,
        };
      });
      
      // Refresh metrics immediately
      const newMetrics = await api.analytics.today();
      setMetrics(newMetrics);
    } catch (e) {
      console.error("Toggle complete failed", e);
    }
  }, [taskData]);

  const handleAttentionChange = useCallback(async (task: Task, attention: number) => {
    // Optimistic UI update for smoothness
    setTaskData(prev => {
      if (!prev) return prev;
      return {
        ...prev,
        tasks: prev.tasks.map(t => t.id === task.id ? { ...t, slider_val: attention } : t)
      };
    });

    try {
      const res = await api.tasks.toggleSubtask(task.id, "Be_attentive", true, attention);
      setTaskData(prev => {
        if (!prev) return prev;
        const updatedTasks = prev.tasks.map(t => t.id === task.id ? res.task : t);
        const completedCount = updatedTasks.filter(t => t.completed).length;
        const totalCount = updatedTasks.length;
        const completion_pct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
        return {
          ...prev,
          tasks: updatedTasks,
          completed: completedCount,
          completion_pct,
        };
      });

      // Refresh metrics immediately
      const newMetrics = await api.analytics.today();
      setMetrics(newMetrics);
    } catch (e) {
      console.error("Attention update failed", e);
    }
  }, []);

  const handleCheckIn = useCallback(async (keptCommitment: boolean) => {
    try {
      const res = await api.analytics.checkIn(keptCommitment);
      setMetrics(res);
    } catch (e) {
      console.error("Check-in failed", e);
    }
  }, []);

  // PLANNING CHECKS
  const startPlanning = () => {
    if (taskData && taskData.tasks.length > 0) {
      setPlanTasks(taskData.tasks.map(t => ({
        name: t.task,
        start_time: t.start_time,
        end_time: t.end_time,
        task_class: t.task_class,
        sub_class: t.sub_class,
      })));
    } else {
      setPlanTasks([
        { name: "Yoga and Wellness", start_time: "06:00", end_time: "07:00", task_class: "Yoga_and_Wellness", sub_class: null },
        { name: "Academics Selfstudy", start_time: "07:00", end_time: "09:00", task_class: "Academics_Selfstudy", sub_class: null },
        { name: "Project Development", start_time: "09:00", end_time: "10:00", task_class: "Project", sub_class: null },
      ]);
    }
    setPlanError(null);
    setIsPlanning(true);
  };

  const loadGuideline = () => {
    setPlanTasks([...GUIDELINE_SCHEDULE]);
    setPlanError(null);
  };

  const addTimeBlock = () => {
    let nextStart = "08:00";
    let nextEnd = "09:00";
    if (planTasks.length > 0) {
      const last = planTasks[planTasks.length - 1];
      nextStart = last.end_time;
      const [h, m] = last.end_time.split(":").map(Number);
      const endH = (h + 1) % 24;
      nextEnd = `${String(endH).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
    }
    setPlanTasks([...planTasks, { name: "", start_time: nextStart, end_time: nextEnd, task_class: "Unspecified", sub_class: null }]);
  };

  const removeTimeBlock = (index: number) => {
    setPlanTasks(planTasks.filter((_, i) => i !== index));
  };

  const updatePlanTask = (index: number, fields: Partial<EditableTask>) => {
    setPlanTasks(planTasks.map((t, i) => i === index ? { ...t, ...fields } : t));
  };

  const saveSchedule = async () => {
    if (planTasks.length === 0) {
      setPlanError("Please add at least one task to your schedule.");
      return;
    }
    for (const t of planTasks) {
      if (!t.name.trim()) {
        setPlanError("All tasks must have a name / description.");
        return;
      }
      if (!t.start_time || !t.end_time) {
        setPlanError("All tasks must have start and end times.");
        return;
      }
    }

    try {
      setIsSaving(true);
      setPlanError(null);
      await api.tasks.schedule({
        tasks: planTasks.map(t => ({
          name: t.name,
          start_time: t.start_time,
          end_time: t.end_time,
          task_class: t.task_class,
          sub_class: t.sub_class,
        }))
      });

      // Reload fresh metrics & tasks
      const [tasksRes, metricsRes] = await Promise.all([
        api.tasks.today(),
        api.analytics.today(),
      ]);

      setTaskData(tasksRes);
      setMetrics(metricsRes);
      setIsPlanning(false);
    } catch (e) {
      console.error(e);
      setPlanError("Failed to save schedule. Make sure the backend server is running.");
    } finally {
      setIsSaving(false);
    }
  };

  const completedCount = taskData?.completed ?? 0;
  const totalCount = taskData?.total ?? 0;
  const pct = taskData?.completion_pct ?? 0;

  return (
    <div style={{ padding: "32px", maxWidth: "1100px", margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "32px" }}>
        <div>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            {today}
          </div>
          <h1 style={{ fontSize: "28px", fontWeight: 700 }} className="gradient-text">
            Dashboard
          </h1>
        </div>
        {!isPlanning && (
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={() => setShowCheckInModal(true)}
              style={{
                background: "rgba(255, 255, 255, 0.03)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                color: "var(--text-muted)",
                padding: "10px 18px",
                borderRadius: "12px",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = "rgba(244, 114, 182, 0.06)";
                e.currentTarget.style.borderColor = "rgba(244, 114, 182, 0.3)";
                e.currentTarget.style.color = "var(--text)";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = "rgba(255, 255, 255, 0.03)";
                e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.08)";
                e.currentTarget.style.color = "var(--text-muted)";
              }}
            >
              <Flame size={15} style={{ color: "#f472b6" }} />
              Daily Check-In
            </button>
            <button
              onClick={startPlanning}
              style={{
                background: "linear-gradient(135deg, #7c5cfc, #6366f1)",
                border: "none",
                color: "white",
                padding: "10px 20px",
                borderRadius: "12px",
                fontWeight: 600,
                fontSize: "13px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                boxShadow: "0 4px 15px rgba(124, 92, 252, 0.3)",
                transition: "transform 0.15s ease",
              }}
              onMouseEnter={e => e.currentTarget.style.transform = "translateY(-1px)"}
              onMouseLeave={e => e.currentTarget.style.transform = "translateY(0)"}
            >
              <Calendar size={15} />
              {taskData && taskData.tasks.length > 0 ? "Modify Schedule" : "Plan Today's Schedule"}
            </button>
          </div>
        )}
      </div>

      {/* PLANNER INTERFACE */}
      {isPlanning ? (
        <div className="glass fade-in" style={{ padding: "28px", marginBottom: "32px", position: "relative", border: "1px solid rgba(124, 92, 252, 0.2)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <div>
              <h2 style={{ fontSize: "18px", fontWeight: 600, display: "flex", alignItems: "center", gap: "8px" }}>
                <Sparkles size={16} style={{ color: "var(--accent)" }} /> Configure Today's Schedule
              </h2>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                Define your timeblocks. Feynlist will track performance per timeblock.
              </div>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              <button
                onClick={loadGuideline}
                style={{
                  background: "rgba(255,255,255,0.05)",
                  color: "var(--text)",
                  border: "1px solid var(--border)",
                  padding: "8px 14px",
                  borderRadius: "8px",
                  fontSize: "12px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Load Guidelines Template
              </button>
              <button
                onClick={addTimeBlock}
                style={{
                  background: "rgba(124, 92, 252, 0.15)",
                  color: "var(--text)",
                  border: "1px solid rgba(124, 92, 252, 0.3)",
                  padding: "8px 14px",
                  borderRadius: "8px",
                  fontSize: "12px",
                  fontWeight: 500,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                }}
              >
                <Plus size={14} /> Add Block
              </button>
            </div>
          </div>

          {planError && (
            <div style={{
              background: "rgba(239, 68, 68, 0.1)",
              border: "1px solid rgba(239, 68, 68, 0.2)",
              color: "#f87171",
              padding: "10px 16px",
              borderRadius: "8px",
              fontSize: "12px",
              marginBottom: "16px",
            }}>
              {planError}
            </div>
          )}

          {/* Time blocks form */}
          <div style={{ display: "flex", flexDirection: "column", gap: "8px", maxHeight: "450px", overflowY: "auto", paddingRight: "4px", marginBottom: "24px" }}>
            {planTasks.map((t, idx) => (
              <div
                key={idx}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 100px 100px 180px 40px",
                  gap: "10px",
                  alignItems: "center",
                  padding: "10px",
                  background: "rgba(255,255,255,0.01)",
                  borderRadius: "8px",
                  border: "1px solid rgba(255,255,255,0.03)",
                }}
              >
                {/* Name */}
                <input
                  type="text"
                  placeholder="What are you doing? (e.g. Project Work)"
                  value={t.name}
                  onChange={e => updatePlanTask(idx, { name: e.target.value })}
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid var(--border)",
                    color: "white",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    outline: "none",
                  }}
                />

                {/* Start Time */}
                <input
                  type="time"
                  value={t.start_time}
                  onChange={e => updatePlanTask(idx, { start_time: e.target.value })}
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid var(--border)",
                    color: "white",
                    padding: "8px 10px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    outline: "none",
                  }}
                />

                {/* End Time */}
                <input
                  type="time"
                  value={t.end_time}
                  onChange={e => updatePlanTask(idx, { end_time: e.target.value })}
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid var(--border)",
                    color: "white",
                    padding: "8px 10px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    outline: "none",
                  }}
                />

                {/* Category */}
                <select
                  value={t.task_class}
                  onChange={e => updatePlanTask(idx, { task_class: e.target.value })}
                  style={{
                    background: "rgba(17, 17, 24, 0.9)",
                    border: "1px solid var(--border)",
                    color: "white",
                    padding: "8px 10px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    outline: "none",
                    cursor: "pointer",
                  }}
                >
                  {DEFAULT_CLASSES.map(cls => (
                    <option key={cls.value} value={cls.value} style={{ background: "#111118", color: "white" }}>
                      {cls.label}
                    </option>
                  ))}
                </select>

                {/* Remove Button */}
                <button
                  onClick={() => removeTimeBlock(idx)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "var(--text-muted)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: "8px",
                    borderRadius: "6px",
                    transition: "color 0.15s, background 0.15s",
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.color = "#ef4444";
                    e.currentTarget.style.background = "rgba(239, 68, 68, 0.08)";
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.color = "var(--text-muted)";
                    e.currentTarget.style.background = "transparent";
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          {/* Action buttons */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", borderTop: "1px solid var(--border)", paddingTop: "20px" }}>
            <button
              onClick={() => setIsPlanning(false)}
              disabled={isSaving}
              style={{
                background: "transparent",
                color: "var(--text-muted)",
                border: "none",
                padding: "10px 18px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              onClick={saveSchedule}
              disabled={isSaving}
              style={{
                background: "linear-gradient(135deg, #7c5cfc, #5eead4)",
                color: "white",
                border: "none",
                padding: "10px 22px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "0 4px 15px rgba(124, 92, 252, 0.2)",
              }}
            >
              {isSaving ? (
                <span>Saving...</span>
              ) : (
                <>
                  <Check size={14} /> Publish Schedule
                </>
              )}
            </button>
          </div>
        </div>
      ) : null}

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px", marginBottom: "28px" }}>
        <StatCard label="Discipline" value={`${metrics?.discipline?.toFixed(0) ?? 0}%`}
          sub={(metrics?.discipline ?? 0) > 70 ? "↑ On track" : "Needs work"}
          icon={Target} color="#7c5cfc" />
        <StatCard label="Alertness" value={`${metrics?.alertness?.toFixed(0) ?? 0}%`}
          icon={Brain} color="#818cf8" />
        
        {/* Clickable Aura Card */}
        <div 
          onClick={() => setShowAuraInfo(!showAuraInfo)} 
          style={{ cursor: "pointer", transition: "transform 0.15s" }}
          onMouseEnter={e => e.currentTarget.style.transform = "translateY(-2px)"}
          onMouseLeave={e => e.currentTarget.style.transform = "translateY(0)"}
          title="Click to learn how Aura is computed!"
        >
          <StatCard label="Aura (Click for Info)" value={(metrics?.aura ?? 0).toFixed(2)}
            sub={`${metrics?.retention_streak ?? 0}d consistency streak · Info`}
            icon={Flame} color="#f472b6" />
        </div>

        {/* Clickable PS Hours Card */}
        <div 
          onClick={() => setShowPSInfo(!showPSInfo)} 
          style={{ cursor: "pointer", transition: "transform 0.15s" }}
          onMouseEnter={e => e.currentTarget.style.transform = "translateY(-2px)"}
          onMouseLeave={e => e.currentTarget.style.transform = "translateY(0)"}
          title="Click to learn how PS Hours are computed!"
        >
          <StatCard label="PS Hours (Click Info)" value={`${metrics?.ps_hrs?.toFixed(1) ?? 0}h`}
            sub="Explain metric"
            icon={Zap} color="#34d399" />
        </div>
      </div>

      {/* Aura explanation info banner */}
      {showAuraInfo && (
        <div className="glass fade-in" style={{
          padding: "16px 20px", marginBottom: "28px", background: "rgba(244, 114, 182, 0.04)",
          border: "1px solid rgba(244, 114, 182, 0.2)", borderRadius: "12px", fontSize: "13px",
          lineHeight: 1.5, color: "var(--text)"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <strong style={{ color: "#f472b6", display: "flex", alignItems: "center", gap: "6px" }}>
              <Flame size={15} /> Understanding Your Aura Score
            </strong>
            <button 
              onClick={() => setShowAuraInfo(false)}
              style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "11px", fontWeight: 600 }}
            >
              Close
            </button>
          </div>
          <p style={{ marginBottom: "8px", fontSize: "12.5px", opacity: 0.9 }}>
            <strong>Aura</strong> represents your cognitive momentum and focus consistency. Unlike binary metrics, it measures how deeply and regularly you execute your scheduled deep-work guidelines.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", fontSize: "12px", opacity: 0.85 }}>
            <div>
              <span style={{ color: "#5eead4" }}><strong>Factors affecting Aura:</strong></span>
              <ul style={{ paddingLeft: "14px", marginTop: "4px" }}>
                <li><strong>Discipline</strong> (Starting scheduled timeblocks on time)</li>
                <li><strong>PS Hours</strong> (Problem Solving study block density)</li>
                <li><strong>Consistency streak</strong> (Days you kept your commitment to your plan)</li>
              </ul>
            </div>
            <div>
              <span style={{ color: "#5eead4" }}><strong>Score mechanics:</strong></span>
              <ul style={{ paddingLeft: "14px", marginTop: "4px" }}>
                <li><strong>Increases</strong> by maintaining high discipline, studying consistently, and protecting your streak.</li>
                <li><strong>Resets</strong> when a day ends without keeping your commitment, or declines gradually if study volume drops.</li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* PS Hours explanation info banner */}
      {showPSInfo && (
        <div className="glass fade-in" style={{
          padding: "16px 20px", marginBottom: "28px", background: "rgba(52, 211, 153, 0.04)",
          border: "1px solid rgba(52, 211, 153, 0.2)", borderRadius: "12px", fontSize: "13px",
          lineHeight: 1.5, color: "var(--text)"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <strong style={{ color: "#34d399", display: "flex", alignItems: "center", gap: "6px" }}>
              <Zap size={15} /> Understanding Problem-Solving (PS) Hours
            </strong>
            <button 
              onClick={() => setShowPSInfo(false)}
              style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "11px", fontWeight: 600 }}
            >
              Close
            </button>
          </div>
          <p style={{ marginBottom: "8px", fontSize: "12.5px", opacity: 0.9 }}>
            <strong>Problem-Solving (PS) Hours</strong> measures the time spent on dedicated, high-concentration cognitive work. It represents a commitment to deliberate practice and mastery.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", fontSize: "12px", opacity: 0.85 }}>
            <div>
              <span style={{ color: "#5eead4" }}><strong>How it is calculated:</strong></span>
              <ul style={{ paddingLeft: "14px", marginTop: "4px" }}>
                <li>Sum of scheduled durations (in hours) of all <strong>completed</strong> <em>Academics Selfstudy</em> blocks.</li>
                <li>Duration is parsed directly from your timeblocks (e.g. <code>07:00–09:00 = 2.0h</code>).</li>
              </ul>
            </div>
            <div>
              <span style={{ color: "#5eead4" }}><strong>Impact and Role:</strong></span>
              <ul style={{ paddingLeft: "14px", marginTop: "4px" }}>
                <li><strong>Only counts</strong> when the overall task complete milestone is fully checked off.</li>
                <li><strong>Directly influences Aura</strong>, ensuring study volume acts as a powerful momentum multiplier.</li>
              </ul>
            </div>
          </div>
        </div>
      )}



      {/* Progress bar */}
      <div className="glass" style={{ padding: "16px 20px", marginBottom: "16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px" }}>
          <span style={{ fontSize: "13px", fontWeight: 500 }}>Today's Progress</span>
          <span style={{ fontSize: "13px", color: "var(--accent)" }}>
            {completedCount}/{totalCount} tasks · {pct.toFixed(0)}%
          </span>
        </div>
        <div style={{ height: "6px", background: "rgba(255,255,255,0.06)", borderRadius: "3px", overflow: "hidden" }}>
          <div style={{
            height: "100%", width: `${pct}%`,
            background: "linear-gradient(90deg, #7c5cfc, #5eead4)",
            borderRadius: "3px", transition: "width 0.5s ease",
          }} />
        </div>
      </div>

      {/* Task list */}
      <div className="glass" style={{ padding: "8px" }}>
        {!taskData || taskData.tasks.length === 0 ? (
          <div style={{ textAlign: "center", padding: "60px", color: "var(--text-muted)" }}>
            <Clock size={32} style={{ marginBottom: "12px", opacity: 0.4 }} />
            <div style={{ fontSize: "14px" }}>No tasks scheduled for today</div>
            <div style={{ fontSize: "12px", marginTop: "4px", opacity: 0.6 }}>
              Quickly lay out your time blocks using the planner
            </div>
            <button
              onClick={startPlanning}
              style={{
                marginTop: "16px",
                background: "rgba(124, 92, 252, 0.12)",
                color: "var(--accent)",
                border: "1px solid rgba(124, 92, 252, 0.3)",
                padding: "8px 16px",
                borderRadius: "8px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s",
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = "var(--accent)";
                e.currentTarget.style.color = "white";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = "rgba(124, 92, 252, 0.12)";
                e.currentTarget.style.color = "var(--accent)";
              }}
            >
              Build Today's Schedule
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {taskData.tasks.map(task => (
              <TaskRow 
                key={task.id} 
                task={task} 
                onToggle={handleToggle} 
                onToggleComplete={handleToggleComplete}
                onAttentionChange={handleAttentionChange}
              />
            ))}
          </div>
        )}
      </div>

      {/* Daily Check-In Modal Overlay */}
      {showCheckInModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
          background: "rgba(0, 0, 0, 0.7)", backdropFilter: "blur(8px)",
          display: "flex", alignItems: "center", justifyContent: "center",
          zIndex: 1000, animation: "fadeIn 0.2s ease"
        }}>
          <div className="glass fade-in" style={{
            padding: "24px", borderRadius: "16px", maxWidth: "420px", width: "90%",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            boxShadow: "0 20px 40px rgba(0, 0, 0, 0.5)",
            background: "rgba(18, 18, 24, 0.85)"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <span style={{ fontSize: "15px", fontWeight: 700, color: "var(--text)", display: "flex", alignItems: "center", gap: "8px" }}>
                <Flame size={16} style={{ color: "#f472b6" }} /> Daily Check-In
              </span>
              <button
                onClick={() => setShowCheckInModal(false)}
                style={{
                  background: "transparent", border: "none", color: "var(--text-muted)",
                  cursor: "pointer", fontSize: "14px", display: "flex", alignItems: "center"
                }}
              >
                <X size={18} />
              </button>
            </div>
            
            <p style={{ fontSize: "13px", color: "var(--text)", lineHeight: 1.5, marginBottom: "8px" }}>
              Did you keep your commitment to today&apos;s plan?
            </p>
            <p style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: 1.5, marginBottom: "20px" }}>
              Your consistency streak grows on days you tap &quot;Yes&quot; or finish at least half of your planned tasks.
              &quot;Not today&quot; resets it to zero. That&apos;s fine; tomorrow is a fresh start.
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "16px" }}>
              <button
                onClick={() => {
                  handleCheckIn(true);
                  setShowCheckInModal(false);
                }}
                style={{
                  background: metrics?.kept_commitment === true ? "rgba(52, 211, 153, 0.18)" : "rgba(255, 255, 255, 0.03)",
                  color: metrics?.kept_commitment === true ? "#34d399" : "var(--text-muted)",
                  border: metrics?.kept_commitment === true ? "1px solid rgba(52, 211, 153, 0.4)" : "1px solid rgba(255, 255, 255, 0.06)",
                  padding: "12px", borderRadius: "10px", fontSize: "13px", fontWeight: 600,
                  cursor: "pointer", transition: "all 0.15s", display: "flex", flexDirection: "column", alignItems: "center", gap: "6px"
                }}
              >
                <span style={{ fontSize: "16px" }}>✅</span>
                Yes, I kept it
              </button>
              <button
                onClick={() => {
                  handleCheckIn(false);
                  setShowCheckInModal(false);
                }}
                style={{
                  background: metrics?.kept_commitment === false ? "rgba(251, 191, 36, 0.14)" : "rgba(255, 255, 255, 0.03)",
                  color: metrics?.kept_commitment === false ? "#fbbf24" : "var(--text-muted)",
                  border: metrics?.kept_commitment === false ? "1px solid rgba(251, 191, 36, 0.4)" : "1px solid rgba(255, 255, 255, 0.06)",
                  padding: "12px", borderRadius: "10px", fontSize: "13px", fontWeight: 600,
                  cursor: "pointer", transition: "all 0.15s", display: "flex", flexDirection: "column", alignItems: "center", gap: "6px"
                }}
              >
                <span style={{ fontSize: "16px" }}>🌙</span>
                Not today
              </button>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                onClick={() => setShowCheckInModal(false)}
                style={{
                  background: "linear-gradient(135deg, #7c5cfc, #6366f1)",
                  border: "none", color: "white", padding: "8px 16px", borderRadius: "8px",
                  fontSize: "12px", fontWeight: 600, cursor: "pointer", boxShadow: "0 4px 10px rgba(124, 92, 252, 0.2)"
                }}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
