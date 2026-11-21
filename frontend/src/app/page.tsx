import { api } from "@/lib/api";
import DashboardClient from "./DashboardClient";

export const revalidate = 0;

export default async function DashboardPage() {
  let tasks = null;
  let metrics = null;
  let unreachable = false;

  try {
    [tasks, metrics] = await Promise.all([
      api.tasks.today(),
      api.analytics.today(),
    ]);
  } catch {
    // Backend down or asleep: say so instead of showing an empty account.
    unreachable = true;
  }

  // `key` remounts the client when the backend comes back, so fresh data replaces the empty state.
  return (
    <DashboardClient
      key={unreachable ? "unreachable" : "ok"}
      initialTasks={tasks}
      initialMetrics={metrics}
      backendUnreachable={unreachable}
    />
  );
}
