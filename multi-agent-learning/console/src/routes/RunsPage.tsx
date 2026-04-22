import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listRuns } from "../api/client";

export default function RunsPage() {
  const [runs, setRuns] = useState<any[]>([]);

  useEffect(() => {
    void listRuns().then(setRuns);
  }, []);

  return (
    <section>
      <h1>Runs</h1>
      <ul>
        {runs.map((run) => (
          <li key={run.run_id}>
            <Link to={`/runs/${run.run_id}`}>{run.run_id}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
