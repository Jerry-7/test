import { NavLink, Route, Routes } from "react-router-dom";

import AppShell from "./components/AppShell";
import DashboardPage from "./routes/DashboardPage";
import PlanDetailPage from "./routes/PlanDetailPage";
import PlansPage from "./routes/PlansPage";
import RunDetailPage from "./routes/RunDetailPage";
import RunsPage from "./routes/RunsPage";

export default function App() {
  return (
    <AppShell>
      <nav aria-label="Primary">
        <NavLink to="/">Dashboard</NavLink>
        <NavLink to="/plans">Plans</NavLink>
        <NavLink to="/runs">Runs</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/plans" element={<PlansPage />} />
        <Route path="/plans/:planId" element={<PlanDetailPage />} />
        <Route path="/runs" element={<RunsPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </AppShell>
  );
}
