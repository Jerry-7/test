import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getPlan, listModelProfiles, startRun } from "../api/client";

export default function PlanDetailPage() {
  const { planId = "" } = useParams();
  const [plan, setPlan] = useState<any | null>(null);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [profileId, setProfileId] = useState("");
  const [maxWorkers, setMaxWorkers] = useState(1);

  useEffect(() => {
    void Promise.all([getPlan(planId), listModelProfiles()]).then(
      ([nextPlan, nextProfiles]) => {
        setPlan(nextPlan);
        setProfiles(nextProfiles);
        setProfileId(
          nextPlan.model_profile_id ?? nextProfiles[0]?.model_profile_id ?? "",
        );
      },
    );
  }, [planId]);

  if (!plan) {
    return <p>Loading plan</p>;
  }

  return (
    <section>
      <h1>{plan.source_goal}</h1>
      <p>
        {plan.model_profile_name} - {plan.provider} - {plan.model_name}
      </p>
      <label>
        Run Profile
        <select
          aria-label="Run Profile"
          value={profileId}
          onChange={(event) => setProfileId(event.target.value)}
        >
          {profiles.map((profile) => (
            <option key={profile.model_profile_id} value={profile.model_profile_id}>
              {profile.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Max Workers
        <input
          aria-label="Max Workers"
          type="number"
          min={1}
          value={maxWorkers}
          onChange={(event) => setMaxWorkers(Number(event.target.value))}
        />
      </label>
      <button
        onClick={() =>
          void startRun({
            plan_id: plan.plan_id,
            profile_id: profileId,
            max_workers: maxWorkers,
          })
        }
      >
        Start run
      </button>
      <ul>
        {plan.tasks.map((task: any) => (
          <li key={task.task_id}>{task.title}</li>
        ))}
      </ul>
    </section>
  );
}
