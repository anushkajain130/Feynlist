import { api } from "@/lib/api";
import DashboardClient from "./DashboardClient";

export const revalidate = 0;

export default async function DashboardPage() {
  let tasks = null;
  let metrics = null;

  try {
    [tasks, metrics] = await Promise.all([
      api.tasks.today(),
      api.analytics.today(),
    ]);
  } catch {
    // Backend may not be running; render with empty state
  }

  return <DashboardClient initialTasks={tasks} initialMetrics={metrics} />;
}
