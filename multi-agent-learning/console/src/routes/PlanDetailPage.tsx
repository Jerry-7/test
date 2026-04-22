import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getPlan } from "../api/client";

export default function PlanDetailPage() {
  const { planId = "" } = useParams();
  const [plan, setPlan] = useState<any | null>(null);

  useEffect(() => {
    void getPlan(planId).then(setPlan);
  }, [planId]);

  if (!plan) {
    return <p>Loading plan</p>;
  }

  return (
    <section>
      <h1>{plan.source_goal}</h1>
      <ul>
        {plan.tasks.map((task: any) => (
          <li key={task.task_id}>{task.title}</li>
        ))}
      </ul>
    </section>
  );
}
