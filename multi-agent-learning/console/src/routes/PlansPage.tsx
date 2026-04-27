import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createPlan, listModelProfiles, listPlans } from "../api/client";

export default function PlansPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const [profiles, setProfiles] = useState<any[]>([]);
  const [task, setTask] = useState("");
  const [profileId, setProfileId] = useState("");

  useEffect(() => {
    void Promise.all([listPlans(), listModelProfiles()]).then(
      ([nextPlans, nextProfiles]) => {
        setPlans(nextPlans);
        setProfiles(nextProfiles);
        setProfileId(nextProfiles[0]?.model_profile_id ?? "");
      },
    );
  }, []);

  const hasProfiles = profiles.length > 0;

  return (
    <section>
      <h1>Plans</h1>
      {!hasProfiles ? <p>No model profile configured. Create one first.</p> : null}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!profileId) {
            return;
          }
          void createPlan({ task, profile_id: profileId });
        }}
      >
        <label>
          Goal
          <textarea
            aria-label="Goal"
            value={task}
            onChange={(event) => setTask(event.target.value)}
          />
        </label>
        <label>
          Model Profile
          <select
            aria-label="Model Profile"
            value={profileId}
            onChange={(event) => setProfileId(event.target.value)}
            disabled={!hasProfiles}
          >
            {profiles.map((profile) => (
              <option
                key={profile.model_profile_id}
                value={profile.model_profile_id}
              >
                {profile.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!hasProfiles}>
          Create plan
        </button>
      </form>
      <ul>
        {plans.map((plan) => (
          <li key={plan.plan_id}>
            <Link to={`/plans/${plan.plan_id}`}>{plan.source_goal}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
