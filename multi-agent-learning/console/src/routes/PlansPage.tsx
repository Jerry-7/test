import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listPlans } from "../api/client";

export default function PlansPage() {
  const [plans, setPlans] = useState<any[]>([]);

  useEffect(() => {
    void listPlans().then(setPlans);
  }, []);

  return (
    <section>
      <h1>Plans</h1>
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
