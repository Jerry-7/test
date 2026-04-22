import { useEffect, useState } from "react";

import { listPlans, listRuns } from "../api/client";

export default function DashboardPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    let alive = true;

    async function load() {
      const [nextPlans, nextRuns] = await Promise.all([listPlans(), listRuns()]);
      if (alive) {
        setPlans(nextPlans);
        setRuns(nextRuns);
      }
    }

    void load();
    const timer = window.setInterval(load, 5000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <section>
      <h1>Dashboard</h1>
      <ul>{plans.map((plan) => <li key={plan.plan_id}>{plan.source_goal}</li>)}</ul>
      <ul>{runs.map((run) => <li key={run.run_id}>{run.run_id}</li>)}</ul>
    </section>
  );
}
