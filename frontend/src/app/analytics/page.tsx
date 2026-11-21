"use client";

import DataLoader from "@/components/DataLoader";
import { api } from "@/lib/api";
import AnalyticsClient from "./AnalyticsClient";

async function loadAnalytics() {
  const [history, weekly, burnout] = await Promise.all([
    api.analytics.history(14),
    api.analytics.weekly(),
    api.analytics.burnout(),
  ]);
  return { history, weekly, burnout };
}

export default function AnalyticsPage() {
  return (
    <DataLoader load={loadAnalytics}>
      {d => <AnalyticsClient history={d.history} weekly={d.weekly} burnout={d.burnout} />}
    </DataLoader>
  );
}
