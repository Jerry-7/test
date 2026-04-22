import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getRunDetail, retryRun } from "../api/client";

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [detail, setDetail] = useState<any | null>(null);

  useEffect(() => {
    let alive = true;

    async function load() {
      const next = await getRunDetail(runId);
      if (alive) {
        setDetail(next);
      }
    }

    void load();
    const timer = window.setInterval(load, 2000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [runId]);

  if (!detail) {
    return <p>Loading run detail</p>;
  }

  return (
    <section>
      <h1>Run {detail.run_id}</h1>
      <button onClick={() => void retryRun(runId)}>Retry run</button>
      <button disabled>Pause</button>
      <button disabled>Cancel</button>
      <ul>
        {detail.tasks.map((task: any) => (
          <li key={task.task_id}>
            {task.task_id} - {task.status}
          </li>
        ))}
      </ul>
      <ul>
        {detail.executions.map((execution: any) => (
          <li key={execution.task_id}>{execution.error || execution.output}</li>
        ))}
      </ul>
    </section>
  );
}
