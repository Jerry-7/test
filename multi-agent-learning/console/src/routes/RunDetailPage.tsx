import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getRunDetail, listModelProfiles, retryRun } from "../api/client";

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [detail, setDetail] = useState<any | null>(null);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [retryProfileId, setRetryProfileId] = useState("");

  useEffect(() => {
    let alive = true;

    async function load() {
      const [next, nextProfiles] = await Promise.all([
        getRunDetail(runId),
        listModelProfiles(),
      ]);
      if (alive) {
        setDetail(next);
        setProfiles(nextProfiles);
        setRetryProfileId(
          next.model_profile_id ?? nextProfiles[0]?.model_profile_id ?? "",
        );
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
      <p>
        {detail.model_profile_name} - {detail.provider} - {detail.model_name}
      </p>
      <label>
        Retry Profile
        <select
          aria-label="Retry Profile"
          value={retryProfileId}
          onChange={(event) => setRetryProfileId(event.target.value)}
        >
          {profiles.map((profile) => (
            <option key={profile.model_profile_id} value={profile.model_profile_id}>
              {profile.name}
            </option>
          ))}
        </select>
      </label>
      <button
        onClick={() =>
          void retryRun(runId, { profile_id: retryProfileId })
        }
      >
        Retry run
      </button>
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
