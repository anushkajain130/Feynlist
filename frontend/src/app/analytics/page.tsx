import { api } from "@/lib/api";
import AnalyticsClient from "./AnalyticsClient";

export const revalidate = 0;

export default async function AnalyticsPage() {
  let history = null;
  let weekly = null;
  let burnout = null;
  let unreachable = false;

  try {
    [history, weekly, burnout] = await Promise.all([
      api.analytics.history(14),
      api.analytics.weekly(),
      api.analytics.burnout(),
    ]);
  } catch {
    unreachable = true;
  }

  return <AnalyticsClient history={history} weekly={weekly} burnout={burnout} backendUnreachable={unreachable} />;
}
