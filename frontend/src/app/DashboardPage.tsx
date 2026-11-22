"use client";

import { useState } from "react";
import DataLoader from "@/components/DataLoader";
import DemoPanel from "@/components/DemoPanel";
import NudgesPanel from "@/components/NudgesPanel";
import { api } from "@/lib/api";
import DashboardClient from "./DashboardClient";

async function loadDashboard() {
  const [tasks, metrics, demo] = await Promise.all([
    api.tasks.today(),
    api.analytics.today(),
    api.demo.status(),
  ]);
  return { tasks, metrics, demo };
}

export default function DashboardPage() {
  const [version, setVersion] = useState(0);

  return (
    <DataLoader load={loadDashboard}>
      {(d, reload) => {
        const refresh = async () => { await reload(); setVersion(v => v + 1); };
        return (
          <DashboardClient
            initialTasks={d.tasks}
            initialMetrics={d.metrics}
            topSlot={
              <>
                {d.demo.demo_mode && <DemoPanel onChanged={refresh} />}
                <NudgesPanel refreshKey={version} />
              </>
            }
          />
        );
      }}
    </DataLoader>
  );
}
